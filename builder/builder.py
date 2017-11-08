from reasoner.graph_components import KNode,KEdge,elements_to_json
from reasoner import node_types 
from greent.rosetta import Rosetta
import chemotext
import userquery
import argparse
import networkx as nx
from networkx.readwrite.json_graph.node_link import node_link_data
import logging
import sys
from neo4j.v1 import GraphDatabase
from collections import OrderedDict

class KnowledgeGraph:
    def __init__(self, userquery, rosetta):
        """KnowledgeGraph is a local version of the query results. 
        After full processing, it gets pushed to neo4j.
        """
        self.logger = logging.getLogger('application')
        self.graph = nx.MultiDiGraph()
        self.userquery = userquery
        self.rosetta = rosetta
        #node_map is a map from identifiers to the node associated.  It's useful because
        # we are collapsing nodes along synonym edges, so each node might asked for in
        # multiple different ways.
        self.node_map = {}
        uri = 'bolt://localhost:7687'
        self.driver = GraphDatabase.driver(uri,encrypted=False)
    def execute(self):
        """Execute the query that defines the graph"""
        self.logger.debug('Executing Query')
        #GreenT wants a cypherquery to find transitions, and a starting point
        cypher = self.userquery.generate_cypher()
        #print(cypher)
        identifier, ntype = self.userquery.get_start_node()
        start_node = KNode( identifier, ntype )
        #Fire this to rosetta, collect the result
        result_graph = self.rosetta.graph([(None, start_node)],query=cypher)
        #result_graph contains duplicate edges.  Remove them, while preserving order:
        result_graph = list(OrderedDict.fromkeys( result_graph ) )
        self.add_edges( result_graph )
        self.logger.debug('Query Complete')
    def add_synonymous_edge(self, edge):
        source = self.find_node(edge.source_node)
        target = self.find_node(edge.target_node)
        if source is None and target is None:
            raise Exception('Synonym between two new terms')
        if source is not None and target is not None:
            raise Exception('synonym between two existing nodes not yet implemented')
        if target is not None:
            source, target = target, source
        source.add_synonym(edge.target_node)
        self.node_map[ edge.target_node.identifier ] = source
    def add_nonsynonymous_edge(self,edge):
        #Found an edge between nodes. Add nodes if needed.
        source_node = self.add_or_find_node(edge.source_node)
        target_node = self.add_or_find_node(edge.target_node)
        edge.source_node=source_node
        edge.target_node=target_node
        #Now the nodes are translated to the canonical identifiers, make the edge
        self.graph.add_edge(source_node, target_node, object=edge)
    def add_edges( self, edge_list ):
        """Add a list of edges (and the associated nodes) to the graph."""
        for edge in edge_list:
            if edge.is_synonym:
                self.add_synonymous_edge(edge)
            else:
                self.add_nonsynonymous_edge(edge)
    def find_node(self,node):
        """If node exists in graph, return it, otherwise, return None"""
        if node.identifier in self.node_map:
            return self.node_map[node.identifier]
        return None
    def add_or_find_node(self, node):
        """Find a node that already exists in the graph, checking for synonyms. If not found, create it & add to graph"""
        fnode = self.find_node(node)
        if fnode is not None:
            return fnode
        else:
            self.graph.add_node(node)
            self.node_map[node.identifier] = node
            return node
    def prune(self):
        """Recursively remove poorly connected nodes.  In particular, each (non-terminal) node must be connected to two different kinds of nodes."""
        #TODO, that is maybe a bit too much.  You can't have disease-gene-disease for instance !
        # But degree is not enough because you can have A and B both go to C but C doesn't go anywhere.
        # Probably need to interact with the query to decide whether this node is prunable or not.
        self.logger.debug('Pruning Graph')
        removed = True
        keep_types = self.userquery.get_terminal_types()
        n_pruned = 0
        while removed:
            removed = False
            to_remove = []
            for node in self.graph.nodes():
                if node.node_type in keep_types:
                    continue
                #Graph is directed.  graph.neighbors only returns successors 
                neighbors = self.graph.successors(node) + self.graph.predecessors(node)
                neighbor_types = set( [ neighbor.node_type for neighbor in neighbors ] )
                if len(neighbor_types) < 2 :
                    to_remove.append(node)
            for node in to_remove:
                removed=True
                n_pruned += 1
                self.graph.remove_node(node)
        self.logger.debug('Pruned {} nodes.'.format(n_pruned) )
    def get_terminal_nodes(self):
        """Return the nodes at the beginning or end of a query"""
        #TODO: Currently doing via type.  Probably need to mark these instead.
        start_type, end_type = self.userquery.get_terminal_types()
        start_nodes = []
        end_nodes = []
        nodes = self.graph.nodes()
        for node in nodes:
            if node.node_type == start_type:
                start_nodes.append( node )
            elif node.node_type == end_type:
                end_nodes.append( node )
        return start_nodes, end_nodes
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
        start_nodes, end_nodes = self.get_terminal_nodes()
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
            support_edge = chemotext.term_to_term(source,target, self.rosetta.core)
            if support_edge is not None:
                n_supported += 1
                self.logger.debug ('  -Adding support edge from {} to {}'.format(source.identifier, target.identifier) )
                self.add_nonsynonymous_edge( support_edge )
        self.logger.debug('Support Completed.  Added {} edges'.format( n_supported) )
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
    def export(self,resultname):
        """Export to neo4j database."""
        #TODO: lots of this should probably go in the KNode and KEdge objects?
        self.logger.info("Writing to neo4j with label {}".format(resultname))
        session = self.driver.session()
        #If we have this query already, overwrite it...
        session.run('MATCH (a:%s) DETACH DELETE a' % resultname)
        #Now add all the nodes
        for node in self.graph.nodes():
            #TODO: get a name correctly
            prepare_node_for_output(node,self.rosetta.core)
            #print( '----\n{} {}\n properties:{}\n synonyms:{}'.format(node.identifier, node.label, node.properties, node.synonyms))
            session.run("CREATE (a:%s {id: {id}, name: {name}, node_type: {node_type}, synonyms: {syn}, meta: {meta}})" % resultname, \
                    {"id": node.identifier, "name": node.label, "node_type": node.node_type, "syn": list(node.synonyms), "meta": ''})
        for edge in self.graph.edges(data=True):
            aid = edge[0].identifier
            bid = edge[1].identifier
            ke = edge[2]['object']
            if ke.is_support:
                label = 'Support'
            else:
                label = 'Result'
            prepare_edge_for_output(ke)
            #print( '----\nEdge {} {}\n properties:{}\n'.format(aid, bid, ke.properties))
            session.run("MATCH (a:%s), (b:%s) WHERE a.id={aid} AND b.id={bid} CREATE (a)-[r:%s {source: {source}, function: {function}, pmids: {pmids}, onto_relation_id: {ontoid}, onto_relation_label: {ontolabel}} ]->(b) return r" % \
                    (resultname,resultname, label),\
                    { "aid": aid, "bid": bid, "source": ke.edge_source, "function": ke.edge_function, "pmids": ke.pmidlist, "ontoid": ke.typed_relation_id, "ontolabel": ke.typed_relation_label } )
        session.close()

