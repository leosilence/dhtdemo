# -*- coding: utf-8 -*-

import sys
import SocketServer
import logging
import time
from node import Node
from bencode import bdecode, bencode, BTFailure
import threading
from utils import decode_nodes, random_trans_id, random_node_id, get_version
from rtable import RoutingTable

SELF_LAN_IP = "34.219.153.100"

#formatter = logging.Formatter("[%(levelname)s@%(created)s] %(message)s")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

stdout_handler = logging.StreamHandler()
stdout_handler.setFormatter(formatter)

logger = logging.getLogger("log")
logger.setLevel(logging.DEBUG)
logger.addHandler(stdout_handler)

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

        # Do we already know about this node?
        node = self.server.nodeTable.node_by_id(node_id)
        if not node:
            logger.debug("Cannot find appropriate node during simple search: %r" % (node_id.encode("hex")))
            #Trying to search via transaction id
            #get the node who sent the request, that correspondents to the response
            node = self.server.node_by_trans(trans_id)
            if not node:
                logger.debug("Cannot find appropriate node for transaction: %r" % (trans_id.encode("hex")))
                return

        logger.debug("We found apropriate node %r for %r" % (node, node_id.encode("hex")))

        if trans_id in self.server.trans:
            logger.debug("Found and deleting transaction %r in node: %r" % (trans_id.encode("hex"), node))
            #由于长时间没有响应的node会被自动删除,这里关系到多线程并发。所以可能会有bug
            #the server thread competes "node" resource with the iterative_thread
            try:
                trans = self.server.trans[trans_id]
                self.server.delete_trans(trans_id)
            except:
                logger.debug('delete trans on a deleted node')
                return
        else:
            logger.debug("Cannot find transaction %r in node: %r" % (trans_id.encode("hex"), node))
            return

        if "ip" in args:
            logger.debug("They try to SECURE me: %s", unpack_host(args["ip"].encode('hex')))

        #the server thread competes "node" resource with the iterative_thread
        try:
            t_name = trans["name"]
        except:
            logger.debug('get name on a deleted trans')
            return

        if t_name == "find_node":
            node.update_access()
            logger.debug("find_node response from %r" % (node))
            if "nodes" in args:
                new_nodes = decode_nodes(args["nodes"])
                logger.debug("We got new nodes from %r" % (node))
                for new_node_id, new_node_host, new_node_port in new_nodes:
                    logger.debug("Adding %r %s:%d as new node" % (new_node_id.encode("hex"), new_node_host, new_node_port))
                    self.server.nodeTable.update_node(new_node_id, Node(new_node_host, new_node_port, new_node_id))

            # cleanup boot node
            if node._id == "boot":
                logger.debug("This is response from \"boot\" node, replacing it")
                # Create new node instance and move transactions from boot node to newly node
                new_boot_node = Node(client_host, client_port, node_id)
                new_boot_node.trans = node.trans
                self.server.nodeTable.update_node(node_id, new_boot_node)
                # Remove old boot node
                self.server.nodeTable.remove_node(node._id)

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
        self.lock = threading.Lock()

        self.nodeTable = RoutingTable()

        self.trans = {}
        
    def getCurTransID(self):
        transid = random_trans_id()

        with self.lock:
            while transid in self.trans:
                transid = random_trans_id()

        return transid

    def add_trans(self, name, node, info_hash=None):
        """ Generate and add new transaction """
        trans_id = self.getCurTransID()
        with self.lock:
            self.trans[trans_id] = {
                    "name": name,
                    "node": node,
                    "info_hash": info_hash,
                    "access_time": int(time.time())
            }
        return trans_id

    def delete_trans(self, trans_id):
        """ Delete specified transaction """
        with self.lock:
            del self.trans[trans_id]            

    def node_by_trans(self, trans_id):
        """ Get appropriate node by transaction_id """
        with self.lock:
            if trans_id in self.trans:
                return self.trans[trans_id].node
        return None

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
    def find_node(self, target_id, toNode, sender_id=None, lock=None):
        """ Construct query find_node message """
        trans_id = self.add_trans("find_node", toNode)
        message = {
            "y": "q",
            "q": "find_node",
            "a": { 
                "id": sender_id,
                "target": target_id
            }
        }

        logger.debug("find_node msg to %s:%d, y:%s, q:%s, t: %r" % (
            toNode.host, 
            toNode.post,
            message["y"], 
            message["q"], 
            trans_id.encode("hex")
        ))

        self._sendmessage(message, trans_id=trans_id, ips=(toNode.host, toNode.port), lock=lock)

if __name__ == "__main__":
    dhtSvr = DHTServer(('0.0.0.0', 9500), DHTRequestHandler)

    server_thread = threading.Thread(target=dhtSvr.serve_forever)
    server_thread.daemon = True

    server_thread.start()

    id = random_node_id()

    boot_node = Node('router.bittorrent.com', 6881, "boot")
    while dhtSvr.nodeTable.count() <= 4:

        if len(dhtSvr.trans) > 5:
            logger.error("Too many attempts to bootstrap, seems boot node %s:%d is down. Givin up" % (dhtSvr.host, dhtSvr.port))
            break

        #去find自己，这样的作用是可以得到与自己邻近的节点
        #self.server.socket是UDP的socket

        dhtSvr.find_node(target_id=id, toNode=boot_node, sender_id=id)
        time.sleep(5)

    logger.debug("finish!")

    time.sleep(60*60*8)
