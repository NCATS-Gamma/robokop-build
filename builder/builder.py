from WorldGraph import WorldGraph
import networkx as nx
from networkx.readwrite.json_graph.node_link import node_link_data
import json
import logging

class Operation():
    def __init__(self, layer0, layer1):
        self.subject_layer = layer0
        self.object_layer = layer1
        self.completed = False

def is_valid_layer_type(lt):
    """Defines the allowed set of layer types"""
    return lt in ('S','G','P','A','PH','D','GC')

#TODO: Need to sort out the representation of nodes/edges more carefullly.  
class KnowledgeGraph:
    def __init__(self, querystring, wg):
        """Convert a string defining a path query into a sequence of Query objects.

        A query string is defined as a - delimited list of node types defined as:
        S: Substance, Compound, Drug
        G: Gene, Target
        P: Pathway
        A: Anatomy, Cell Type, Tissue
        PH: Phenotype
        D: Disease
        GC: Genetic Condition (subclass of Disease)

        Nodes can also define a particular object.  Parentheses denote that this
        will be a specific object.  Inside the parentheses, the object is
        given as Type;Curie, so that a particular disease with DOID of 1470 is
        defined as:
        (D;DOID:1470)

        A valid query must have a fixed node at the beginning, and it may have a 
        fixed node at the end.  These restrictions may be relaxed in the future.

        Given a such a path, the results from the previous query become the
        input to the subsequent query.
        """
        self.logger = logging.getLogger('application')
        self.graph = nx.MultiDiGraph()
        self.worldgraph = wg
        layer_def_list = querystring.split('-')
        self.layer_types = []
        for layer_num, layer_def in enumerate(layer_def_list):
            if layer_num == 0:
                #TODO: should be smarter, handle errors
                layer_type, layer_example = layer_def[1:-1].split(';')
            #TODO: need to handle fixed endpoint
            else:
                layer_type = layer_def
                layer_example = None
            if not is_valid_layer_type(layer_type):
                raise Error(layer_type)
            self.layer_types.append(layer_type)
            if layer_example is not None:
                self.add_node(layer_example, layer_type, layer_num)
        self.operations = []
        #This is going to be a sequential set of operations. Right
        # now, it's a bit dumb, but later it may be useful to define.
        for i in range(len(self.layer_types)-1):
            self.operations.append( Operation( i, i+1 ) )
        #In the future, we might want to check and amke sure that
        # we have certain node types, but not now
        #validate_operations()
    def add_node(self,node_id,node_type,layer_number,node_properties={}):
        """Add an unattached node to a particular query layer"""
        #TODO: what if the node already exists?
        self.graph.add_node(node_id, \
                node_type = node_type, \
                layer = layer_number, \
                **node_properties)
    def execute(self):
        """Execute the query that defines the graph"""
        self.logger.debug('Executing Query')
        for op in self.operations:
            self.logger.debug('Creating layer: %d' % op.object_layer)
            subjects = self.get_nodes(op.subject_layer)
            if len(subjects) == 0:
                #TODO: Clean
                raise(Exception("no subject"))
            for subject in subjects:
                object_type = self.layer_types[ op.object_layer ]
                relationships,success = \
                        self.worldgraph.query( subject, object_type )
                #keep track of success == False which indicates missing queries
                #if not success:
                #    complain, and work around hole.
                self.add_relationships( subject, relationships, object_type, op.object_layer )
        self.logger.debug('Query Complete')
    def get_nodes(self, layer_number):
        """Returns the nodes in the given layer of the graph"""
        nodes = list(filter(lambda x: x[1]['layer'] == layer_number, \
                self.graph.nodes(data=True)) )
        return nodes
    def add_relationships( self, subject, relations, object_type, object_layer ):
        """Add new relationships and nodes to the graph"""
        for relation, obj in relations:
            #Here obj is a tuple like ('hgnc:123', {})
            object_id = obj[0]
            self.add_node( object_id, object_type, object_layer, obj[1] )
            #We expect relation to be a dict, passing it in as **relation means that the dict
            # will be interpreted as keyword arguments.  That will allow the keys/values to be attributes
            # of the edge.
            self.graph.add_edge( subject[0], object_id , etype='queried', **relation)
    def prune(self):
        """Backwards prune.
        This is probably overkill - we might want to allow hops over missing nodes, etc
        but for now it reduces the number of supports that we want to try to build"""
        self.logger.debug('Pruning Graph')
        nlayers = len(self.layer_types)
        #Don't remove terminal nodes, but back up one and remove
        #Don't remove query node either
        n_pruned = 0
        for level in range( nlayers -2, 0, -1):
            nodes = self.get_nodes(level)
            for node in nodes:
                if self.graph.out_degree(node[0]) == 0:
                    n_pruned += 1
                    self.graph.remove_node(node[0])
        self.logger.debug('Pruned %d nodes.' % n_pruned)
    def support(self):
        """Look for extra information connecting nodes."""
        #TODO: how do we want to handle support edges
        # Questions: Are they new edges even if we have an edge already, or do we integrate
        #            Do we look for edges within a layer, e.g. to identify similar concepts
        #               That's a good idea, but might be a separate query?
        #            Do we only check for connections along a path?  That would help keep paths
        #               distinguishable, but we lose similarity stuff.
        #            Do we want to use knowledge to connect within (or across) layers.
        #               e.g. look for related diseases in  a disease layer.
        # Prototype version looks at each paths connecting ends, and tries to look for any more edges
        #  in each path. I think this is probably too constraining... but is more efficient
        #
        # Generate paths, (unique) edges along paths
        self.logger.debug('Building Support')
        start_nodes = self.get_nodes(0)
        end_nodes = self.get_nodes( len(self.layer_types) - 1 )
        links_to_check = set()
        for start_node in start_nodes:
            for end_node in end_nodes:
                for path in nx.all_shortest_paths(self.graph,source=start_node[0],target=end_node[0]):
                    for n_i,source in enumerate(path):
                        for n_j in range(n_i + 1, len(path) ):
                            link=( source, path[n_j] )
                            links_to_check.add(link)
        # Check each edge, add any support found.
        n_supported = 0
        for source,target in links_to_check:
            data_source, support = self.worldgraph.support_query(source,target)
            if len(support) > 0:
                n_supported += 1
                self.graph.add_edge( source, target, etype='support', data_source= data_source, support = support )
        self.logger.debug('Support Completed.  Added %d edges' % n_supported)
    def write(self,root=None,level=-1):
        """Write the graph as a tree to stdout"""
        #TODO: add other output stream
        if root is None:
            [root] = self.get_nodes(0)
            self.write(root[0], 0)
        else:
            lprefix = []
            for n in range(level):
                lprefix += [' ']
            prefix = ''.join(lprefix)
            print( '%s%s' % (prefix, root ) )
            children = self.graph.successors(root)
            for child in children:
                self.write(child,level+1)
    def export(self, output_path, fmt='json'):
        """Export in a format that can be read by other tools.

        JSON is probably the most straightforward/accurate and it can be reloaded into 
             a networkx format using node_link_graph.
        GraphML is an XML based method of writing graphs.  The only reason for exporting it
            is so that cytoscape can read it for visualization.  If we have a smarter vis
            then this should be removed.  The real problem with GraphML is that it can't handle
            json arrays in the properties, so we have to escape them."""
        if fmt == 'json':
            js = node_link_data( self.graph )
            with open(output_path,'w') as outf:
                json.dump(js, outf, indent=4)
        elif fmt == 'graphml':
            #GraphML can't handle structure, so try to escape attributes to write stuff quickndirty
            export_graph = self.graph.copy()
            for node in export_graph.nodes(data=True):
                for key in node[1]:
                    node[1][key] = str(node[1][key])
            for edge in export_graph.edges(data=True):
                for key in edge[2]:
                    edge[2][key] = str(edge[2][key])
            nx.write_graphml(export_graph, output_path)
        else:
            #warn
            pass
        
