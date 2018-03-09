from greent.node_types import node_types, DRUG_NAME, DISEASE_NAME, UNSPECIFIED
from greent.util import Text

class Transition:
    def __init__(self, last_type, next_type, min_path_length, max_path_length):
        self.in_type = last_type
        self.out_type = next_type
        self.min_path_length = min_path_length
        self.max_path_length = max_path_length
        self.in_node = None
        self.out_node = None

    def generate_reverse(self):
        return Transition(self.out_type, self.in_type, self.min_path_length, self.max_path_length)

    @staticmethod
    def get_fstring(ntype):
        if ntype == DRUG_NAME or ntype == DISEASE_NAME:
            return 'n{0}{{name:"{1}"}}'
        if ntype is None:
            return 'n{0}'
        else:
            return 'n{0}:{1}'

    def generate_concept_cypher_pathstring(self, t_number):
        end   = f'(c{t_number+1}:Concept {{name: "{self.out_type}" }})'
        pstring = ''
        if t_number == 0:
            start = f'(c{t_number}:Concept {{name: "{self.in_type}" }})\n'
            pstring += start
        if self.max_path_length > 1:
            pstring += f'-[:translation*{self.min_path_length}..{self.max_path_length}]-\n'
        else:
            pstring += '--\n'
        pstring += f'{end}\n'
        return pstring

class QueryDefinition:
    """Defines a query"""

    def __init__(self):
        self.start_values = None
        self.start_type = None
        self.end_values = None
        self.node_types = []
        self.transitions = []
        self.start_lookup_node = None
        self.end_lookup_node = None

class UserQuery:
    """This is the class that the rest of builder uses to interact with a query."""

    def __init__(self, start_values, start_type, lookup_node):
        """Create an instance of UserQuery. Takes a starting value and the type of that value"""
        self.query = None
        self.definition = QueryDefinition()
        # Value for the original node
        self.definition.start_values = start_values
        self.definition.start_type = start_type
        self.definition.end_values = None
        # The term used to create the initial point
        self.definition.start_lookup_node = lookup_node
        # List of user-level types that we must pass through
        self.add_node(start_type)

    def add_node(self, node_type):
        """Add a node to the node list, validating the type
           20180108: node_type may be None"""
        # Our start node is more specific than this...  Need to have another validation method
        if node_type is not None and node_type not in node_types:
            raise Exception('node type must be one of greent.node_types')
        self.definition.node_types.append(node_type)

    def add_transition(self, next_type, min_path_length=1, max_path_length=1, end_values=None):
        """Add another required node type to the path.

        When a new node is added to the user query, the user is asserting that
        the returned path must go through a node of this type.  The default is
        that the next node should be directly related to the previous. That is,
        no other node types should be between the previous node and the current
        node.   There may be other nodes, but they will represent synonyms of
        the previous or current node.  This is defined using the
        max_path_length input, which defaults to 1.  On the other hand, a user
        may wish to define that some number of other node types must be between
        one node and another.  This can be specified by the min_path_length,
        which also defaults to 1.  If indirect edges are demanded, this
        parameter is set higher.  If this is the final transition, a value for
        the terminal node may be added.  Attempting to add more transitions
        after setting an end value will result in an exception.  If this is the
        terminal node, but it does not have a specified value, then no
        end_value needs to be specified.

        arguments: next_type: type of the output node from the transition.
                              Must be an element of reasoner.node_types.
                   min_path_length: The minimum number of non-synonym transitions
                                    to get from the previous node to the added node
                   max_path_length: The maximum number of non-synonym transitions to get
                                    from the previous node to the added node
                   end_value: Value of this node (if this is the terminal node, otherwise None)
        """
        # validate some inputs
        # TODO: subclass Exception
        if min_path_length > max_path_length:
            raise Exception('Maximum path length cannot be shorter than minimum path length')
        if self.definition.end_values is not None:
            raise Exception('Cannot add more transitions to a path with a terminal node')
        # Add the node to the type list
        self.add_node(next_type)
        # Add the transition
        t = Transition(self.definition.node_types[-2], next_type, min_path_length, max_path_length)
        self.definition.transitions.append(t)
        # Add the end_value
        if end_values is not None:
            self.definition.end_values = end_values

    def add_end_lookup_node(self, lookup_node):
        self.definition.end_lookup_node = lookup_node

    def generate_cypher(self):
        """Generate a cypher query to find paths through the concept-level map."""
        cypherbuffer = ['MATCH p=\n']
        paths_parts = []
        for t_number, transition in enumerate(self.definition.transitions):
            paths_parts.append(transition.generate_concept_cypher_pathstring(t_number))
        cypherbuffer.append( ''.join(paths_parts) )
        last_node_i = len(self.definition.transitions)
        cypherbuffer.append(f'WITH p,c0,c{last_node_i}\n')
        if self.definition.end_values is None:
            cypherbuffer.append(f'MATCH q=(c0:Concept)-[:translation*0..{last_node_i}]->(c{last_node_i}:Concept)\n')
        else:
            cypherbuffer.append(f'MATCH q=(c0:Concept)-[:translation*0..{last_node_i}]->()<-[:translation*0..{last_node_i}]-(c{last_node_i}:Concept)\n')
        cypherbuffer.append('WHERE p=q\n')
        cypherbuffer.append('RETURN p, EXTRACT( r in relationships(p) | startNode(r) ) \n')
        return ''.join(cypherbuffer)

    def compile_query(self, rosetta):
        self.cypher = self.generate_cypher()
        plans = rosetta.type_graph.get_transitions(self.cypher)
        self.programs = [Program(plan, self.definition, rosetta) for plan in self.plans]
        return len(self.programs) > 0

    def get_programs(self):
        return []

    #def get_terminal_types(self):
    #    return self.query.get_terminal_types()
