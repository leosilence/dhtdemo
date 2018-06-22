import SocketServer
import logging
from bencode import bdecode, bencode, BTFailure
import threading
from utils import random_trans_id, random_node_id, get_version

SELF_LAN_IP = "34.219.153.100"

logger = logging.getLogger("log")
logger.setLevel(logging.DEBUG)

class DHTRequestHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        logger.debug("Got packet from: %s:%d" % (self.client_address))
        if SELF_LAN_IP == self.client_address[0]:
            return

        req = self.request[0].strip()

        try:
            message = bdecode(req)
            msg_type = message["y"]
            logger.debug("This is DHT connection with msg_type: %s" % (msg_type))

            if msg_type == "r":
                self.handle_response(message)
            elif msg_type == "q":
                self.handle_query(message)
            elif msg_type == "e":
                self.handle_error(message)
            else:
                logger.error("Unknown rpc message type %r" % (msg_type))
        except BTFailure:
            logger.error("Fail to parse message %r" % (self.request[0].encode("hex")))
            pass

    def handle_response(self, message):
        logger.debug("in response")

        trans_id = message["t"]
        args = message["r"]
        node_id = args["id"]

        client_host, client_port = self.client_address
        logger.debug("Response message from %s:%d, t:%r, id:%r" % (client_host, client_port, trans_id.encode("hex"), node_id.encode("hex")))

        return

    def handle_query(self, message):
        logger.debug("in query")
        return

    def handle_error(self, message):
        logger.debug("in error")
        return

class DHTServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
    def __init__(self, host_address, handler_cls):

        self.host, self.port = host_address

        #__init__ is the constructor of the UDPServer
        SocketServer.UDPServer.__init__(self, host_address, handler_cls)
        #the mutex for multi_threading
        self.send_lock = threading.Lock()

    def _sendmessage(self, message, trans_id=None, ips=None, lock=None):
        """ Send and bencode constructed message to other node """
        message["v"] = get_version()
        if trans_id:
            message["t"] = trans_id
        #the communication message format of the DHT is the "bencode"
        encoded = bencode(message)

        if self.socket:
            if lock:
                with lock:
                    try:
                        self.socket.sendto(encoded, ips)
                    except:
                        logger.error('send udp error')
            else:
                try:
                    self.socket.sendto(encoded, ips)
                except:
                    logger.error('send udp error')        

    #find the node close
    def find_node(self, target_id, sender_id=None, nodeips=None, lock=None):
        """ Construct query find_node message """
        trans_id = random_trans_id()
        message = {
            "y": "q",
            "q": "find_node",
            "a": { 
                "id": sender_id,
                "target": target_id
            }
        }

        logger.debug("find_node msg to %s:%d, y:%s, q:%s, t: %r" % (
            self.host, 
            self.port, 
            message["y"], 
            message["q"], 
            trans_id.encode("hex")
        ))

        self._sendmessage(message, trans_id=trans_id, ips=nodeips, lock=lock)

if __name__ == "__main__":
    dhtSvr = DHTServer(('0.0.0.0', 9500), DHTRequestHandler)

    server_thread = threading.Thread(target=dhtSvr.serve_forever)
    server_thread.daemon = True

    server_thread.start()

    id = random_node_id()
    dhtSvr.find_node(target_id=id, sender_id=id, nodeips=('router.bittorrent.com', 6881))



