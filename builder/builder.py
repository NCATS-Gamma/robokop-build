from greent.graph_components import KNode, KEdge
from greent import node_types
from greent.rosetta import Rosetta
from greent.util import Text
from userquery import UserQuery
import argparse
import networkx as nx
import logging
import sys
from neo4j.v1 import GraphDatabase
from collections import OrderedDict
from importlib import import_module
from lookup_utils import lookup_identifier
from collections import defaultdict
from pathlex import tokenize_path


class KnowledgeGraph:
    def __init__(self, userquery, rosetta):
        """KnowledgeGraph is a local version of the query results. 
        After full processing, it gets pushed to neo4j.
        """
        self.logger = logging.getLogger('application')
        self.graph = nx.MultiDiGraph()
        self.userquery = userquery
        self.rosetta = rosetta
        if not self.userquery.compile_query(self.rosetta):
            self.logger.error('Query fails. Exiting.')
            sys.exit(1)
        # node_map is a map from identifiers to the node associated.  It's useful because
        #  we are collapsing nodes along synonym edges, so each node might asked for in
        #  multiple different ways.
        self.node_map = {}
        uri = 'bolt://localhost:7687'
        self.driver = GraphDatabase.driver(uri, encrypted=False)

    def execute(self):
        """Execute the query that defines the graph"""
        self.logger.debug('Executing Query')
        # GreenT wants a cypher query to find transitions, and a starting point
        cyphers  = self.userquery.generate_cypher()
        starts   = self.userquery.get_start_node()
        reverses = self.userquery.get_reversed()
        lookups  = self.userquery.get_lookups()
        for cypher, start, reverse, lookup in zip(cyphers, starts, reverses, lookups):
            input_name = Text.un_curie(lookup.identifier)
            self.logger.debug(start)
            self.logger.debug(input_name)
            self.logger.debug('CYPHER')
            self.logger.debug(cypher)
            identifier, ntype = start
            start_node = KNode(identifier, ntype, label=input_name)
            kedge = KEdge('lookup', 'lookup')
            kedge.source_node = lookup
            kedge.target_node = start_node
            self.add_nonsynonymous_edge(kedge)
            # Fire this to rosetta, collect the result
            result_graph = self.rosetta.graph([(None, start_node)], query=cypher)
            # result_graph contains duplicate edges.  Remove them, while preserving order:
            result_graph = list(OrderedDict.fromkeys(result_graph))
            self.add_edges(result_graph, reverse)
        self.logger.debug('Query Complete')

    def print_types(self):
        counts = defaultdict(int)
        for node in self.graph.nodes():
            counts[node.node_type] += 1
        for node_type in counts:
            self.logger.info('{}: {}'.format(node_type, counts[node_type]))

    def merge(self, source, target):
        """Source and target are both members of the graph, and we've found that they are
        synonyms.  Remove target, and attach all of target's edges to source"""
        source.add_synonym(target)
        nodes_from_target = self.graph.successors(target)
        for s in nodes_from_target:
            # b/c this is a multidigraph, this is actually a map where the edges are the values
            self.logger.debug('Node s: {}'.format(s))
            kedgemap = self.graph.get_edge_data(target, s)
            if kedgemap is None:
                self.logger.error('s?')
            for i in kedgemap.values():
                kedge = i['object']
                # The node being removed is the source in these edges, replace it
                kedge.source_node = source
                self.graph.add_edge(source, s, object=kedge)
        nodes_to_target = self.graph.predecessors(target)
        for p in nodes_to_target:
            self.logger.debug('Node p: {}'.format(p))
            kedgemap = self.graph.get_edge_data(p, target)
            if kedgemap is None:
                self.logger.error('p?')
            for i in kedgemap.values():
                kedge = i['object']
                kedge.target_node = source
                self.graph.add_edge(p, source, object=kedge)
        self.graph.remove_node(target)
        # now, any synonym that was mapping to the old target should be remapped to source
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
                self.logger.debug('Already merged')
                return
            self.merge(source, target)
            return
        if target is not None:
            source, target = target, source
        source.add_synonym(edge.target_node)
        self.node_map[edge.target_node.identifier] = source

    def add_nonsynonymous_edge(self, edge, reverse_edges=False):
        self.logger.debug(' New Nonsynonymous')
        # Found an edge between nodes. Add nodes if needed.
        source_node = self.add_or_find_node(edge.source_node)
        target_node = self.add_or_find_node(edge.target_node)
        edge.source_node = source_node
        edge.target_node = target_node
        # Now the nodes are translated to the canonical identifiers, make the edge
        if reverse_edges:
            edge.properties['reversed'] = True
            self.graph.add_edge(target_node, source_node, object=edge)
            self.logger.debug('Edge: {}'.format(self.graph.get_edge_data(target_node, source_node)))
        else:
            edge.properties['reversed'] = False
            self.graph.add_edge(source_node, target_node, object=edge)
            self.logger.debug('Edge: {}'.format(self.graph.get_edge_data(source_node, target_node)))

    def add_edges(self, edge_list, reverse_edges):
        """Add a list of edges (and the associated nodes) to the graph."""
        for edge in edge_list:
            self.logger.debug('Edge: {} -> {}'.format(edge.source_node.identifier, edge.target_node.identifier))
            if edge.is_synonym:
                self.add_synonymous_edge(edge)
            else:
                self.add_nonsynonymous_edge(edge, reverse_edges)

    def find_node(self, node):
        """If node exists in graph, return it, otherwise, return None"""
        if node.identifier in self.node_map:
            return self.node_map[node.identifier]
        return None

    def add_or_find_node(self, node):
        """Find a node that already exists in the graph, checking for synonyms.
        If not found, create it & add to graph"""
        fnode = self.find_node(node)
        if fnode is not None:
            return fnode
        else:
            self.graph.add_node(node)
            self.node_map[node.identifier] = node
            return node

    def prune(self):
        """Recursively remove poorly connected nodes.  In particular, each (non-terminal) node
        must be connected to two different kinds of nodes."""
        # TODO, that is maybe a bit too much.  You can't have disease-gene-disease for instance !
        # But degree is not enough because you can have A and B both go to C but C doesn't go anywhere.
        # Probably need to interact with the query to decide whether this node is pruneable or not.
        self.logger.debug('Pruning Graph')
        removed = True
        # make the set of types that we don't want to prune.  These are the end points (both text and id versions).
        ttypes = self.userquery.get_terminal_types()
        if node_types.UNSPECIFIED in ttypes[1]:
            #Any kind of end node will match, so stop
            return
        keep_types = set()
        keep_types.update(ttypes[0])
        keep_types.update(ttypes[1])
        keep_types.add(node_types.DISEASE_NAME)
        keep_types.add(node_types.DRUG_NAME)
        n_pruned = 0
        while removed:
            removed = False
            to_remove = []
            for node in self.graph.nodes():
                if node.node_type in keep_types:
                    continue
                # Graph is directed.  graph.neighbors only returns successors
                neighbors = self.graph.successors(node) + self.graph.predecessors(node)
                neighbor_types = set([neighbor.node_type for neighbor in neighbors])
                if len(neighbor_types) < 2:
                    to_remove.append(node)
            for node in to_remove:
                removed = True
                n_pruned += 1
                self.graph.remove_node(node)
        self.logger.debug('Pruned {} nodes.'.format(n_pruned))

    def get_terminal_nodes(self):
        """Return the nodes at the beginning or end of a query"""
        # TODO: Currently doing via type.  Probably need to mark these instead.
        start_types, end_types = self.userquery.get_terminal_types()
        start_nodes = []
        end_nodes = []
        nodes = self.graph.nodes()
        for node in nodes:
            if node.node_type in start_types:
                start_nodes.append(node)
            elif node.node_type in end_types:
                end_nodes.append(node)
        return start_nodes, end_nodes

    def enhance(self):
        """Enhance nodes,edges with good labels and properties"""
        # TODO: it probably makes sense to push this stuff into the KNode itself
        self.logger.debug('Enhancing nodes with labels')
        for node in self.graph.nodes():
            prepare_node_for_output(node, self.rosetta.core)

    def support(self, support_module_names):
        """Look for extra information connecting nodes."""
        supporters = [import_module(module_name).get_supporter(self.rosetta.core)
                      for module_name in support_module_names]
        # TODO: how do we want to handle support edges
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
                    for path in nx.all_shortest_paths(self.graph, source=start_node, target=end_node):
                        for n_i, source in enumerate(path):
                            for n_j in range(n_i + 1, len(path)):
                                link = (source, path[n_j])
                                links_to_check.add(link)
                except:
                    self.logger.error('No paths from {} to {}'.format(start_node.identifier, end_node.identifier))
        self.logger.debug('Number of pairs to check: {}'.format(len(links_to_check)))
        if len(links_to_check) == 0:
            self.logger.error('No paths across the data.  Exiting without writing.')
            sys.exit(1)
        # Check each edge, add any support found.
        n_supported = 0
        for supporter in supporters:
            supporter.prepare(self.graph.nodes())
            for source, target in links_to_check:
                support_edge = supporter.term_to_term(source, target)
                if support_edge is not None:
                    n_supported += 1
                    self.logger.debug('  -Adding support edge from {} to {}'.
                                      format(source.identifier, target.identifier))
                    self.add_nonsynonymous_edge(support_edge)
        self.logger.debug('Support Completed.  Added {} edges.'.format(n_supported))

    def export(self, resultname):
        """Export to neo4j database."""
        # Just make sure that resultname is not going to bork up neo4j
        resultname = ''.join(resultname.split('-'))
        resultname = ''.join(resultname.split(' '))
        resultname = ''.join(resultname.split(','))
        # TODO: lots of this should probably go in the KNode and KEdge objects?
        self.logger.info("Writing to neo4j with label {}".format(resultname))
        session = self.driver.session()
        # If we have this query already, overwrite it...
        session.run('MATCH (a:%s) DETACH DELETE a' % resultname)
        # Now add all the nodes
        for node in self.graph.nodes():
            type_label = ''.join(node.node_type.split('.'))
            session.run("CREATE (a:%s:%s {id: {id}, name: {name}, node_type: {node_type}, synonyms: {syn}, meta: {meta}})"
                        % (resultname, type_label),
                        {"id": node.identifier, "name": node.label, "node_type": node.node_type,
                         "syn": list(node.synonyms), "meta": ''})
        for edge in self.graph.edges(data=True):
            aid = edge[0].identifier
            bid = edge[1].identifier
            ke = edge[2]['object']
            if ke.is_support:
                label = 'Support'
            elif ke.edge_source == 'lookup':
                #       TODO: make this an edge prop
                label = 'Lookup'
            else:
                label = 'Result'
            prepare_edge_for_output(ke)
            if ke.edge_source == 'chemotext2':
                session.run(
                    "MATCH (a:%s), (b:%s) WHERE a.id={aid} AND b.id={bid} CREATE (a)-[r:%s {source: {source}, function: {function}, pmids: {pmids}, onto_relation_id: {ontoid}, onto_relation_label: {ontolabel}, similarity: {sim}, terms:{terms}} ]->(b) return r" %
                    (resultname, resultname, label),
                    {"aid": aid, "bid": bid, "source": ke.edge_source, "function": ke.edge_function,
                     "pmids": ke.pmidlist, "ontoid": ke.typed_relation_id, "ontolabel": ke.typed_relation_label,
                     'sim': ke.properties['similarity'], 'terms': ke.properties['terms']})
            elif ke.edge_source == 'cdw':
                session.run(
                    "MATCH (a:%s), (b:%s) WHERE a.id={aid} AND b.id={bid} CREATE (a)-[r:%s {source: {source}, function: {function}, pmids: {pmids}, source_counts: {c1}, target_counts: {c2}, shared_counts: {c}, expected_counts: {e}, p_value:{p}} ]->(b) return r" %
                    (resultname, resultname, label),
                    {"aid": aid, "bid": bid, "source": ke.edge_source, "function": ke.edge_function,
                     "pmids": ke.pmidlist, "ontoid": ke.typed_relation_id, "ontolabel": ke.typed_relation_label,
                     'c1': ke.properties['c1'], 'c2': ke.properties['c2'], 'c': ke.properties['c'],
                     'e': ke.properties['e'], 'p': ke.properties['p']})
            else:
                session.run(
                    "MATCH (a:%s), (b:%s) WHERE a.id={aid} AND b.id={bid} CREATE (a)-[r:%s {source: {source}, function: {function}, pmids: {pmids}, onto_relation_id: {ontoid}, onto_relation_label: {ontolabel}} ]->(b) return r" %
                    (resultname, resultname, label),
                    {"aid": aid, "bid": bid, "source": ke.edge_source, "function": ke.edge_function,
                     "pmids": ke.pmidlist, "ontoid": ke.typed_relation_id, "ontolabel": ke.typed_relation_label})
        session.close()
        self.logger.info("Wrote {} nodes.".format(len(self.graph.nodes())))


