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

import os
import subprocess
import time

import mininet
import mininet.clean
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import lg, info
from mininet.link import TCLink
from mininet.node import Node, OVSKernelSwitch, RemoteController
from mininet.topo import Topo
from mininet.util import waitListening, custom

from topo import Fattree


class FattreeNet(Topo):
    """
    Create a fat-tree network in Mininet
    """

    def __init__(self, ft_topo):

        Topo.__init__(self)

        # TODO: please complete the network generation logic here
        # 1) add all switches
        count_switches = 0
        for sw in ft_topo.switches:
            # switch names must be alphanumeric only
            hex_dpid = '%016x' % int(sw.id.replace('a','1').replace('e','2').replace('c','3'))  # simple mapper
            self.addSwitch(sw.id, dpid=hex_dpid)
            count_switches+=1
        info(f"Total {count_switches} Switches added\n")

        # 2) add all hosts with their IPs
        count_host = 0
        for h in ft_topo.servers:
            # IP: 10.pod.edge.idx/8
            ip = f"10.{h.pod}.{h.edge}.{h.idx+2}/8"
            # info(f"Host with ip: {ip} Added")
            self.addHost(h.id, ip=ip)
            count_host+=1
        info(f"Total {count_host} Hosts added\n")

        # 3) add links for every edge in the graph
        #    use TCLink with 15 Mbps, 5 ms delay
        seen = set()
        count_edge = 0
        for sw in ft_topo.switches:
            for edge in sw.edges:
                n1 = edge.lnode
                n2 = edge.rnode
                # build a unique key to avoid duplicate links
                key = tuple(sorted([n1.id, n2.id]))
                if key in seen:
                    continue
                seen.add(key)

                # all links get same bw/delay
                self.addLink(n1.id, n2.id,
                             cls=TCLink,
                             bw=15,
                             delay='5ms')
                count_edge+=1



def make_mininet_instance(graph_topo):

    net_topo = FattreeNet(graph_topo)
    net = Mininet(topo=net_topo, controller=None, autoSetMacs=True)
    net.addController('c0', controller=RemoteController,
                      ip="127.0.0.1", port=6653)
    return net


def run(graph_topo):

    # Run the Mininet CLI with a given topology
    lg.setLogLevel('info')
    mininet.clean.cleanup()
    net = make_mininet_instance(graph_topo)

    info('*** Starting network ***\n')
    net.start()
    info('*** Running CLI ***\n')
    CLI(net)
    info('*** Stopping network ***\n')
    net.stop()


if __name__ == '__main__':
    ft_topo = Fattree(4)
    run(ft_topo)
