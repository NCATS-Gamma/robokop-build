from greent.graph_components import KNode,KEdge,elements_to_json
from greent import node_types 
from greent.rosetta import Rosetta
import chemotext
from userquery import UserQuery
import mesh
import argparse
import networkx as nx
from networkx.readwrite.json_graph.node_link import node_link_data
import logging
import sys
from neo4j.v1 import GraphDatabase
from collections import OrderedDict
from importlib import import_module
from lookup_utils import lookup_disease_by_name, lookup_drug_by_name, lookup_phenotype_by_name
from collections import defaultdict

class KnowledgeGraph:
    def __init__(self, userquery, rosetta):
        """KnowledgeGraph is a local version of the query results. 
        After full processing, it gets pushed to neo4j.
        """
        self.logger = logging.getLogger('application')
        self.graph = nx.MultiDiGraph()
        self.userquery = userquery
        self.rosetta = rosetta
        if not self.userquery.compile_query( self.rosetta ):
            self.logger.error('Query fails. Exiting.')
            sys.exit(1)
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
        cyphers  = self.userquery.generate_cypher()
        starts   = self.userquery.get_start_node()
        reverses = self.userquery.get_reversed()
        lookups  = self.userquery.get_lookups()
        for cypher, start, reverse,lookup in zip(cyphers,starts,reverses,lookups):
            self.logger.debug(start)
            self.logger.debug('CYPHER')
            self.logger.debug(cypher)
            identifier, ntype = start
            start_node = KNode( identifier, ntype )
            kedge = KEdge( 'lookup', 'lookup' )
            kedge.source_node = lookup
            kedge.target_node = start_node
            self.add_nonsynonymous_edge( kedge )
            #Fire this to rosetta, collect the result
            result_graph = self.rosetta.graph([(None, start_node)],query=cypher)
            #result_graph contains duplicate edges.  Remove them, while preserving order:
            result_graph = list(OrderedDict.fromkeys( result_graph ) )
            self.add_edges( result_graph , reverse )
        self.logger.debug('Query Complete')
    def print_types(self):
        counts = defaultdict(int)
        for node in self.graph.nodes():
            counts[ node.node_type ] += 1
        for node_type in counts:
            self.logger.info('{}: {}'.format(node_type, counts[node_type]))
    def merge( self, source, target ):
        """Source and target are both members of the graph, and we've found that they are
        synonyms.  Remove target, and attach all of target's edges to source"""
        source.add_synonym( target )
        nodes_from_target = self.graph.successors(target)
        for s in nodes_from_target:
            #b/c this is a multidigraph, this is actually a map where the edges are the values
            self.logger.debug('Node s: {}'.format(s))
            kedgemap = self.graph.get_edge_data(target, s)
            if kedgemap is None:
                self.logger.error('s?')
            for i in kedgemap.values():
                kedge = i['object']
                #The node being removed is the source in these edges, replace it
                kedge.source_node = source
                self.graph.add_edge( source, s, object = kedge )
        nodes_to_target = self.graph.predecessors(target)
        for p in nodes_to_target:
            self.logger.debug('Node p: {}'.format(p))
            kedgemap = self.graph.get_edge_data(p, target)
            if kedgemap is None:
                self.logger.error('p?')
            for i in kedgemap.values():
                kedge = i['object']
                kedge.target_node = source
                self.graph.add_edge(p, source, object = kedge )
        self.graph.remove_node(target)
        #now, any synonym that was mapping to the old target should be remapped to source
        for k in self.node_map:
            if self.node_map[k] == target:
                self.node_map[k] = source
    def add_synonymous_edge(self, edge):
        self.logger.debug(' Synonymous')
        source = self.find_node(edge.source_node)
        target = self.find_node(edge.target_node)
        self.logger.debug('Source: {}'.format(source))
        self.logger.debug('Target: {}'.format(target))
        if source is None and target is None:
            raise Exception('Synonym between two new terms')
        if source is not None and target is not None:
            if source == target:
                self.logger.debug('Alredy merged')
                return
            self.merge( source, target )
            return
        if target is not None:
            source, target = target, source
        source.add_synonym(edge.target_node)
        self.node_map[ edge.target_node.identifier ] = source
    def add_nonsynonymous_edge(self,edge, reverse_edges = False):
        self.logger.debug(' New Nonsynonymous')
        #Found an edge between nodes. Add nodes if needed.
        source_node = self.add_or_find_node(edge.source_node)
        target_node = self.add_or_find_node(edge.target_node)
        edge.source_node=source_node
        edge.target_node=target_node
        #Now the nodes are translated to the canonical identifiers, make the edge
        if reverse_edges:
            edge.properties['reversed'] = True
            self.graph.add_edge(target_node, source_node, object=edge)
            self.logger.debug( 'Edge: {}'.format( self.graph.get_edge_data(target_node, source_node)))
        else:
            edge.properties['reversed'] = False
            self.graph.add_edge(source_node, target_node, object=edge)
            self.logger.debug( 'Edge: {}'.format( self.graph.get_edge_data(source_node, target_node)))
    def add_edges( self, edge_list , reverse_edges):
        """Add a list of edges (and the associated nodes) to the graph."""
        for edge in edge_list:
            self.logger.debug( 'Edge: {} -> {}'.format(edge.source_node.identifier,edge.target_node.identifier))
            if edge.is_synonym:
                self.add_synonymous_edge(edge)
            else:
                self.add_nonsynonymous_edge(edge, reverse_edges)
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
        #make the set of types that we don't want to prune.  These are the end points (both text and id versions).
        ttypes = self.userquery.get_terminal_types()
        keep_types = set()
        keep_types.update(ttypes[0])
        keep_types.update(ttypes[1])
        keep_types.add( node_types.DISEASE_NAME )
        keep_types.add( node_types.DRUG_NAME )
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
        start_types, end_types = self.userquery.get_terminal_types()
        start_nodes = []
        end_nodes = []
        nodes = self.graph.nodes()
        for node in nodes:
            if node.node_type in start_types:
                start_nodes.append( node )
            elif node.node_type in end_types:
                end_nodes.append( node )
        return start_nodes, end_nodes
    def enhance(self):
        """Enhance nodes,edges with good labels and properties"""
        #TODO: it probably makes sense to push this stuff into the KNode itself
        self.logger.debug('Enhancing nodes with labels')
        for node in self.graph.nodes():
            prepare_node_for_output(node,self.rosetta.core)
    def support(self, support_module_names):
        """Look for extra information connecting nodes."""
        supporters = [import_module(module_name).get_supporter(self.rosetta.core)
                      for module_name in support_module_names]
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
                try:
                    for path in nx.all_shortest_paths(self.graph,source=start_node,target=end_node):
                        for n_i,source in enumerate(path):
                            for n_j in range(n_i + 1, len(path) ):
                                link=( source, path[n_j] )
                                links_to_check.add(link)
                except:
                    self.logger.error('No paths from {} to {}'.format(start_node.identifier, end_node.identifier) )
        self.logger.debug('Number of pairs to check: {}'.format( len( links_to_check) ) )
        if len(links_to_check) == 0:
            self.logger.error('No paths across the data.  Exiting without writing.')
            sys.exit(1)
        # Check each edge, add any support found.
        n_supported = 0
        for supporter in supporters:
            supporter.prepare( self.graph.nodes() )
            for source,target in links_to_check:
                support_edge = supporter.term_to_term(source,target)
                if support_edge is not None:
                    n_supported += 1
                    self.logger.debug ('  -Adding support edge from {} to {}'.format(source.identifier, target.identifier) )
                    self.add_nonsynonymous_edge( support_edge )
        self.logger.debug('Support Completed.  Added {} edges.'.format( n_supported ))
    def export(self,resultname):
        """Export to neo4j database."""
        #Just make sure that resultname is not going to bork up neo4j
        resultname=''.join(resultname.split('-'))
        resultname=''.join(resultname.split(' '))
        resultname=''.join(resultname.split(','))
        #TODO: lots of this should probably go in the KNode and KEdge objects?
        self.logger.info("Writing to neo4j with label {}".format(resultname))
        session = self.driver.session()
        #If we have this query already, overwrite it...
        session.run('MATCH (a:%s) DETACH DELETE a' % resultname)
        #Now add all the nodes
        for node in self.graph.nodes():
            session.run("CREATE (a:%s {id: {id}, name: {name}, node_type: {node_type}, synonyms: {syn}, meta: {meta}})" % resultname, \
                    {"id": node.identifier, "name": node.label, "node_type": node.node_type, "syn": list(node.synonyms), "meta": ''})
        for edge in self.graph.edges(data=True):
            aid = edge[0].identifier
            bid = edge[1].identifier
            ke = edge[2]['object']
            if ke.is_support:
                label = 'Support'
            elif ke.edge_source == 'lookup':  #TODO: make this an edge prop
                label = 'Lookup'
            else:
                label = 'Result'
            prepare_edge_for_output(ke)
            if ke.edge_source == 'chemotext2':
                session.run("MATCH (a:%s), (b:%s) WHERE a.id={aid} AND b.id={bid} CREATE (a)-[r:%s {source: {source}, function: {function}, pmids: {pmids}, onto_relation_id: {ontoid}, onto_relation_label: {ontolabel}, similarity: {sim}, terms:{terms}} ]->(b) return r" % \
                        (resultname,resultname, label),\
                        { "aid": aid, "bid": bid, "source": ke.edge_source, "function": ke.edge_function, "pmids": ke.pmidlist, "ontoid": ke.typed_relation_id, "ontolabel": ke.typed_relation_label, 'sim':ke.properties['similarity'] , 'terms':ke.properties['terms'] } )
            elif ke.edge_source == 'cdw':
                session.run("MATCH (a:%s), (b:%s) WHERE a.id={aid} AND b.id={bid} CREATE (a)-[r:%s {source: {source}, function: {function}, pmids: {pmids}, source_counts: {c1}, target_counts: {c2}, shared_counts: {c}, expected_counts: {e}, p_value:{p}} ]->(b) return r" % \
                        (resultname,resultname, label),\
                        { "aid": aid, "bid": bid, "source": ke.edge_source, "function": ke.edge_function, "pmids": ke.pmidlist, "ontoid": ke.typed_relation_id, "ontolabel": ke.typed_relation_label, 'c1': ke.properties['c1'], 'c2': ke.properties['c2'], 'c': ke.properties['c'], 'e': ke.properties['e'], 'p': ke.properties['p']} )
            else:
                session.run("MATCH (a:%s), (b:%s) WHERE a.id={aid} AND b.id={bid} CREATE (a)-[r:%s {source: {source}, function: {function}, pmids: {pmids}, onto_relation_id: {ontoid}, onto_relation_label: {ontolabel}} ]->(b) return r" % \
                        (resultname,resultname, label),\
                        { "aid": aid, "bid": bid, "source": ke.edge_source, "function": ke.edge_function, "pmids": ke.pmidlist, "ontoid": ke.typed_relation_id, "ontolabel": ke.typed_relation_label } )
        session.close()
        self.logger.info("Wrote {} nodes.".format( len(self.graph.nodes()) ) )

