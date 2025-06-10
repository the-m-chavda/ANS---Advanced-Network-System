"""
 Copyright (c) 2025 Computer Networks Group @ UPB

 Permission is hereby granted, free of charge, to any person obtaining a copy of
 this software and associated documentation files (the "Software"), to deal in
 the Software without restriction, including without limitation the rights to
 use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 the Software, and to permit persons to whom the Software is furnished to do so,
 subject to the following conditions:

 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 """

#!/usr/bin/env python3

from ryu.base import app_manager
from ryu.controller import mac_to_port
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import packet, ethernet, arp, ipv4

from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
from ryu.app.wsgi import ControllerBase

import topo
import heapq
import os
import logging

# Configure logging to file
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, "sp_routing.log")

logger = logging.getLogger("ryu.app.sp_routing")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(log_file)
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

class SPRouter(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SPRouter, self).__init__(*args, **kwargs)
        
        # Initialize the topology with #ports=4
        self.topo_net = topo.Fattree(4)  # Initialize fat-tree
        self.graph = {}                  # Graph: dpid -> {neighbor: out_port}
        self.ip_location = {}            # dpid -> {mac -> port}
        self.mac_location = {}           # mac -> (dpid, port)
        # self.discovery_started = False


    # ================= TOPOLOGY DISCOVERY =================
    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):

        switch_list = get_switch(self, None)
        self.graph.clear()

        # logger.info(f"switch_list: {switch_list}")
        for sw in switch_list:
            # logger.info(f"sw: {sw}")
            self.graph[sw.dp.id] = {}

        link_list = get_link(self, None)
        # logger.info(f"link_list: {link_list}")
        for link in link_list:
            # logger.info(f"Link: src={link.src.dpid} (port {link.src.port_no}) -> dst={link.dst.dpid} (port {link.dst.port_no})")
            src = link.src.dpid
            dst = link.dst.dpid
            out_port = link.src.port_no
            self.graph[src][dst] = out_port
        logger.info("graph built: %s", self.graph)

    # @set_ev_cls(event.EventLinkAdd)
    # def _link_add_handler(self, ev):
    #     self.logger.info("Link detected: rebuilding topology...")
    #     self.build_topology_graph()
    
    # def build_topology_graph(self):
    #     self.graph.clear()
    #     switch_list = get_switch(self, None)
    #     for sw in switch_list:
    #         # logger.info(f"sw: {sw}")
    #         self.graph[sw.dp.id] = {}

    #     link_list = get_link(self, None)
    #     for link in link_list:
    #         # logger.info(f"link: {link}")
    #         src = link.src.dpid
    #         dst = link.dst.dpid
    #         out_port = link.src.port_no
    #         self.graph[src][dst] = out_port
    #     logger.info(f"TOPOLOGY Graph: {self.graph}")

    # ================= FLOW TABLE INIT =================
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        # Delay LLDP/startup discovery
        # if not self.discovery_started:
        #     hub.spawn_after(10, self.start_discovery)  # 5 second delay
        #     self.discovery_started = True
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # ports = datapath.ports
        # logger.info(f"default flow rule added {ports}")

        # port_numbers = list(datapath.ports.keys())
        # logger.info(f"Ports on switch {datapath.id}: {port_numbers}")


        # for port_no, port in ports.items():
        #     logger.info(f"Switch {datapath.id} has port {port_no} with MAC {port.hw_addr}")

        # Install Default flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        logger.info(f"Switch connected: DPID = {datapath.id}")


    # Add a flow entry to the flow-table
    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Construct flow_mod message and send it
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)


    # ================== DIJKSTRA ALGORITHM ==================
    def dijkstra(self, start, target):
        logger.info(f"start: {start} target: {target}")
        dist = {node: float('inf') for node in self.graph}
        prev = {node: None for node in self.graph}
        dist[start] = 0
        heap = [(0, start)]

        while heap:
            cur_dist, u = heapq.heappop(heap)
            if u == target:
                break
            for v in self.graph[u]:
                alt = cur_dist + 1
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(heap, (alt, v))

        path = []
        u = target
        while u is not None:
            path.insert(0, u)
            u = prev[u]
        logger.info(f"path:{path}")
        return path if path[0] == start else []

    # ================== PACKET HANDLER ==================
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        # logger.info(f"dpid: {dpid}")
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        # Ignore LLDP
        if eth.ethertype == 0x88cc:
            return
        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if not arp_pkt and not ip_pkt:
            return
        elif arp_pkt:
            src_ip = arp_pkt.src_ip
            dst_ip = arp_pkt.dst_ip
        else:
            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst

        logger.info(f"dpid: {dpid} src_ip: {src_ip} dst_ip:{dst_ip}")

        # Learn location
        is_src_edge = self.ip_to_edge_dpid(src_ip)
        if dpid == is_src_edge:
            self.ip_location[src_ip] = (dpid, in_port)

        # Handle ARP or IP similar
        if arp_pkt or ip_pkt:
            dst_edge_dpid = self.ip_to_edge_dpid(dst_ip)
            if dpid == dst_edge_dpid:
                if dst_ip in self.ip_location:
                    _, out_port = self.ip_location[dst_ip]
                    broadcast_ports = {out_port}
                    logger.info(f"broadcast_ports if- {broadcast_ports}")
                else:
                    broadcast_ports = self.get_host_ports(datapath, self.graph) - {in_port}
                    logger.info(f"broadcast_ports else- {broadcast_ports}") 

                actions = []
                for port in broadcast_ports:
                    if port != in_port:  # avoid sending back to uplink
                        actions.append(parser.OFPActionOutput(port))

                if actions:
                    out = parser.OFPPacketOut(
                        datapath=datapath,
                        buffer_id=msg.buffer_id,
                        in_port=in_port,
                        actions=actions,
                        data=msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
                    )
                    logger.info(f"Broadcast to end hosts - dpid: {dpid} src_ip: {src_ip} dst_ip: {dst_ip} host_ports: {broadcast_ports}")
                    logger.info(f"Graph: {self.graph}")
                    logger.info(f"ip_location - {self.ip_location}")
                    if dst_ip in self.ip_location:
                        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(dst_ip))
                        self.add_flow(datapath, 10, match, actions)
                    datapath.send_msg(out)
                    return

            # Only handle ARP if we can determine the destination switch
            if dst_edge_dpid is not None and dst_edge_dpid in self.graph:
                path = self.dijkstra(dpid, dst_edge_dpid)
                logger.info("pkt path %s → %s: %s", dpid, dst_edge_dpid, path)

                if len(path) >= 2:
                    next_hop = path[1]
                    out_port = self.graph[dpid][next_hop]
                    match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(dst_ip, "255.255.255.0"))
                    actions = [parser.OFPActionOutput(out_port)]
                    self.add_flow(datapath, 10, match, actions)
                    out = parser.OFPPacketOut(
                        datapath=datapath,
                        buffer_id=msg.buffer_id,
                        in_port=in_port,
                        actions=actions,
                        data=msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
                    )
                    logger.info(f"Forwarded - dpid: {dpid} src_ip: {src_ip} dst_ip: {dst_ip} out_port: {out_port}")
                    logger.info(f"Graph: {self.graph}")
                    datapath.send_msg(out)
                    return

    def ip_to_edge_dpid(self, ip_str):
        # Example IP: 10.pod.switch.host
        try:
            parts = list(map(int, ip_str.split('.')))
            pod = parts[1]
            edge = parts[2]
            return int(f"2{pod}{edge}")  # matches our dpid scheme for edge switches
        except:
            return None
        
    def get_host_ports(self, datapath, graph):
        """
        Returns a set of port numbers on the given datapath (switch)
        that are not connected to other switches — i.e., likely host-facing.

        Args:
            datapath: The Ryu datapath object for the switch.
            graph: Your {dpid: {neighbor_dpid: port_no}} topology map.

        Returns:
            A set of port numbers that are likely connected to hosts.
        """
        dpid = datapath.id

        # What is OFPP_LOCAL?
        # It represents the switch’s local interface (used for management, not data plane).
        # It's automatically included in the datapath.ports dictionary.
        # It is not an actual physical port you use for packet forwarding.

        all_ports = {p for p in datapath.ports.keys() if p < ofproto_v1_3.OFPP_MAX}
        # logger.info(f"swithc {dpid} - {all_ports}")

        # Get all inter-switch port numbers from the graph
        inter_switch_ports = set(graph.get(dpid, {}).values())

        # Host-facing ports = all - inter-switch
        host_ports = all_ports - inter_switch_ports
        return host_ports

    # can't use below method as we required to forward pkt uplink but usefull knowledge
    def disable_flooding_on_port(self, datapath, port_no, hw_addr):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Set the NO_FLOOD flag for this port
        mod = parser.OFPPortMod(
            datapath=datapath,
            port_no=port_no,
            hw_addr=hw_addr,
            config=ofproto.OFPPC_NO_FLOOD,
            mask=ofproto.OFPPC_NO_FLOOD,
            advertise=0
        )
        datapath.send_msg(mod)