# TODO: push to node, ...
def prepare_node_for_output(node, gt):
    node.synonyms.update([mi['curie'] for mi in node.mesh_identifiers if mi['curie'] != ''])
    if node.node_type == node_types.DISEASE or node.node_type == node_types.GENETIC_CONDITION:
        if 'mondo_identifiers' in node.properties:
            node.synonyms.update(node.properties['mondo_identifiers'])
        try:
            node.label = gt.mondo.get_label(node.identifier)
        except:
            if node.label is None:
                node.label = node.identifier
    if node.label is None:
        if node.node_type == node_types.DISEASE_NAME or node.node_type == node_types.DRUG_NAME:
            node.label = node.identifier.split(':')[-1]
        elif node.node_type == node_types.GENE and node.identifier.startswith('HGNC:'):
            node.label = gt.hgnc.get_name(node)
        elif node.node_type == node_types.GENE and node.identifier.upper().startswith('NCBIGENE:'):
            node.label = gt.hgnc.get_name(node)
        elif node.node_type == node_types.CELL and node.identifier.upper().startswith('CL:'):
            node.label = gt.uberongraph.cell_get_cellname(node.identifier)[0]['cellLabel']
        else:
            node.label = node.identifier
    logging.getLogger('application').debug(node.label)


# Push to edge...
def prepare_edge_for_output(edge):
    # We should settle on a format for PMIDs.  Do we always lookup / include e.g. title? Or does UI do that?
    pmidlist = []
    if 'publications' in edge.properties:
        for pub in edge.properties['publications']:
            # v. brittle. Should be put into the edge creation...
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


