import json
import networkx as nx
from networkx.readwrite.json_graph.node_link import node_link_graph
import matplotlib.pyplot as plt

with open('builder/example1') as inf:
    js = json.load(inf)

graph = node_link_graph(js)

#nx.draw_spring(graph)
#plt.show()
for node in list(graph.nodes()):
    print(node, graph[node])
    #print(graph[node].keys())