#TODO: push to node, ...
def prepare_node_for_output(node,gt):
    if 'mesh_identifiers' in node.properties:
        node.synonyms.update( [mi['curie'] for mi in node.properties['mesh_identifiers']] )
    if node.node_type == node_types.DISEASE or node.node_type == node_types.GENETIC_CONDITION:
        if 'mondo_identifiers' in node.properties:
            node.synonyms.update(node.properties['mondo_identifiers'])
        node.label = gt.mondo.get_label( node.identifier )
    elif node.node_type == node_types.DISEASE_NAME or node.node_type == node_types.DRUG_NAME:
        node.label = node.identifier.split(':')[-1]
    elif node.node_type == node_types.GENE and node.identifier.startswith('HGNC:'):
        node.label = gt.hgnc.get_name( node )
    else:
        node.label = node.identifier

#Push to edge...
def prepare_edge_for_output(edge):
    #We should settle on a format for PMIDs.  Do we always lookup / include e.g. title? Or does UI do that?
    pmidlist = []
    if 'publications' in edge.properties:
        for pub in edge.properties['publications']:
            #v. brittle. Should be put into the edge creation...
            if 'pmid' in pub:
                pmidlist.append('PMID:{}'.format(pub['pmid']))
            elif 'id' in pub:
                pmidlist.append(pub['id'])
        del edge.properties['publications']
    edge.pmidlist = pmidlist
    if 'relation' in edge.properties:
        edge.typed_relation_id = edge.properties['relation']['typeid']
        edge.typed_relation_label = edge.properties['relation']['label']
    else:
        edge.typed_relation_id = ''
        edge.typed_relation_label = ''