def run_query(querylist, supports, result_name, rosetta, prune=True):
    """Given a query, create a knowledge graph though querying external data sources.  Export the graph"""
    kgraph = KnowledgeGraph(querylist, rosetta)
    kgraph.execute()
    kgraph.print_types()
    if prune:
        kgraph.prune()
    kgraph.enhance()
    kgraph.support(supports)
    kgraph.export(result_name)
       

def generate_query(pathway, start_node, start_identifiers, end_node=None, end_identifiers=None):
    start, middle, end = pathway[0], pathway[1:-1], pathway[-1]
    query = UserQuery(start_identifiers, start.nodetype, start_node)
    print(start.nodetype)
    for transition in middle:
        print(transition)
        query.add_transition(transition.nodetype, transition.min_path_length, transition.max_path_length)
    print(end)
    query.add_transition(end.nodetype, end.min_path_length, end.max_path_length, end_values=end_identifiers)
    if end_node is not None:
        query.add_end_lookup_node(end_node)
    return query


def generate_name_node(name, nodetype):
    if nodetype == node_types.DRUG:
        return KNode('{}:{}'.format(node_types.DRUG_NAME, name), node_types.DRUG_NAME)
    elif nodetype == node_types.DISEASE or nodetype == node_types.PHENOTYPE:
        return KNode('{}:{}'.format(node_types.DISEASE_NAME, name), node_types.DISEASE_NAME)


