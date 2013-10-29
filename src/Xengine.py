'''
@author: paulp
'''

import logging
import Engine

logger = logging.getLogger(__name__)

class Xengine(Engine.Engine):
    '''
    An X-engine, regardless of where it is located.
    '''
    def __init__(self, xengine_id):
        '''Constructor.
        '''
        Engine.Engine.__init__(self, engine_id=xengine_id)
        
        self.xeng_sample_bits = 32 # FROM DESIGN
        
        
        logger.info('New Xengine(%i) created.' % (xengine_id))

    def __str__(self):
        return 'xengine %i @ %s' % (self.id, self.host)
# end