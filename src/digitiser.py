# pylint: disable-msg=C0103
# pylint: disable-msg=C0301
'''
@author: paulp
'''

import logging
LOGGER = logging.getLogger(__name__)

from casperfpga import KatcpClientFpga

class Digitiser(KatcpClientFpga):
    def __init__(self, host_device, port=7147):
        KatcpClientFpga.__init__(self, host_device, port)
        LOGGER.info('New Digitiser created - %s', str(self))

    def get_current_time(self):
        '''Read the latest time on the digitiser, since the last sync.
        '''
        return ((self.registers.local_time_msw.read_uint() << 32) | self.registers.local_time_lsw.read_uint())

    def __str__(self):
        return 'digitiser %s @ %i' % (self.host, self.katcp_port)