def run(pathway, start_name, end_name, label, supports):
    """Programmatic interface.  Pathway defined as in the command-line input.
       Arguments:
         pathway: A string defining the query.  See command line help for details
         start_name: The name of the entity at one end of the query
         end_name: The name of the entity at the other end of the query. Can be None.
         label: the label designating the result in neo4j
         supports: array strings designating support modules to apply
    """
    # TODO: move to a more structured pathway description (such as json)
    steps = tokenize_path(pathway)
    # start_type = node_types.type_codes[pathway[0]]
    start_type = steps[0].nodetype
    rosetta = setup()
    start_identifiers = lookup_identifier(start_name, start_type, rosetta.core)
    start_node = generate_name_node(start_name, start_type)
    if end_name is not None:
        # end_type = node_types.type_codes[pathway[-1]]
        end_type = steps[-1].nodetype
        end_identifiers = lookup_identifier(end_name, end_type, rosetta.core)
        end_node = generate_name_node(end_name, end_type)
    else:
        end_node = None
        end_identifiers = None
    query = generate_query(steps, start_node, start_identifiers, end_node, end_identifiers)
    run_query(query, supports, label, rosetta, prune=True)


def setup():
    logger = logging.getLogger('application')
    logger.setLevel(level=logging.DEBUG)
    rosetta = Rosetta()
    return rosetta


