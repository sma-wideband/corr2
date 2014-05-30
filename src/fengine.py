# pylint: disable-msg=C0103
# pylint: disable-msg=C0301
'''
@author: paulp
'''

import logging
LOGGER = logging.getLogger(__name__)

from corr2.engine import Engine
from corr2.fpgadevice import tengbe

import numpy, struct, socket

class Fengine(Engine):
    ''' An F-engine, regardless of where it is located 
    '''

    #TODO make part of separate class
    def arm_timed_latch(self, fpga, latch_name, time=None, force=False):
        ''' Arm a timed latch. Use force=True to force even if already armed 
        '''
        
        status = fpga.device_by_name('%s_status' %(latch_name)).read()['data']

        # get armed, arm and load counts
        armed_before = status['armed']
        arm_count_before = status['arm_count']
        load_count_before = status['load_count']

        # if not forcing it, check for already armed first
        if armed_before == True:
            if force == False:
                LOGGER.info('forcing arm of already armed timed latch %s' %latch_name)
            else:
                LOGGER.error('timed latch %s already armed' %latch_name)
                return

        # we load immediate if not given time
        if time == None:
            fpga.device_by_name('%s_control0' %(latch_name)).write(arm=0, load_immediate=1)
            fpga.device_by_name('%s_control0' %(latch_name)).write(arm=1, load_immediate=1)
                
            #TODO time
            LOGGER.info('Timed latch %s arm-for-immediate-loading attempt' %latch_name)
            
        else: 
            # TODO time conversion
            time_samples = numpy.uint32(0)
            time_msw = (time_samples & 0xFFFF0000) >> 32
            time_lsw = (time_samples & 0x0000FFFF)
            
            fpga.device_by_name('%s_control0' %(latch_name)).write(arm=0, load_immediate=0)
            fpga.device_by_name('%s_control0' %(latch_name)).write(arm=1, load_immediate=0)

            #TODO time
            LOGGER.info('Timed latch %s arm-for-loading-at-time attempt' %latch_name)

        #TODO check that arm count increased as expected
        status = fpga.device_by_name('%s_status' %(latch_name)).read()['data']
        
        # get armed, arm and load counts
        armed_after = status['armed']
        arm_count_after = status['arm_count']
        load_count_after = status['load_count']
        
        # armed count did not succeed
        if arm_count_after != (arm_count_before+1):
            #TODO time
            LOGGER.error('Timed latch %s arm count at %i instead of %i' %(latch_name, arm_count_after, (arm_count_before+1)))
        else:
            # check load count increased as expected
            if time == None: 
                if load_count_after != (load_count_before+1):
                    LOGGER.error('Timed latch %s load count at %i instead of %i' %(latch_name, load_count_after, (load_count_before+1)))

            else:
                LOGGER.info('Timed latch %s successfully armed' %(latch_name))

    def get_timed_latch_status(self, fpga, device):
        ''' Get current state of timed latch device
        '''
        tl_control_reg = fpga.device_by_name('%s_control'%device).read()['data']
        tl_control0_reg = fpga.device_by_name('%s_control0'%device).read()['data']
        tl_status_reg = fpga.device_by_name('%s_status'%device).read()['data']

        status = {}
        status['armed'] = tl_status_reg['armed']
        status['arm_count'] = tl_status_reg['arm_count']       
        status['load_count'] = tl_status_reg['load_count']       
        #TODO convert this to a time
        status['load_time'] = (tl_control0_reg['load_time_msw'] << 32) | (tl_control_reg['load_time_lsw'])

        return status

    #################
    # fengine setup #
    #################
    
    #TODO put in try block/s to detect bad info dictionary
    def init_config(self, info=None):
        ''' initialise config from info 
        '''
        #defaults if no info passe#d
        if info == None:
            #TODO determine n_chans from system info
            self.config = { 'n_chans': 4096, 
                            'fft_shift': 0,
                            'sampling_frequency': 1700000000,
                            'feng_id': 0,
                            'board_id': 0,
                            'txport': 0,
                            'txip_str': '192.168.0.0'}
            
            #TODO determine some equalisation factors from system info
            self.config['equalisation'] = {}
            self.config['equalisation']['decimation'] =     1
            self.config['equalisation']['coeffs'] =         []
            self.config['equalisation']['poly'] =           [1]
            self.config['equalisation']['type'] =           'complex'
            self.config['equalisation']['n_bytes'] =        2      #number of bytes per coefficient
            self.config['equalisation']['bin_pt'] =         1      #location of binary point/number of fractional bits
            self.config['equalisation']['default'] =        'poly'

            #TODO
            #NOTE   delay are unsigned (positive), phase and delta values are signed
            #       phase and delta values are in the range (-1,1]

            #TODO should get this from system info
            self.config['delay_tracking'] = {}
            self.config['delay_tracking']['delay_integer_bits'] =       16
            self.config['delay_tracking']['delay_fractional_bits'] =    16
            self.config['delay_tracking']['delta_delay_bits'] =         16
            self.config['delay_tracking']['phase_bits'] =               16
            self.config['delay_tracking']['delta_phase_bits'] =         16
            self.config['delay_tracking']['divisor_bits'] =             16
            self.config['delay_tracking']['min_ld_time'] =              0.1
            self.config['delay_tracking']['network_latency_adjust'] =   0.015
                            
        else:
            self.config = {}
            #number of channels post PFB
            self.config['n_chans'] = info['n_chans']         

            #shift factor for every FFT stage
            self.config['fft_shift'] = info['fft_shift'] 
            #scale factor applied to timestamp to get time in ms
            #self.config['mcnt_scale_factor'] = info['mcnt_scale_factor']
            #sampling frequency in Hz
            self.config['sampling_frequency'] = info['sampling_frequency']
            #feng on board 
            self.config['feng_id'] = info['feng_id']
            #board id
            self.config['board_id'] = info['board_id']
            
            self.config['txport'] = info['txport']
            txip_str = info['txip_str']
            self.config['txip_str'] = txip_str
            self.config['txip'] = struct.unpack('>L',socket.inet_aton(txip_str))[0]
            
            #equalisation settings
            self.config['equalisation'] = {}
            #number of channels each value applied to
            self.config['equalisation']['decimation'] = info['equalisation']['decimation']
            #list of complex values
            self.config['equalisation']['coeffs'] = info['equalisation']['coeffs']
            #'complex' or 'real'
            self.config['equalisation']['type'] = info['equalisation']['type']
            #default form, 'poly' or 'coeffs'
            self.config['equalisation']['default'] = info['equalisation']['default']

    def __init__(self, parent, info=None):
        ''' Constructor '''
        Engine.__init__(self, parent, 'f-engine')
        
        #set up configuration related to this f-engine
        self.init_config(info)
        
        LOGGER.info('%i-channel Fengine created with id %i @ %s',
            self.config['n_chans'], self.config['feng_id'], str(self.parent))

    def setup(self, reset=True, set_eq=True, send_spead=True):
        ''' Configure fengine for data processing 
        '''

        #check status
        #place in reset
        self.enable_reset()
        #clear status bits
        self.clear_status()
        #calibrate qdr sram
        #TODO    
        #set fft shift
        self.set_fft_shift()
        #set board id used to tag data
        self.set_board_id()
        #set equaliser settings pre requantization
        if set_eq == True:
            self.set_eq()
        #configure comms settings
        self.set_txip()
        self.set_txport()
        #send SPEAD meta data
        #TODO
        #remove reset
        self.disable_reset()
        #check status
        status = self.get_status(debug=False)
        #TODO what do we expect to have happened at this point?
    
    def calibrate(self, qdr=True):
        ''' Run software calibration 
        '''
        raise NotImplementedError

    ########
    # TVGs #
    ########
   
    def enable_tvg(self, dvalid=False, adc=False, pfb=False, corner_turner=False):
        ''' turn on specified (default is none) tvg/s 
                dvalid          : simulate enable signal from unpack block
                adc             : simulate impulse data from unpack block
                pfb             : simulate constant from PFB
                corner_turner   : simulate frequency channel label in each channel after corner turner
        ''' 

        #prepare for posedge on enable
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_en = 0)

        if dvalid == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_dvalid = True)
        if adc == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_adc = True)
        if pfb == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_pfb = True)
        if corner_turner == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_ct = True)

        #posedge on enable 
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_en = 1)
    
    def disable_tvg(self, dvalid=True, adc=True, pfb=True, corner_turner=True):
        ''' turn off specified (default is all) tvg/s
        '''
        
        #prepare for posedge on enable
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_en = 0)

        if dvalid == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_dvalid = False)
        if adc == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_adc = False)
        if pfb == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_pfb = False)
        if corner_turner == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_ct = False)

        #posedge on enable 
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(tvg_en = 1)

    ##################
    # Data snapshots #
    ##################

    def get_adc_data_snapshot(self):
        ''' Get snapshot of adc data 
        '''
   
        #get raw data 
        data = self.parent.device_by_name('snap_adc%i_ss'%(self.config['feng_id'])).read(man_trig=False, man_valid=True)['data']   
 
        streams = len(data.keys())
        length = len(data['data0'])
    
        #extract data in order and stack into rows 
        data_stacked = numpy.vstack(data['data%i' %count] for count in range(streams))
    
        repacked = numpy.reshape(data_stacked, streams*length, 1)

        return repacked

    def get_quantiser_data_snapshot(self):
        ''' Get snapshot of data after quantiser 
        '''

        data = self.parent.device_by_name('snap_quant%i_ss'%(self.config['feng_id'])).read(man_trig=False, man_valid=False)['data']   
        
        streams = len(data.keys())
        length = len(data['real0'])

        #extract data in order and stack into columns
        data_stacked = numpy.column_stack((numpy.array(data['real%i' %count])+1j*numpy.array(data['imag%i' %count])) for count in range(streams/2))
    
        repacked = numpy.reshape(data_stacked, (streams/2)*length, 1)

        return repacked

    ##################################################
    # Status monitoring of various system components #
    ##################################################

    def clear_status(self, comms=True, fstatus_reg=True):
        ''' Clear status registers 
        '''
        # needs a positive edge to clear 
        if comms == True and fstatus_reg == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(status_clr=0, comms_status_clr=0)
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(status_clr=1, comms_status_clr=1)
        elif comms == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(comms_status_clr=0)
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(comms_status_clr=1)
        elif fstatus_reg == True:
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(fstatus_reg=0)
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(fstatus_reg=1)
    
    def get_status(self, rx_comms=True, timestamp=True, dsp=True, tx_comms=True, timed_latches=True, debug=True):
        ''' Status of f-engine returned in dictionary. All status returned if specific status not specified 
        '''

        status = {}
       
        status['board_id'] = self.get_board_id()
        status['engine_id'] = self.get_engine_id()
 
        if rx_comms == True:
            status['rx_comms'] = self.get_rx_comms_status(debug=debug)
        
        if timestamp == True:
            status['timestamp'] = self.get_timestamp()       
                
        if dsp == True:
            status['dsp'] = self.get_dsp_status()
        
        if tx_comms == True:
            status['tx_comms'] = self.get_tx_comms_status(debug=debug)
            
        if timed_latches == True:
            status['timed_latches'] = self.get_timed_latches_status()

        return status

    ######################################
    # Control of various system settings #
    ######################################
    
    def get_timed_latches_status(self, coarse_delay=True, fine_delay=True, tvg=True):
        ''' Get status of timed latches 
        '''

        status = {}
        if coarse_delay == True:
            status['coarse_delay'] = self.get_timed_latch_status('tl_cd%i'%(self.config['feng_id']))

        #if tvg == True:
        #    status['tvg'] = self.get_timed_latch_status('tl_tvg')
        
        if fine_delay == True:
            status['fine_delay'] = self.get_timed_latch_status('tl_fd%i'%(self.config['feng_id']))

        return status
 
    def get_dsp_status(self):
        ''' Get current state of DSP pipeline 
        '''
        
        #control
        control_reg = self.parent.device_by_name('control%i'%(self.config['feng_id'])).read()['data']
        status_reg = self.parent.device_by_name('dsp_status%i'%(self.config['feng_id'])).read()['data']
        trigger_level_reg = self.parent.device_by_name('trigger_level').read()['data']
        fft_shift_reg = self.parent.device_by_name('fft_shift').read()['data']

        #in reset
        control = {'reset': control_reg['dsp_rst']} 

        #status
        dsp_status = {}
        #adc overflows reported
        dsp_status['adc_over_range'] = status_reg['adc_or']
        #fft over range
        dsp_status['fft_over_range'] = status_reg['fft_or']
        #requantiser overflow
        dsp_status['equalisation_over_range'] = status_reg['quant_or']
        #qdr not ready
        dsp_status['qdr_sram_not_ready'] = status_reg['qdr_not_ready']
        #qdr calibration fail
        dsp_status['qdr_calibration_fail'] = status_reg['qdr_cal_fail']
        #qdr parity error
        dsp_status['qdr_parity_error'] = status_reg['qdr_parity_error']
   
        status = {}
        #trigger level
        status['trigger_level'] = trigger_level_reg['trigger_level']
        #fft shift
        status['fft_shift'] = fft_shift_reg['fft_shift']
        status['status'] = dsp_status
        status['control'] = control

        return status
         
    # fft shift
    def set_fft_shift(self, fft_shift=None):
        ''' Set current FFT shift schedule 
        '''    
        if fft_shift == None:
            fft_shift = self.config['fft_shift']
        else:
            self.config['fft_shift'] = fft_shift
        self.parent.device_by_name('fft_shift').write(fft_shift=fft_shift)
    
    def get_fft_shift(self):
        ''' Get current FFT shift schedule 
        '''
        fft_shift = self.parent.device_by_name('fft_shift').read()['data']['fft_shift']
        self.config['fft_shift'] = fft_shift
        return fft_shift
   
    # board id
    def get_board_id(self):
        ''' Get board ID 
        '''
        board_id = self.parent.device_by_name('board_id').read()['data']['board_id']
        self.config['board_id'] = board_id
        return board_id
   
    def set_board_id(self, board_id=None):
        ''' Set board ID 
        '''
        if board_id == None:
            board_id = self.config['board_id']
        else:
            self.config['board_id'] = board_id
        self.parent.device_by_name('board_id').write(board_id=board_id)
    
    # engine id
    def get_engine_id(self):
        ''' Get engine ID 
        '''
        return self.config['feng_id']
   
    def set_engine_id(self, engine_id):
        ''' Set engine ID 
        '''
        self.config['feng_id'] = engine_id

    # reset
    def enable_reset(self, dsp=True, comms=True):
        ''' Place aspects of system in reset 
        '''
        if (dsp == True) and (comms == True):
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(dsp_rst=1, comms_rst=1)
        elif (dsp == True):
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(dsp_rst=1)
        elif (comms == True):
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(comms_rst=1)
    
    def disable_reset(self, dsp=True, comms=True):
        ''' Remove aspects of system from reset 
        '''
        if (dsp == True) and (comms == True):
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(dsp_rst=0, comms_rst=0)
        elif (dsp == True):
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(dsp_rst=0)
        elif (comms == True):
            self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(comms_rst=0)
   
    # timestamp
    def get_timestamp(self):
        ''' Get timestamp of data currently being processed 
        '''
        lsw = self.parent.device_by_name('timestamp_lsw').read()['data']['timestamp_lsw']
        msw = self.parent.device_by_name('timestamp_msw').read()['data']['timestamp_msw']
        return numpy.uint32(msw << 32) + numpy.uint32(lsw) 

    # flashy leds on front panel
    def enable_kitt(self):
        ''' Turn on the Knightrider effect 
        '''
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(fancy_en=1)
    
    def disable_kitt(self):
        ''' Turn off the Knightrider effect 
        '''
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(fancy_en=0)

    # trigger level
    def set_trigger_level(self, trigger_level):    
        ''' Set the level at which data capture to snapshot is stopped 
        '''
        self.parent.device_by_name('trigger_level').write(trigger_level=trigger_level)

    def get_trigger_level(self):    
        ''' Get the level at which data capture to snapshot is stopped 
        '''
        return self.parent.device_by_name('trigger_level').read()['data']['trigger_level']

    #################################
    # Delay and phase compensation  #
    #################################

    #TODO
    def set_delay(self, ant_str, delay=0, delay_delta=0, phase=0, phase_delta=0, load_time=None, load_check=True, extra_wait_time = 0):
        raise NotImplementedError

    ##################
    # RX comms stuff #
    ##################

    def get_rx_comms_status(self, debug=True):
        ''' Get status for rx comms, debug=True gives low level core info 
        '''

        #control
        reg = self.parent.device_by_name('control%i'%(self.config['feng_id'])).read()['data']
        control = {'enabled': (reg['comms_en'] == 1), 'reset': (reg['comms_rst'] == 1)} 

        #status
        reg = self.parent.device_by_name('comms_status%i'%(self.config['feng_id'])).read()['data']

        core_info = {}
        #core info
        for gbe in self.parent.tengbes:
            core_info[gbe.name] = {}
            if debug == True:
                core_info[gbe.name]['core_details'] = gbe.get_10gbe_core_details()
                core_info[gbe.name]['counters'] = gbe.read_tx_counters()

        #TODO check that these names exist
        for index in range(4):
            gbe = {}
            #link down reported by gbe core
            gbe['link_down'] = (((reg['gbe_ldn'] >> index) & 0x1) == 1)
            #spead_unpack reported error
            #1. SPEAD header bad
            #2. SPEAD flags not received or bad
            #3. payload length not expected length
            gbe['spead_error'] = (((reg['spead_error'] >> index) & 0x1) == 1)
            #an overflow happened in the fifo buffer in the unpack/fifo block 
            #this should never happen, packets should be discarded first (see packet_discarded)
            gbe['unpack_fifo_overflow'] = (((reg['unpack_fifo_of'] >> index) & 0x1) == 1)
            #fifo block in unpack discarded packet due to one of the following;
            #1. discard line went high during packet reception
            #2. packet was not the correct multiple of words
            #3. the fifo contained the maximum packets supported and might overflow
            #4. the maximum number of words supported per packet is being exceeded
            gbe['packet_discarded'] = (((reg['packet_of'] >> index) & 0x1) == 1)
            core_info['gbe%i' %index]['status'] = gbe                

        status = {}
        #this polarisation is missing data
        status['missing_data'] = (reg['recvd_error'] == 1)
        #one of the polarisations is missing
        status['data_streams_misaligned'] = (reg['misaligned'] == 1)
        #data count does not align with timestamp changes expected
        status['timestamp_error'] = (reg['timestamp_error'] == 1)
        #timestamp received by unpack/pkt_reorder block not in range allowed
        status['timestamp_unlocked'] = (reg['mcnt_no_lock'] == 1)

        rx_status = {}
        rx_status['core_info'] = core_info
        rx_status['control'] = control
        rx_status['status'] = status
      
        return rx_status

    ##################
    # TX comms stuff #
    ##################

    def get_tx_comms_status(self, debug=True):
        ''' Get status of tx comms, debug=True gives low level core info 
        '''

        #status
        reg = self.parent.device_by_name('comms_status%i'%(self.config['feng_id'])).read()['data']
        status = {} 

        core_info = {}
        #core info
        for gbe in self.parent.tengbes:
            core_info[gbe.name] = {}
            if debug == True:
                core_info[gbe.name]['core_details'] = gbe.get_10gbe_core_details()
                core_info[gbe.name]['counters'] = gbe.read_tx_counters()

        #TODO check that these names exist
        for index in range(4):
            gbe = {}
            #link down reported by gbe core
            gbe['link_down'] = (((reg['gbe_ldn'] >> index) & 0x1) == 1)
            #TX FIFO overflowed (a reset of the gbe core is required)
            gbe['gbe_fifo_overflow'] = (((reg['gbe_of'] >> index) & 0x1) == 1)
            #spead_pack detected error
            #1. payload length is not as expected
            gbe['spead_error'] = (((reg['pack_of'] >> index) & 0x1) == 1)
            core_info['gbe%i' %index]['status'] = gbe

        #control
        reg = self.parent.device_by_name('control%i'%(self.config['feng_id'])).read()['data']
        control = {'enabled': (reg['comms_en'] == 1), 'reset': (reg['comms_rst'] == 1)} 
 
        tx_status = {}        
        #base ip and port
        tx_status['base_port'] = self.get_txport()
        tx_status['base_ip'] = self.get_txip_str()

        tx_status['core_info'] = core_info
        tx_status['control'] = control
        tx_status['status'] = status

        return tx_status
 
    # base data transmission UDP port 
    def set_txport(self, txport=None, issue_spead=False):
        ''' Set data transmission port 
        '''    
        if txport == None:
            txport = self.config['txport']
        
        self.config['txport'] = txport
        self.parent.device_by_name('txport').write(port_gbe=txport)

        #TODO spead stuff

    def get_txport(self):
        ''' Get data transmission port 
        '''    
        txport = self.parent.device_by_name('txport').read()['data']['port_gbe']
        self.config['txport'] = txport 
        return txport

    # data transmission UDP IP address 
    def set_txip(self, txip_str=None, txip=None, issue_spead=False):
        ''' Set data transmission IP base 
        '''    
        if txip_str == None and txip == None:
            txip = self.config['txip']
            txip_str = self.config['txip_str']
        elif txip == None:
            self.config['txip_str'] = txip_str
            txip = struct.unpack('>L',socket.inet_aton(txip_str))[0]
            self.config['txip'] = txip
        else:
            self.config['txip_str'] = tengbe.ip2str(txip)
            self.config['txip'] = txip
        
        #TODO spead stuff

        self.parent.device_by_name('txip').write(ip_gbe=txip)
    
    def get_txip(self):
        ''' Get current data transmission IP base 
        '''
        txip = self.parent.device_by_name('txip').read()['data']['ip_gbe']
        self.config['txip'] = txip 
        self.config['txip_str'] = tengbe.ip2str(txip)
        return txip
    
    def get_txip_str(self):
        ''' Get current data transmission IP base in string form 
        '''
        txip = self.parent.device_by_name('txip').read()['data']['ip_gbe']
        self.config['txip'] = txip 
        txip_str = tengbe.ip2str(txip)
        self.config['txip_str'] = txip_str
        return txip_str

    def reset_tx_comms(self):
        ''' Place all communications logic in reset 
        '''
        self.enable_reset(comms=True)
   
    #TODO SPEAD stuff
    def config_tx_comms(self, reset=True, issue_spead=True):
        ''' Configure transmission infrastructure 
        ''' 
        if reset == True:
            self.disable_tx_comms()
            self.reset_tx_comms()   
    
    def enable_tx_comms(self):
        ''' Enable communications transmission. Comms for both fengines need to be enabled for data to flow 
        '''
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(comms_en=1, comms_rst=0)
    
    def disable_tx_comms(self):
        ''' Disable communications transmission. Comms for both fengines need to be enabled for data to flow 
        '''
        self.parent.device_by_name('control%i'%(self.config['feng_id'])).write(comms_en=1)
 
    #TODO SPEAD stuff
    def start_tx(self, issue_spead=True):
        ''' Start data transmission 
        '''
        self.enable_tx_comms()
 
    def stop_tx(self, issue_spead=True):
        ''' Stop data transmission 
        '''
        self.disable_tx_comms()

    ################   
    # SPEAD stuff ##
    ################
 
    #TODO 
    def issue_spead(self):
        ''' Issue SPEAD meta data 
        '''
        raise NotImplementedError


    ##############################################
    # Equalisation before re-quantisation stuff  #
    ##############################################

    def pack_eq(self, coeffs, n_bits, bin_pt=0, signed=True):
        ''' Convert coeffs into a string with n_bits of resolution and a binary point at bin_pt 
        '''
        
        if len(coeffs) == 0:
            raise RuntimeError('Passing empty coeffs list')
        if bin_pt < 0:
            raise RuntimeError('Binary point cannot be less than 0')
        
        step = 1/(2**bin_pt) #coefficient resolution

        if signed == True:
            min_val = -(2**(n_bits-bin_pt-1))
            max_val = -(min_val)-step
        else:
            min_val = 0
            max_val = 2**(n_bits-bin_pt)-step

        if numpy.max(coeffs) > max_val or numpy.min(coeffs) < min_val:
            raise RuntimeError('Coeffs out of range')
     
        is_complex = numpy.iscomplexobj(coeffs)
        if is_complex == True:
            n_coeffs = len(coeffs)*2
            coeffs = numpy.array(coeffs, dtype = numpy.complex128)
        else:
            n_coeffs = len(coeffs) 
            coeffs = numpy.array(coeffs, dtype = numpy.float64)
     
        #compensate for fractional bits
        coeffs = (coeffs * 2**bin_pt)

        byte_order = '>' #big endian

        if n_bits == 16:
            if signed == True:
                pack_type = 'h'
            else:
                pack_type = 'H'
        else:
            raise RuntimeError('Don''t know how to pack data type with %i bits' %n_bits)
        
        coeff_str = struct.pack('%s%i%s' %(byte_order, n_coeffs, pack_type), *coeffs.view(dtype=numpy.float64))
        return coeff_str

    def unpack_eq(self, string, n_bits, eq_complex=True, bin_pt=0, signed=True):
        ''' Unpack string according to format specified. Return array of floats 
        '''

        byte_order = '>' #big endian

        n_vals = len(string)/(n_bits/8)

        if n_bits == 16:
            if signed == True:
                pack_type = 'h'
            else:
                pack_type = 'H'
        else:
            raise RuntimeError('Don''t know how to pack data type with %i bits' %n_bits)
        
        coeffs = struct.unpack('%s%i%s'%(byte_order, n_vals, pack_type), string)
        coeffs_na = numpy.array(coeffs, dtype = numpy.float64)

        coeffs = coeffs_na/(2**bin_pt) #scale by binary points 
        
        if eq_complex == True:
            #change view to 64 bit floats packed as complex 128 bit values
            coeffs = coeffs.view(dtype = numpy.complex128) 

        return coeffs 

    def get_eq(self):
        ''' Get current equalisation values applied pre-quantisation 
        '''
        
        register_name='eq%i'%(self.config['feng_id'])
        n_chans = self.config['n_chans']
        decimation = self.config['equalisation']['decimation']
        n_coeffs = n_chans/decimation

        eq_type = self.config['equalisation']['type']
        if eq_type == 'complex':
            n_coeffs = n_coeffs*2

        n_bytes = self.config['equalisation']['n_bytes']
        bin_pt = self.config['equalisation']['bin_pt']

        #read raw bytes
        coeffs_raw = self.parent.read(register_name, n_coeffs*n_bytes)

        if eq_type == 'complex':
            eq_complex = True
        else:
            eq_complex = False

        coeffs = self.unpack_eq(coeffs_raw, n_bytes*8, eq_complex, bin_pt, signed=True)        

        #pad coeffs out by decimation factor
        coeffs_padded = numpy.reshape(numpy.tile(coeffs, [decimation, 1]), [1, n_chans], 'F')
    
        return coeffs_padded[0]
    
    def get_default_eq(self):
        ''' Get default equalisation settings 
        '''
        
        decimation = self.config['equalisation']['decimation']
        n_chans = self.config['n_chans']       
        n_coeffs = n_chans/decimation
        eq_default = self.config['equalisation']['default']

        if eq_default == 'coeffs':
            equalisation = self.config['equalisation']['coeffs']
        elif eq_default == 'poly':
            poly = self.config['equalisation']['poly']
            equalisation = numpy.polyval(poly, range(n_chans))[decimation/2::decimation]
            if self.config['equalisation']['type'] == 'complex':
                equalisation = [eq+0*1j for eq in equalisation]
        else:
            raise RuntimeError("Your EQ type, %s, is not understood." % eq_default)

        if len(equalisation) != n_coeffs:
            raise RuntimeError("Something's wrong. I have %i eq coefficients when I should have %i." % (len(equalisation), n_coeffs))
        return equalisation

    def set_eq(self, init_coeffs=[], init_poly=[]):
        ''' Set equalisation values to be applied pre-quantisation 
        '''

        n_chans = self.config['n_chans']
        decimation = self.config['equalisation']['decimation']
        n_coeffs = n_chans / decimation

        if init_coeffs == [] and init_poly == []:
            coeffs = self.get_default_eq()
        elif len(init_coeffs) == n_coeffs:
            coeffs = init_coeffs
        elif len(init_coeffs) == n_chans:
            coeffs = init_coeffs[0::decimation]
            LOGGER.warn("You specified %i EQ coefficients but your system only supports %i actual values. Only writing every %ith value."%(n_chans ,n_coeffs, decimation))
        elif len(init_coeffs) > 0:
            raise RuntimeError ('You specified %i coefficients, but there are %i EQ coefficients in this design.'%(len(init_coeffs), n_coeffs))
        else:
            coeffs = numpy.polyval(init_poly, range(n_chans))[decimation/2::decimation]

        eq_type = self.config['equalisation']['type'] 
        if eq_type == 'scalar':
            coeffs = numpy.real(coeffs)
        elif eq_type == 'complex':
            coeffs = numpy.complex64(coeffs)
        else:
            raise RuntimeError ('Don''t know what to do with %s equalisation type.'%eq_type)

        n_bytes = self.config['equalisation']['n_bytes'] 
        bin_pt = self.config['equalisation']['bin_pt'] 

        coeffs_str = self.pack_eq(coeffs, n_bits=n_bytes*8, bin_pt=bin_pt, signed=True) 

        # finally write to the bram
        self.parent.write('eq%i'%self.config['feng_id'], coeffs_str)


# end
