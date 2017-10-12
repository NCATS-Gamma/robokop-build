import pharos as ph
import biolink as biol
import chemotext as ct
from collections import defaultdict

class WorldGraph:
    """The WorldGrpah is an interface to the data sources."""
    def __init__(self, configfile):
        """Configure the list of data sources."""
        #TODO: Load a config file saying which goes where
        #self.router = { 'S':{}, 'G':{}, 'P':{}, 'A':{}, 'PH':{}, 'D':{}, 'GC':{}}
        self.router = defaultdict( lambda: defaultdict(list) )
        self.router['D']['G'].append(ph.disease_get_gene)
        self.router['G']['GC'].append(biol.gene_get_genetic_condition)
    def query(self, subject_node, object_type ):
        """Given a subject KNode and an object type, return data from the sources. 
        
        Returns: list of (edge,node) tuples 
                 boolean indicator of whether a query function was found
                 
        Nodes are defined as a tuple of two elements.  The first element is the id 
        of the node (usually a curie).  The second element is a dict of node
        properties.
        
        Edges are defined as a dict with two keys.  The "edge_source" key retrieves
        a value such as pharos or biolink (later it may be the URI that produced
        the edge or something similar).  The "properties" key retrieves another
        dict with remaining edge properties.  These properties will be source dependent,
        though in the future we may want to harominze that."""
        subject_type=subject_node.node_type
        query_functions = self.router[subject_type][object_type]
        if len(query_functions) == 0:
            return [],False
        results = []
        for qf in query_functions:
            results += qf(subject_node)
        return results,True
    def support_query(self,subject_node,object_node):
        """Check sources to find links between two specific nodes, for the purpose of support.
        Right now, this is hitting chemotext to look for articles."""
        #TODO: check the nodes for mesh names, or pass whole node to chemotext and have it do that?
        return ct.term_to_term(subject_node, object_node)