helpstring = """Execute a query across all configured data sources.  The query is defined 
using the -p argument, which takes a string.  Each character in the string 
represents one high-level type of node that will be sequentially included 
denoted as:
S: Substance (Drug)
G: Gene
P: Process (Pathway)
C: Cell Type
A: Anatomical Feature
T: Phenotype
D: Disease
X: Genetic Condition
?: Unspecified Node

It is also possible to specify indirect transitions by including 
parenthetical values between these letters containing the number of 
allowed type transitions. A default (direct) transition would
be denoted (1-1), but it is not necessary to include between
every node.

Examples:
    DGX        Go directly from Disease, to Gene, to Genetic Condition.
    D(1-2)X    Go from Disease to Genetic Condition, either directly (1)
               or via another node (of any type) in between
    SGPCATD    Construct a Clinical Outcome Pathway, moving from a Drug 
               to a Gene to a Process to a Cell Type to an Anatomical 
               Feature to a Phenotype to a Disease. Each with no 
               intermediary nodes
    SG(2-5)D   Go from a Drug to a Gene, through 2 to 5 other transitions, and 
               to a Disease.
"""


def main():
    parser = argparse.ArgumentParser(description=helpstring,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-s', '--support', help='Name of the support system', 
                        action='append',
                        choices=['chemotext', 'chemotext2', 'cdw'],
                        required=True)
    parser.add_argument('-p', '--pathway', help='Defines the query pathway (see description). Cannot be used with -q',
                        required=False)
    parser.add_argument('-q', '--question',
                        help='Shortcut for certain questions (1=Disease/GeneticCondition, 2=COP, 3=COP ending in Phenotype). Cannot be used with -p',
                        choices=[1, 2, 3],
                        required=False,
                        type=int)
    parser.add_argument('--start', help='Text to initiate query', required=True)
    parser.add_argument('--end', help='Text to finalize query', required=False)
    parser.add_argument('-l', '--label', help='Label for result in neo4j. Will overwrite.', 
                        required=True)
    args = parser.parse_args()
    pathway = None
    if args.pathway is not None and args.question is not None:
        print('Cannot specify both question and pathway. Exiting.')
        sys.exit(1)
    if args.question is not None:
        if args.question == 1:
            pathway = 'DGX'
            if args.end is not None:
                print('--end argument not supported for question 1.  Ignoring')
        elif args.question == 2:
            pathway = 'SGPCATD'
        elif args.question == 3:
            pathway = 'SGPCAT'
        if args.question in (2, 3):
            if args.end is None:
                print('--end required for question 2. Exiting')
                sys.exit(1)
    else:
        pathway = args.pathway
    run(pathway, args.start, args.end, args.label, args.support)


if __name__ == '__main__':
    main()