#
#    def get_start_node(self):
#        return self.query.get_start_node()
#
#    def get_lookups(self):
#        return self.query.get_lookups()
#
#    def get_neighbor_types(self, node_type):
#        return self.query.get_neighbor_types(node_type)

class OneSidedLinearUserQuery:
    """A class for constructing linear paths through a series of knowledge sources.

    We have a set of knowledge sources that can be considered as a graph.  Each edge in the graph represents
    an endpoint in the sources (i.e. a service call) that takes (usually) one node and returns one or more nodes.
    These endpoints are typed, such as a service that takes drug ids and returns genes ids.

    To execute queries, we need to define a path through this graph, but the user should not be tasked with this.
    Instead, the user generates a high-level description of the kind of path that they want to execute, and
    it gets turned into a cypher query on the knowledge source graph.

    This class represents the user-level query"""

    def __init__(self, start_value, query_definition):
        """Create an instance of UserQuery. Takes a starting value and the type of that value"""
        self.start_value = start_value
        self.start_type = query_definition.start_type
        self.node_types = query_definition.node_types
        self.transitions = query_definition.transitions
        self.final_concepts=set()

    def get_start_node(self):
        node = self.node_types[0]
        if node in (DISEASE_NAME, DRUG_NAME):
            return [('{0}:{1}'.format(node, self.start_value), node)]
        return [(self.start_value, node)]

    def get_terminal_types(self):
        """Returns a two element array.  The first element is a set of starting terminal types.
        The second element is a set of ending terminal types"""
        return [set([self.node_types[0]]), set([self.node_types[-1]])]

    def get_neighbor_types(self, query_node_type):
        neighbor_types = set()
        for node_number, node_type in enumerate(self.node_types):
            if node_number == 0:
                continue
            if node_type == query_node_type:
                if node_number == len(self.node_types) - 1:
                    pair =  (self.node_types[node_number-1], None)
                else:
                    pair =  (self.node_types[node_number-1], self.node_types[node_number+1])
                neighbor_types.add(pair)
        return neighbor_types

    @staticmethod
    def get_reversed():
        return [False]

    def get_final_concepts(self):
        return self.final_concepts

    def compile_query(self, rosetta):
        """Determine whether there is a path through the data that can satisfy this query"""
        self.cyphers = [self.generate_concept_cypher()]
        if len(self.cyphers) == 0:
            return False
        programs = []
        for cypher in self.cyphers:
            programs += rosetta.type_graph.get_transitions(cypher)
            #if len(programs) > 0:
            #    print( programs[0])
            for program in programs:
                self.final_concepts.add( program[-1]['next_type'] )
        return len(programs) > 0

