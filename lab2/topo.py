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

# Class for an edge in the graph
class Edge:
	def __init__(self):
		self.lnode = None
		self.rnode = None
	
	def remove(self):
		self.lnode.edges.remove(self)
		self.rnode.edges.remove(self)
		self.lnode = None
		self.rnode = None

# Class for a node in the graph
class Node:
	def __init__(self, id, type):
		self.edges = []
		self.id = id
		self.type = type

	# Add an edge connected to another node
	def add_edge(self, node):
		edge = Edge()
		edge.lnode = self
		edge.rnode = node
		self.edges.append(edge)
		node.edges.append(edge)
		return edge

	# Remove an edge from the node
	def remove_edge(self, edge):
		self.edges.remove(edge)

	# Decide if another node is a neighbor
	def is_neighbor(self, node):
		for edge in self.edges:
			if edge.lnode == node or edge.rnode == node:
				return True
		return False


class Fattree:

	def __init__(self, num_ports):
		self.servers = [] # list of Node(type='host')
		self.switches = []  # list of Node(type in {'core','agg','edge'})
		self.generate(num_ports) 

	def generate(self, num_ports):
		pods = k = num_ports
		half = k // 2
        
		# 1) create core switches: arranged in half x half matrix
		core_switches = []
		for i in range(half):
			for j in range(half):
				nid = f"c{i}{j}"        # e.g. c00, c01, c10, c11 for k=4
				node = Node(nid, 'core')
				core_switches.append(node)
				self.switches.append(node)

        # 2) build each pod
		for p in range(pods):
            # aggregation and edge in this pod
			agg_switches = []
			edge_switches = []
			for i in range(half):
				a = Node(f"a{p}{i}", 'agg')    # e.g. a00, a01 in pod 0
				e = Node(f"e{p}{i}", 'edge')   # e00, e01 in pod 0
				agg_switches.append(a)
				edge_switches.append(e)
				self.switches += [a, e]

            # 2a) connect each edge to each agg in same pod
			for e in edge_switches:
				for a in agg_switches:
					e.add_edge(a)

            # 2b) attach hosts to each edge switch
            # each edge has half hosts
			for ei, e in enumerate(edge_switches):
				for h in range(half):
					hid = f"h{p}{ei}{h}"   # e.g. h000, h001, h010, h011 for k=4
					host = Node(hid, 'host')
                    # store addressing info for later IP assignment
					host.pod = p
					host.edge = ei
					host.idx = h
					self.servers.append(host)
					e.add_edge(host)

            # 2c) connect agg switches to core
            # each agg i connects to one group of core with index i
			for ai, a in enumerate(agg_switches):
                # group offset = ai * half
				for cj in range(half):
					core_idx = ai * half + cj
					a.add_edge(core_switches[core_idx])