#TODO: push to node, ...
def prepare_node_for_output(node,gt):
    node.synonyms.update( [mi['curie'] for mi in node.mesh_identifiers if mi['curie'] != ''] )
    if node.node_type == node_types.DISEASE or node.node_type == node_types.GENETIC_CONDITION:
        if 'mondo_identifiers' in node.properties:
            node.synonyms.update(node.properties['mondo_identifiers'])
        node.label = gt.mondo.get_label( node.identifier )
    if node.label is None:
        if node.node_type == node_types.DISEASE_NAME or node.node_type == node_types.DRUG_NAME:
            node.label = node.identifier.split(':')[-1]
        elif node.node_type == node_types.GENE and node.identifier.startswith('HGNC:'):
            node.label = gt.hgnc.get_name( node )
        elif node.node_type == node_types.GENE and node.identifier.upper().startswith('NCBIGENE:'):
            node.label = gt.hgnc.get_name( node )
        elif node.node_type == node_types.CELL and node.identifier.upper().startswith('CL:'):
            node.label = gt.uberongraph.cell_get_cellname( node.identifier )[0]['cellLabel']
        else:
            node.label = node.identifier
    logging.getLogger('application').debug(node.label)

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
    edge.reversed = edge.properties['reversed']


def run_query(querylist, supports, result_name, output_path, rosetta, prune=True):
    """Given a query, create a knowledge graph though querying external data sources.  Export the graph"""
    kgraph = KnowledgeGraph( querylist, rosetta )
    kgraph.execute()
    kgraph.print_types()
    if prune:
        kgraph.prune()
    kgraph.enhance()
    kgraph.support(supports)
    kgraph.export(result_name)
       
