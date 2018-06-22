# -*- coding: utf-8 -*-

import logging
import threading

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

    def __repr__(self):
        #official string represent the the node
        return repr("%s %s:%d" % (self._id.encode('hex'), self.host, self.port))

    #修改该节点被访问的时间
    def update_access(self, unixtime=None):
        """ Update last access/modify time of this node """
        with self.lock:
            if unixtime:
                self.access_time = unixtime
            else:
                self.access_time = time.time()

    def getID(self):
        return self._id

    def getIP(self):
        return self.host

    def getPort(self):
        return self.port