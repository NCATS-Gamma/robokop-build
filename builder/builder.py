from WorldGraph import WorldGraph
from graph_components import KNode,KEdge,elements_to_json
import networkx as nx
from networkx.readwrite.json_graph.node_link import node_link_data
import json
import logging
import sys

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
        for layer_number, layer_def in enumerate(layer_def_list):
            if layer_number == 0:
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
                root = KNode(layer_example, layer_type)
                self.add_node(root, layer_number)
        self.operations = []
        #This is going to be a sequential set of operations. Right
        # now, it's a bit dumb, but later it may be useful to define.
        for i in range(len(self.layer_types)-1):
            self.operations.append( Operation( i, i+1 ) )
        #In the future, we might want to check and amke sure that
        # we have certain node types, but not now
        #validate_operations()
    def add_node(self,node,layer_number):
        """Add an unattached node to a particular query layer.
        
        If the node already exists, we don't want to add it, we just
        return the node that was in the graph already.  If it isn't then
        we add it and return newly added node"""
        #TODO: what if the node already exists?
        previous = list(filter(lambda x: x.identifier == node.identifier, \
                self.graph.nodes()) )
        if len(previous) == 1:
            if previous[0].layer_number == layer_number:
                return previous[0]
        node.layer_number = layer_number
        self.graph.add_node(node)
        return node
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
        nodes = list(filter(lambda x: x.layer_number == layer_number, \
                self.graph.nodes()) )
        return nodes
    def add_relationships( self, subject, relations, object_type, object_layer ):
        """Add new relationships and nodes to the graph"""
        for relation, object_node in relations:
            # The thing we want to add might already exist in the
            # graph.  Whatever we get back is the right thing to use.
            object_node = self.add_node( object_node, object_layer )
            self.graph.add_edge( subject, object_node, object = relation )
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
                if self.graph.out_degree(node) == 0:
                    n_pruned += 1
                    self.graph.remove_node(node)
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
                for path in nx.all_shortest_paths(self.graph,source=start_node,target=end_node):
                    for n_i,source in enumerate(path):
                        for n_j in range(n_i + 1, len(path) ):
                            link=( source, path[n_j] )
                            links_to_check.add(link)
        # Check each edge, add any support found.
        n_supported = 0
        for source,target in links_to_check:
            support_edge = self.worldgraph.support_query(source,target)
            if support_edge is not None:
                n_supported += 1
                self.graph.add_edge( source , target, object = support_edge )
        self.logger.debug('Support Completed.  Added %d edges' % n_supported)
    def write(self,root=None,level=-1,output_stream = sys.stdout):
        """Write the graph as a tree to stdout"""
        #TODO: add other output stream
        if root is None:
            [root] = self.get_nodes(0)
            self.write(root, 0, output_stream)
        else:
            lprefix = []
            for n in range(level):
                lprefix += [' ']
            prefix = ''.join(lprefix)
            output_stream.write( '%s%s\n' % (prefix, root.get_shortname() ) )
            children = self.graph.successors(root)
            for child in children:
                self.write(child,level+1, output_stream)
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
                json.dump(js, outf, indent=4, default=elements_to_json)
        elif fmt == 'graphml':
            #GraphML can't handle structure.  The goal here is just to make some simple visualizations
            # so it won't be a full representation.
            #TODO:  But maybe we can do json.dumps on the values?
            export_graph = nx.MultiDiGraph()
            name_remap = {}
            for node in self.graph.nodes():
                node_id, node_props = node.get_exportable()
                export_graph.add_node(node_id, **node_props)
                name_remap[node]=node_id
            for edge in self.graph.edges(data=True):
                exportable_edge_props = edge[2]['object'].get_exportable()
                export_graph.add_edge( name_remap[edge[0]], name_remap[edge[1]], **exportable_edge_props)
            nx.write_graphml(export_graph, output_path)
        else:
            self.logger.error('Invalid export format: %s' % fmt)

def run_query(query, output_path, worldgraph):
    """Given a query, create a knowledge graph though querying external data sources.  Export the graph"""
    kgraph = KnowledgeGraph(query, worldgraph)
    kgraph.execute()
    kgraph.prune()
    kgraph.support()
    kgraph.export('%s.graphml' % output_path, 'graphml')
    kgraph.export('%s.json' % output_path, 'json')
    #Write to both file and stdout
    with open('%s.txt' % output_path, 'w') as output_stream:
        kgraph.write(output_stream = output_stream)
    kgraph.write()
       
def main_test():
    """Run a series of test cases from the NCATS FOA"""
    logger = logging.getLogger('application')
    logger.setLevel(level = logging.DEBUG)
    worldgraph = WorldGraph('config.std')
    #Our test cases are defined as a doid and a name.  The name is from the NCATS FOA. The DOID
    # was looked up by hand.
    test_cases = ( \
                  ('4325',  'ebola'), \
                  ('1470'  ,'major depressive disorder'), \
                  ('11476' ,'osteoporosis'), \
                  ('12365' ,'malaria'), \
                  ('10573' ,'osteomalacia'), \
                  ('9270'  ,'alkaptonuria'), \
                  ('526'   ,'HIV'), \
                  ('1498'  ,'cholera'), \
                  ('13810' ,'Hypercholesterolemia'), \
                  ('9352'  ,'Diabetes Mellitus, Type 2'), \
                  ('2841'  ,'Asthma'), \
                  ('4989'  ,'Chronic Pancreatitis(?)'), \
                  ('10652' ,'Alzheimer Disease'), \
                  ('5844'  ,'Myocardial Infarction'), \
                  ('11723' ,'Duchenne Muscular Dystrophy'), \
                  ('14504' ,'Niemann Pick Type C'), \
                  ('12858' ,'Huntington Disease'), \
                  ('10923' ,'Sickle Cell Disease'), \
                  ('2055'  ,'Post-Truamatic Stress Disorder'), \
                  ('0060728' ,'Deficiency of N-glycanase 1'), \
                  ('0050741' ,'Alcohol Dependence') )
    for doid, disease_name in test_cases:
        print('Running test case: %s (DOID:%s)' % (disease_name,doid) )
        query = '(D;DOID:%s)-G-GC' % doid
        output = 'examples/example.%s' % doid
        run_query(query, output, worldgraph)

if __name__ == '__main__':
    main_test()