def question1(disease_name, disease_identifiers, supports,rosetta):
    name_node = KNode( '{}.{}'.format(node_types.DISEASE_NAME,disease_name), node_types.DISEASE_NAME )
    query = UserQuery(disease_identifiers,node_types.DISEASE, name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.GENETIC_CONDITION)
    run_query(query,supports,'Query1_{}_{}'.format('_'.join(disease_name.split()),'_'.join(supports)) , '.', rosetta)
   
def build_question2(drug_name, disease_name, drug_ids, disease_ids ):
    drug_name_node = KNode( '{}.{}'.format(node_types.DRUG_NAME,drug_name), node_types.DRUG_NAME )
    disease_name_node = KNode( '{}.{}'.format(node_types.DISEASE_NAME,disease_name), node_types.DISEASE_NAME )
    query = UserQuery(drug_ids,node_types.DRUG,drug_name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.PROCESS)
    query.add_transition(node_types.CELL)
    query.add_transition(node_types.ANATOMY)
    query.add_transition(node_types.PHENOTYPE)
    query.add_transition(node_types.DISEASE, end_values = disease_ids)
    query.add_end_lookup_node(disease_name_node)
    return query

def question2(drug_name, disease_name, drug_ids, disease_ids, supports, rosetta ):
    query = build_question2(drug_name, disease_name, drug_ids, disease_ids)
    outdisease = '_'.join(disease_name.split())
    outdrug    = '_'.join(drug_name.split())
    run_query(query,supports,'Query2_{}_{}_{}'.format(outdisease, outdrug, '_'.join(supports)) , '.', rosetta, prune=True)