#    def create_cypher(self,rosetta):
#        self.cyphers = [self.generate_concept_cypher()]
#        paths = rosetta.type_graph.run_cypher_query(cypher)
#        if len(paths) == 0:
#            return []
#        return [cypher]
        #concept_name_lists = [self.extract_concept_nodes(path) for path in paths.rows]
        #self.cyphers = []
        #for concept_names in concept_name_lists:
        #    self.final_concepts.add( concept_names[-1] )
        #    fullcypher = self.generate_type_cypher(concept_names)
        #    self.cyphers.append(fullcypher)
        #return self.cyphers

    def generate_cypher(self):
        return self.cyphers

    def generate_type_cypher(self, concept_names):
        start_curie = Text.get_curie(self.start_value)
        buffer = f'MATCH p=(n0:Type)-[:SYNONYM*0..2]-(n0a:Type:{concept_names[0]})-[]->\n'
        for count, c_name in enumerate(concept_names[1:-1]):
            c = count + 1
            buffer += f'(n{c}:Type:{c_name})-[:SYNONYM*0..2]-(n{c}a:Type:{c_name})-[]->\n'
        c = len(concept_names) - 1
        #We add an extra synonym step at the end to help stitch together different arms of the query.
        buffer += f'(n{c}:Type:{concept_names[-1]})-[:SYNONYM*0..1]-(n{c}a:Type:{concept_names[-1]})\n'
        buffer += f'WHERE n0.name = "{start_curie}"\n'
        buffer += 'return p'
        return buffer

    @staticmethod
    def extract_concept_nodes(path):
        names = [segment[0]['name'] for segment in path]
        names.append(path[-1][-1]['name'])
        return names

    def generate_concept_cypher(self):
        """Generate a cypher query to find paths through the concept-level map."""
        cypherbuffer = ['MATCH\n']
        paths_parts = []
        for t_number, transition in enumerate(self.transitions):
            paths_parts.append(transition.generate_concept_cypher_pathstring(t_number))
        cypherbuffer.append(',\n'.join(paths_parts))
        cypherbuffer.append('\nWHERE\n')
        wheres = []
        for t_number, nodetype in enumerate(self.node_types):
            if nodetype != UNSPECIFIED:
                wheres.append(f'n{t_number}.name = "{nodetype}"')
        cypherbuffer.append('\nAND '.join(wheres))
        ps = [f'p{t}' for t in range(len(self.transitions))]
        cypherbuffer.append('\nRETURN ')
        cypherbuffer.append(','.join(ps))
        cypherbuffer.append('\n')
        return ''.join(cypherbuffer)

    def old_generate_cypher(self, end_value=None):
        """generate a cypher query to generate paths through the data sources. Optionally, callers can
        pass a specified end_value for the type-graph traversal."""
        cypherbuffer = ['MATCH']
        paths_parts = []
        for t_number, transition in enumerate(self.transitions):
            paths_parts.append(transition.generate_cypher_pathstring(t_number))
        cypherbuffer.append(',\n'.join(paths_parts))
        cypherbuffer.append('WHERE')
        curie_prefix = self.start_value.split(':')[0]
        cypherbuffer.append('n0.name="{}" AND'.format(curie_prefix))
        if end_value is not None:
            end_index = len(self.transitions)
            curie_prefix = end_value.split(':')[0]
            cypherbuffer.append('n{}.name="{}" AND'.format(end_index, curie_prefix))
        # NONE (r in relationships(p0) WHERE type(r) = "UNKNOWN"
        no_unknowns = []
        for t_number, transition in enumerate(self.transitions):
            no_unknowns.append('NONE (r in relationships(p{}) WHERE type(r) = "UNKNOWN")'.format(t_number))
        cypherbuffer.append('\nAND '.join(no_unknowns))
        # WITH (list of paths) (previous list of lengths) reduce () as dx, reduce() as synx WHERE [conditions on dx]
        with_parts = []
        pathstring = ','.join(['p{0}'.format(i) for i in range(len(self.transitions))])
        for t_number, transition in enumerate(self.transitions):
            with_parts.append(transition.generate_cypher_withstring(t_number, pathstring))
        cypherbuffer.append('\n'.join(with_parts))
        # SUM UP
        dvars = ['d{0}'.format(i) for i in range(len(self.transitions))]
        svars = ['Syn{0}'.format(i) for i in range(len(self.transitions))]
        dstring = ','.join(dvars)
        sstring = ','.join(svars)
        dsum = '+'.join(dvars)
        ssum = '+'.join(svars)
        sumup = '''WITH {0}, {1}, {2},\n {3} as TD,\n {4} as TS'''.format(pathstring, dstring, sstring, dsum, ssum)
        next_width = '''WITH {0}, TD, TS,'''.format(pathstring)
        getmin = ' min(TD) as minTD\n WHERE TD = minTD'
        rets = 'RETURN {0} ORDER BY TS ASC LIMIT 5'.format(pathstring)
        cypherbuffer.append(sumup)
        cypherbuffer.append(next_width)
        cypherbuffer.append(getmin)
        cypherbuffer.append(rets)
        return ['\n'.join(cypherbuffer)]


#########
#
#  Example Cypher queries.
#
#  These are the sorts of queries that we are trying to create with this class.
#
###

'''
MATCH 
q=(x:Concept{name: "Substance"})--
(w0:Concept{name:   "Gene"})-
[r0*1..2]-
(w1:Concept{name:   "Cell"})-
[r1*1..2]-
(w2:Concept{name:   "Phenotype"})--
(y:Concept{name:   "Disease"})
with q,x,y MATCH
p=(x:Concept)-[zebra*0..6]->()<-[macaroni*0..6]-(y:Concept)
where p=q
return p
'''


#Here is stashing a further upgrade that Patrick made to the query to allow for branches as well:
'''
MATCH 
q0=(a:Concept{name: "Substance"})--(:Concept{name: "Gene"})--(j:Concept{name: "Anatomy"}),
q1=(j)--(:Concept{name: "Cell"})--(b:Concept{name: "BiologicalProcess"}),
q2=(j)--(:Concept{name: "Phenotype"})--(c:Concept{name: "Disease"})
with j,a,b,c,q0,q1,q2
match p0=(a)-[ra0*0..2]->()<-[rj0*0..2]-(j),
p1=(j)-[rb1*0..2]->()<-[rj1*0..2]-(b),
p2=(j)-[rc2*0..2]->()<-[rj2*0..2]-(c)
where p0=q0 and p1=q1 and p2=q2 and not (length(rj0)>0 and length(rj1)>0 and length(rj2)>0)
return nodes(p0)+nodes(p1)+nodes(p2) as nodes, relationships(p0)+relationships(p1)+relationships(p2) as rels
'''