def run_query(query, result_name, output_path, prune=True):
    """Given a query, create a knowledge graph though querying external data sources.  Export the graph"""
    rosetta = Rosetta()
    kgraph = KnowledgeGraph( query, rosetta )
    kgraph.execute()
    if prune:
        kgraph.prune()
    #kgraph.support()
    kgraph.export(result_name)
    #This isn't working right now, leave out....
    #with open('%s.txt' % output_path, 'w') as output_stream:
    #    kgraph.write(output_stream = output_stream)
       
def main_test():
    parser = argparse.ArgumentParser(description='Protokop.')
    parser.add_argument('--data', help='Name of the data layer to use [default|greent]', default='default')
    args = parser.parse_args()
    print (args.data)
    
    """Run a series of test cases from the NCATS FOA"""
    logger = logging.getLogger('application')
    logger.setLevel(level = logging.DEBUG)

    #Our test cases are defined as a doid and a name.  The name is from the NCATS FOA. The DOID
    # was looked up by hand.
    '''test_cases = ( \
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
'''
    test_cases = ( ('0050741' ,'Alcohol Dependence') , )

    for doid, disease_name in test_cases:
        print('Running test case: %s (DOID:%s)' % (disease_name,doid) )
        query = '(D;DOID:%s)-G-GC' % doid
        #output = 'examples_gt/example.%s' % doid
        output = 'examples/example.%s' % doid
        run_query(query, output, worldgraph)

def question1(diseasename):
    query = userquery.OneSidedLinearUserQuery(diseasename,node_types.DISEASE_NAME)
    query.add_transition(node_types.DISEASE)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.GENETIC_CONDITION)
    run_query(query,'Query1_{}'.format('_'.join(diseasename.split())) , '.')
   
def question2a(drugname):
    query = userquery.OneSidedLinearUserQuery(drugname,node_types.DRUG_NAME)
    query.add_transition(node_types.DRUG)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.PROCESS)
    query.add_transition(node_types.CELL)
    query.add_transition(node_types.ANATOMY)
    print( query.generate_cypher())
    run_query(query,'Query2a_{}'.format('_'.join(drugname.split())) , '.', prune=True)

def question2b(diseasename):
    query = userquery.OneSidedLinearUserQuery(diseasename,node_types.DISEASE_NAME)
    query.add_transition(node_types.DISEASE)
    query.add_transition(node_types.PHENOTYPE)
    query.add_transition(node_types.ANATOMY)
    print( query.generate_cypher())
    run_query(query,'Query2b_{}'.format('_'.join(diseasename.split())) , '.', prune=True)

def test():
    #question1('Ebola Virus Infection')
    #question2a('imatinib')
    question2b('asthma')

if __name__ == '__main__':
    test()
