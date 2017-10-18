import pharos as ph
import biolink as biol
import chemotext as ct
import logging
from collections import defaultdict
from greent.rosetta import Rosetta
from greent.rosetta import Translation

logger = logging.getLogger ("application")

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
        """Check sources to find links between two specific nodes, for the purpose of support."""
        # Right now, this is hitting chemotext to look for articles.  Want to do some similar routing, I think.
        return ct.term_to_term(subject_node, object_node)


class WorldGraphFactory:
    @staticmethod
    def create (config, worldgraph_type='default'):
        return {
            'default' : WorldGraph,
            'greent'  : GreenWorldGraph
        }[worldgraph_type](config)

class GreenWorldGraph(WorldGraph):
    def __init__(self, configFile):
        super(GreenWorldGraph, self).__init__(configFile)
        self.translator = Rosetta (greentConf=configFile)
        self.type_to_greent_map = {
            "S"  : [ "c2b2r_drug_id" ],
            "G"  : [ "c2b2r_gene", "hgnc_id" ],
            "P"  : [ "c2b2r_pathway" ],
            "A"  : [ "hetio_cell" ], # anatomy, tissue
            "PH" : [ ],
            "D"  : [ "mesh_disease_id", "mesh_disease_name", "pharos_disease_id", "doid" ],
            "GC" : [ "genetic_condition" ]
        }
    def query(self, subject_node, object_type):
        result = []
        greent_node_types = self.type2greent (subject_node.node_type)
        greent_object_types = self.type2greent (object_type)
        for L in greent_node_types:
            for R in greent_object_types:
                translation = Translation (obj=subject_node, type_a=L, type_b=R)
                logger.debug ("        translation: %s" % translation)
                data = self.translator.translate (thing=translation.obj,
                                                  source=translation.type_a,
                                                  target=translation.type_b)
                result += data if isinstance(data,list) else []
            #print ("------> result: {}".format (result))
        return result, len(result) > 0
    def support_query(self, subject_node, object_node):
        pass

    # ---
    def type2greent0 (self, input_type):
        result = None
        intermediate = self.type_to_greent_map[input_type] \
                       if input_type in self.type_to_greent_map else None
        print ("inermediate {}".format (intermediate))
        if intermediate:
            result = self.greent.translator.mox_resolve[intermediate](None).obj_type \
                     if intermediate in self.greent.translator.mox_resolve else None
            
        print ("-- {}".format (result))
        return result

    def type2greent (self, input_type):
        return self.type_to_greent_map[input_type] \
            if input_type in self.type_to_greent_map else [ ]
