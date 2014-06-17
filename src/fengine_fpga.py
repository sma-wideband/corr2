import logging
LOGGER = logging.getLogger(__name__)

from corr2.fengine import Fengine
from corr2.engine_fpga import EngineFpga
from corr2 import engine_fpga

from misc import log_runtime_error, log_not_implemented_error

import numpy

class FengineFpga(EngineFpga, Fengine):
    ''' An fengine that is also an engine using an FPGA as a host
        Data from two polarisations are received via SPEAD, channelised, equalised pre-requantisation, corner-turned 
        and transmitted via SPEAD. Delay correction is applied via coarse delay before channelisation and phase 
        rotation post channelisation. 
    '''

    def __init__(self, ant_id, host_device, engine_id=0, host_instrument=None, config_file=None, descriptor='fengine_fpga'):
        ''' Constructor 
        @param host: host device 
        @param engine_id: index of fengine on FPGA
        '''
        EngineFpga.__init__(self, host_device, engine_id, host_instrument, config_file, descriptor)
        Fengine.__init__(self, ant_id)

        self._get_fengine_fpga_config()

    def __getattribute__(self, name):
        '''Overload __getattribute__ to make shortcuts for getting object data.
        '''

        # fft_shift is same for all fengine_fpgas of this type on device
        if name == 'fft_shift':
            return self.host.device_by_name('%sfft_shift' %self.tag)
        # we cant
        elif name == 'eq0_name':
            return '%seq%s' %(self.tag, self.pol0_offset)
        elif name == 'eq1_name':
            return '%seq%s' %(self.tag, self.pol1_offset)
        elif name == 'txip_base':
            return self.host.device_by_name('%stxip_base%s' %(self.tag, self.offset))
        elif name == 'txport':
            return self.host.device_by_name('%stxport%s' %(self.tag, self.offset))
        # two polarisations
        elif name == 'snap_adc0':
            return self.host.device_by_name('%ssnap_adc%s_ss'%(self.tag, self.pol0_offset))
        elif name == 'snap_adc1':
            return self.host.device_by_name('%ssnap_adc%s_ss'%(self.tag, self.pol1_offset))
        elif name == 'snap_quant0':
            return self.host.device_by_name('%sadc_quant%s_ss'%(self.tag, self.pol0_offset))
        elif name == 'snap_quant1':
            return self.host.device_by_name('%sadc_quant%s_ss'%(self.tag, self.pol1_offset))
        
        return EngineFpga.__getattribute__(self, name)

    def _get_fengine_fpga_config(self):
  
        # constants for accessing polarisation specific registers 'x' even, 'y' odd  
        self.pol0_offset = '%s'%(str(self.id*2))
        self.pol1_offset = '%s'%(str(self.id*2+1))

        # default fft shift schedule 
        self.config['fft_shift']                        = self.config_portal.get_int(['%s'%self.descriptor, 'fft_shift'])    
        
        # output data resolution after requantisation
        self.config['n_bits_output']                    = self.config_portal.get_int(['%s'%self.descriptor, 'n_bits_output'])    
        self.config['bin_pt_output']                    = self.config_portal.get_int(['%s'%self.descriptor, 'bin_pt_output'])    

        # equalisation
        self.config['equalisation'] = {}
        # TODO this may not be constant across fengines (?)
        self.config['equalisation']['decimation']       = self.config_portal.get_int(['equalisation', 'decimation'])    
        # TODO what is this?
        self.config['equalisation']['tolerance']        = self.config_portal.get_float(['equalisation', 'tolerance'])    
        # coeffs
        self.config['equalisation']['n_bytes_coeffs']   = self.config_portal.get_int(['equalisation', 'n_bytes_coeffs'])    
        self.config['equalisation']['bin_pt_coeffs']    = self.config_portal.get_int(['equalisation', 'bin_pt_coeffs'])    
        # default polynomials
        self.config['equalisation']['poly0']            = self.config_portal.get_int_list(['%s'%self.descriptor, 'poly0'])    
        self.config['equalisation']['poly1']            = self.config_portal.get_int_list(['%s'%self.descriptor, 'poly1'])    

    #######################
    # FFT shift schedule  #
    #######################

    def set_fft_shift(self, shift_schedule=None, issue_spead=True):
        ''' Set the FFT shift schedule
        @param shift_schedule: int representing bit mask. '1' represents a shift for that stage. First stage is MSB. Use default if None provided
        '''
        if shift_schedule == None:
            shift_schedule = self.config['fft_shift']
        self.fft_shift.write(fft_shift=shift_schedule)

    def get_fft_shift(self):
        ''' Get the current FFT shift schedule
        @return bit mask in the form of an unsigned integer
        '''
        return self.fft_shift.read()['data']['fft_shift']
    
    ##############################################
    # Equalisation before re-quantisation stuff  #
    ##############################################

    def get_equalisation(self, pol_index):
        ''' Get current equalisation values applied pre-quantisation 
        '''

        reg_name = getattr(self, 'eq%s_name'%pol_index)
        n_chans = self.config['n_chans']
        decimation = self.config['equalisation']['decimation']
        n_coeffs = n_chans/decimation * 2

        n_bytes = self.config['equalisation']['n_bytes_coeffs']
        bin_pt = self.config['equalisation']['bin_pt_coeffs']

        #read raw bytes
        # we cant access brams like registers, so use old style read
        coeffs_raw = self.host.read(reg_name, n_coeffs*n_bytes)

        coeffs = self.str2float(coeffs_raw, n_bytes*8, bin_pt)        

        #pad coeffs out by decimation factor
        coeffs_padded = numpy.reshape(numpy.tile(coeffs, [decimation, 1]), [1, n_chans], 'F')
    
        return coeffs_padded[0]
    
    def get_default_equalisation(self, pol_index):
        ''' Get default equalisation settings 
        '''
        
        decimation = self.config['equalisation']['decimation']
        n_chans = self.config['n_chans']       
        n_coeffs = n_chans/decimation

        poly = self.config['equalisation']['poly%s' %pol_index]
        eq_coeffs = numpy.polyval(poly, range(n_chans))[decimation/2::decimation]
        eq_coeffs = numpy.array(eq_coeffs, dtype=complex)

        if len(eq_coeffs) != n_coeffs:
            log_runtime_error(LOGGER, "Something's wrong. I have %i eq coefficients when I should have %i." % (len(eq_coeffs), n_coeffs))
        return eq_coeffs

    def set_equalisation(self, pol_index, init_coeffs=[], init_poly=[], issue_spead=True):
        ''' Set equalisation values to be applied pre-requantisation 
        '''

        reg_name = getattr(self, 'eq%s_name'%pol_index)
        n_chans = self.config['n_chans']
        decimation = self.config['equalisation']['decimation']
        n_coeffs = n_chans / decimation

        if init_coeffs == [] and init_poly == []:
            coeffs = self.get_default_equalisation(pol_index)
        elif len(init_coeffs) == n_coeffs:
            coeffs = init_coeffs
        elif len(init_coeffs) == n_chans:
            coeffs = init_coeffs[0::decimation]
            LOGGER.warn("You specified %i EQ coefficients but your system only supports %i actual values. Only writing every %ith value."%(n_chans ,n_coeffs, decimation))
        elif len(init_coeffs) > 0:
            log_runtime_error(LOGGER, 'You specified %i coefficients, but there are %i EQ coefficients required for this engine'%(len(init_coeffs), n_coeffs))
        else:
            coeffs = numpy.polyval(init_poly, range(n_chans))[decimation/2::decimation]
            coeffs = numpy.array(coeffs, dtype=complex)

        n_bytes = self.config['equalisation']['n_bytes_coeffs'] 
        bin_pt = self.config['equalisation']['bin_pt_coeffs'] 

        coeffs_str = self.float2str(coeffs, n_bytes*8, bin_pt) 

        # finally write to the bram
        self.host.write(reg_name, coeffs_str)

    def receiving_valid_data(self):
        '''The engine is receiving valid data.
        @return True or False
        '''
        #TODO
        return True

    def producing_data(self):
        ''' The engine is producing data ready for transmission
        '''
        #TODO 
        return True

    #TODO
    def set_delay(self, pol_index, delay=0, delay_delta=0, phase=0, phase_delta=0, load_time=None):
        ''' Apply delay correction coefficients to polarisation specified from time specified
        @param pol_index: polarisation
        @param delay: delay in samples
        @param delay_delta: change in delay in samples per ADC sample 
        @param phase: initial phase offset TODO units
        @param phase_delta: change in phase TODO units
        @param load_time: time to load values in ADC samples since epoch. If None load immediately
        '''
        log_not_implemented_error(LOGGER, '%s.set_delay not implemented'%self.descriptor)