def main():
    logger = logging.getLogger('application')
    logger.setLevel(level = logging.DEBUG)
    worldgraph = WorldGraph('config.std')
    #doid = 4325  #ebola
    #doid = 1470  #major depressive disorder
    #doid = 11476 #osteoporosis
    #doid = 12365  #malaria
    #doid = 10573 #osteomalacia
    #doid = 9270  #alkaptonuria
    doid = 526   #HIV
    #doid = 1498  #cholera
    #doid = 13810 #Hypercholesterolemia
    #doid = 9352  #Diabetes Mellitus, Type 2
    #doid = 2841  #Asthma
    #doid = 4989  #Chronic Pancreatitis(?)
    #doid = 10652 #Alzheimer Disease
    #doid = 5844  #Myocardial Infarction
    #doid = 11723 #Duchenne Muscular Dystrophy
    #doid = 14504 #Niemann Pick Type C
    #doid = 12858 #Huntington Disease
    #doid = 10923 #Sickle Cell Disease
    #doid = 2055  #Post-Truamatic Stress Disorder
    #doid = 0060728 #Deficiency of N-glycanase 1
    #doid = 0050741 #Alcohol Dependence
    kgraph = KnowledgeGraph('(D;DOID:%d)-G-GC' % doid, worldgraph)
    kgraph.execute()
    kgraph.prune()
    kgraph.support()
    kgraph.export('examples/example.%d.graphml' % doid, 'graphml')
    kgraph.export('examples/example.%d.json' % doid, 'json')
    kgraph.write()

if __name__ == '__main__':
    main()