def question2a(drug_name, phenotype_name, drug_ids, phenotype_ids, supports, rosetta ):
    drug_name_node = KNode( '{}.{}'.format(node_types.DRUG_NAME,drug_name), node_types.DRUG_NAME )
    #TODO: clean up name type.  We can probably just drop to "NAME" since we're not using the graph to get names...
    p_name_node = KNode( '{}.{}'.format(node_types.DISEASE_NAME,phenotype_name), node_types.DISEASE_NAME )
    query = UserQuery(drug_ids,node_types.DRUG,drug_name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.PROCESS)
    query.add_transition(node_types.CELL)
    query.add_transition(node_types.ANATOMY)
    query.add_transition(node_types.PHENOTYPE, end_values = phenotype_ids)
    query.add_end_lookup_node(p_name_node)
    outdisease = '_'.join(phenotype_name.split())
    outdrug    = '_'.join(drug_name.split())
    run_query(query,supports,'Query2a_{}_{}_{}'.format(outdisease, outdrug, '_'.join(supports)) , '.', rosetta, prune=True)

def quicktest(drugname):
    lquery = userquery.OneSidedLinearUserQuery(drugname,node_types.DRUG_NAME)
    lquery.add_transition(node_types.DRUG)
    lquery.add_transition(node_types.GENE)
    lquery.add_transition(node_types.PROCESS)
    run_query(lquery,['chemotext'],'Testq', '.')

def setup():    
    logger = logging.getLogger('application')
    logger.setLevel(level = logging.DEBUG)
    rosetta = Rosetta()
    return rosetta

def main_test():
    parser = argparse.ArgumentParser(description='Protokop.')
    parser.add_argument('-s', '--support', help='Name of the support system', action='append', choices=['chemotext','chemotext2','cdw'], required=True)
    parser.add_argument('-q', '--question', help='Shortcut for certain questions (1=Disease/GeneticCondition, 2=COP)', choices=[1,2], required=True, type=int)
    parser.add_argument('--start', help='Text to initiate query', required = True)
    parser.add_argument('--end', help='Text to finalize query', required = False)
    args = parser.parse_args()
    rosetta = setup()
    if args.question == 1:
        if args.end is not None:
            print('--end argument not supported for question 1.  Ignoring')
        disease_ids = lookup_disease_by_name( args.start, rosetta.core )
        if len(disease_ids) == 0:
            sys.exit(1)
        question1( args.start, disease_ids, args.support ,rosetta)
    elif args.question == 2:
        if args.end is None:
            print('--end required for question 2. Exiting')
            sys.exit(1)
        drug_ids    = lookup_drug_by_name( args.start , rosetta.core )
        disease_ids = lookup_disease_by_name( args.end, rosetta.core )
        if len(drug_ids) == 0:
            sys.exit(1)
        if len(disease_ids) > 0:
            question2(args.start, args.end, drug_ids, disease_ids, args.support, rosetta)
        else:
            #Maybe the 'disease' is really a phenotype
            phenotype_ids = lookup_phenotype_by_name( args.end, rosetta.core )
            if len(phenotype_ids) == 0:
                sys.exit(1)
            #It is a phenotype!
            question2a(args.start, args.end, drug_ids, phenotype_ids, args.support, rosetta)

if __name__ == '__main__':
    main_test()
    #quicktest('ADAPALENE')
