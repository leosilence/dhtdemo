import logging

logger = logging.getLogger("log")

class Node(object):
    """ Represent a DHT node """
    def __init__(self, host, port, _id):
        self._id = _id
        self.host = host
        self.port = port
        '''
        each node will create a lot of message. and each message had it's own trans. for each trans
        it will have the trans_id, message_type,hash_info,access_time
        '''
        self.trans = {}
        #the mutex of the node
        self.lock = threading.Lock()

        self.access_time = time.time()