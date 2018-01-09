from greent.node_types import node_types, DRUG_NAME, DISEASE_NAME

class Transition():
    def __init__(self, last_type, next_type, min_path_length, max_path_length):
        self.in_type = last_type
        self.out_type = next_type
        self.min_path_length = min_path_length
        self.max_path_length = max_path_length
    def generate_reverse(self):
        return Transition(self.out_type, self.in_type, self.min_path_length, self.max_path_length)
    def get_fstring(self,ntype):
        if ntype == DRUG_NAME or ntype == DISEASE_NAME:
            return 'n{0}{{name:"{1}"}}'
        if ntype is None:
            return 'n{0}'
        else:
            return 'n{0}:{1}'
    def generate_cypher_pathstring(self, t_number):
        fstring = self.get_fstring( self.in_type )
        self.in_node = fstring.format( t_number, self.in_type )
        fstring = self.get_fstring( self.out_type )
        self.out_node = fstring.format( t_number+1, self.out_type )
        pstring = 'p{0}=({1})-[*{2}..{3}]->({4})'
        #TODO: how to set max path here.  It's our max_path, plus some slop for synonyms.  Assuming 1 synonym per translation (and some slop?)?
        return pstring.format( t_number, self.in_node, self.min_path_length, 2 * self.max_path_length + 2 , self.out_node )
    def generate_cypher_withstring(self,t_number, pathstring):
        withline = 'WITH {}'.format(pathstring)
        for i in range(t_number):
            withline += ', d{0}, Syn{0}'.format(i)
        withline += ',\n'
        #TODO: now synonym is a property, switch to use that rather than type.
        withline += '''reduce(weight=0, r in relationships(p{0}) | CASE type(r) WHEN "SYNONYM" THEN weight ELSE weight + 1 END ) as d{0},
reduce(weight=0, r in relationships(p{0}) | CASE type(r) WHEN "SYNONYM" THEN weight + 1 ELSE weight END ) as Syn{0}'''.format(t_number)
        if (self.min_path_length == self.max_path_length):
            withline += '\nWHERE d{0} = {1}'.format(t_number, self.min_path_length)
        else:
            withline += '\nWHERE d{0} >= {1} AND d{0} <= {2}'.format(t_number, self.min_path_length, self.max_path_length)
        return withline

class QueryDefinition():
    """Defines a query"""
    #TODO: start_type probably doesn't need its own property?
    #TODO: potential integration point with UI
    def __init__(self):
        self.start_values = None
        self.start_type   = None
        self.end_values   = None
        self.node_types   = []
        self.transitions  = []
        self.start_lookup_node = None
        self.end_lookup_node   = None
    def generate_left_query_def(self, i):
        """Generate a query definition starting at the left and moving in i steps
           input: 0 < i < len(transitions) """
        if i < 1 or i >= len(self.transitions):
            raise ValueError( "Invalid break point: {}".format(i) )
        left_def = QueryDefinition()
        left_def.start_values = self.start_values
        left_def.start_type   = self.start_type
        left_def.node_types   = self.node_types[:i+1]
        left_def.transitions  = self.transitions[:i]
        left_def.start_lookup_node = self.start_lookup_node
        return left_def
    def generate_right_query_def(self, i):
        """Generate a query definition starting at the right and going to a node i 
           steps from the left end. 
           input: 0 < i < len(transitions) 
           output: A query definition complementary to generate_left_query_def(i)
           """
        if i < 1 or i >= len(self.transitions):
            raise ValueError( "Invalid break point: {}".format(i) )
        right_def = QueryDefinition()
        right_def.start_values = self.end_values
        right_def.start_type   = self.node_types[-1]
        right_def.node_types   = self.node_types[i:]
        right_def.transitions  = self.transitions[i:]
        right_def.start_lookup_node = self.end_lookup_node
        right_def.node_types.reverse()
        right_def.transitions.reverse()
        right_def.transitions = [ t.generate_reverse() for t in right_def.transitions ]
        return right_def
    def generate_paired_query(self,i):
        return self.generate_left_query_def(i), self.generate_right_query_def(i)

class UserQuery():
    """This is the class that the rest of builder uses to interact with a query."""
    def __init__(self, start_values, start_type, lookup_node):
        """Create an instance of UserQuery. Takes a starting value and the type of that value"""
        self.definition = QueryDefinition()
        #Value for the original node
        self.definition.start_values = start_values
        self.definition.start_type   = start_type
        self.definition.end_values = None
        #The term used to create the initial point
        self.definition.start_lookup_node = lookup_node
        #List of user-level types that we must pass through
        self.add_node( start_type )
    def add_node(self,node_type):
        """Add a node to the node list, validating the type
           20180108: node_type may be None"""
        #Our start node is more specific than this...  Need to have another validation method
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
        #validate some inputs
        #TODO: subclass Exception
        if min_path_length > max_path_length:
            raise Exception('Maximum path length cannot be shorter than minimum path length')
        if self.definition.end_values is not None:
            raise Exception('Cannot add more transitions to a path with a terminal node')
        #Add the node to the type list
        self.add_node( next_type )
        #Add the transition
        t = Transition( self.definition.node_types[-2], next_type, min_path_length, max_path_length)
        self.definition.transitions.append(t)
        #Add the end_value
        if end_values is not None:
            self.definition.end_values = end_values
    def add_end_lookup_node(self, lookup_node):
        self.definition.end_lookup_node = lookup_node
    def compile_query(self, rosetta):
        """Based on the type of inputs that we have, create the appropriate form of query,
        and check that it can be satisfied by the typegraph"""
        self.query = None
        if self.definition.end_values is None:
            #this is a one sided graph
            self.query = OneSidedLinearUserQuerySet( self.definition )
        else:
            #this is a two sided graph, we need to check every possible split point. 
            #Temporarily, this does not include a single end-to-end path, but is always a pair of
            # one sided queries
            all_possible_query_defs = [self.definition.generate_paired_query(i) for i in range(1,len(self.definition.transitions))]
            all_possible_queries    = [TwoSidedLinearUserQuery(OneSidedLinearUserQuerySet(l),  
                                                               OneSidedLinearUserQuerySet(r) ) 
                                       for l,r in all_possible_query_defs ]
            self.query = TwoSidedLinearUserQuerySet()
            for query in all_possible_queries:
                self.query.add_query(query, rosetta)
        return self.query.compile_query(rosetta)
    def get_terminal_types(self):
        return self.query.get_terminal_types()
    def generate_cypher(self):
        return self.query.generate_cypher()
    def get_start_node(self):
        return self.query.get_start_node()
    def get_reversed(self):
        return self.query.get_reversed()
    def get_lookups(self):
        return self.query.get_lookups()
        

class TwoSidedLinearUserQuerySet():
    """A composition of multiple two sided linear queries."""
    def __init__(self):
        self.queries = []
    def add_query( self, query, rosetta ):
        if query.compile_query(rosetta):
            self.queries.append( query )
    def compile_query( self, rosetta ):
        #by construction, we only accept queries that compile so don't re-check
        return len(self.queries) > 0
    def get_terminal_types(self):
        return sum( [q.get_terminal_types() for q in self.queries], [] )
    def generate_cypher(self):
        return sum( [q.generate_cypher() for q in self.queries], [] )
    def get_start_node(self):
        return sum( [q.get_start_node() for q in self.queries], [] )
    def get_reversed(self):
        return sum( [q.get_reversed() for q in self.queries], [] )
    def get_lookups(self):
        return sum( [q.get_lookups() for q in self.queries], [] )
 

class TwoSidedLinearUserQuery():
    """Constructs a query that is fixed at either end.
    When this occurs, we are going to treat it as a pair of OneSidedLinearUserQueries that 
    extend inward from the end points and meet in the middle"""
    def __init__(self, left_query, right_query):
        """To construct a two sided query, pass in two one-sided query"""
        #TODO: we want creation of this object to be a bit more dynamic
        #if left_query.node_types[-1] != right_query.node_types[-1]:
        #    raise ValueError('The left and right queries must end with the same node type')
        self.query1 = left_query
        self.query2 = right_query
    def get_terminal_types( self ):
        return [self.query1.get_terminal_types()[0], self.query2.get_terminal_types()[0]]
    def generate_cypher(self):
        return self.query1.generate_cypher() + self.query2.generate_cypher()
    def get_start_node(self):
        return self.query1.get_start_node() + self.query2.get_start_node()
    def get_reversed(self):
        rleft = self.query1.get_reversed()
        rright = [True for r in self.query2.get_reversed() ]
        return rleft +rright
    def get_lookups(self):
        return self.query1.get_lookups() + self.query2.get_lookups()
    def compile_query(self,rosetta):
        """Determine whether there is a path through the data that can satisfy this query"""
        return self.query1.compile_query(rosetta) and self.query2.compile_query(rosetta)


class OneSidedLinearUserQuerySet():
    """A set of one-sided queries that will be run together.  Used to compose two sided queries"""
    def __init__(self, query_definition):
        self.lookup_node  = query_definition.start_lookup_node
        self.queries = []
        for svalue in query_definition.start_values:
            self.queries.append( OneSidedLinearUserQuery( svalue, query_definition ) )
    def get_lookups(self):
        return [self.lookup_node for i in self.queries ]
    def get_start_node(self):
        snodes = [ q.get_start_node() for q in self.queries ]
        return sum( snodes, [] )
    def get_terminal_types(self):
        ttypes=[ set(), set() ]
        for q in self.queries:
            qt = q.get_terminal_types()
            for i in (0,1):
                ttypes[i].update(qt[i])
        return ttypes
    def get_reversed(self):
        return [False for q in self.queries]
    def add_node(self,node_type):
        for q in self.queries:
            q.add_node(node_type)
    def add_transition(self, next_type, min_path_length=1, max_path_length=1, end_value=None):
        for q in self.queries:
            q.add_transition(next_type, min_path_length, max_path_length, end_value)
    def compile_query(self,rosetta):
        """Determine whether there is a path through the data that can satisfy this query"""
        #remove any queries that don't compile
        self.queries = list(filter( lambda q: q.compile_query( rosetta ), self.queries ))
        #is anything left?
        return len(self.queries) > 0
    def generate_cypher(self):
        cyphers = []
        for q in self.queries:
            cyphers += q.generate_cypher()
        return cyphers

class OneSidedLinearUserQuery():
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
        self.start_type  = query_definition.start_type
        self.node_types  = query_definition.node_types
        self.transitions = query_definition.transitions
    def get_start_node( self ):
        node = self.node_types[0]
        if node in (DISEASE_NAME, DRUG_NAME):
            return [ ('{0}:{1}'.format(node,self.start_value), node) ]
        return [ (self.start_value, node) ]
    def get_terminal_types( self ):
        """Returns a two element array.  The first element is a set of starting terminal types. 
        The second element is a set of ending terminal types"""
        return [set([self.node_types[0]]), set([self.node_types[-1]])]
    def get_reversed(self):
        return [False]
    def compile_query(self,rosetta):
        """Determine whether there is a path through the data that can satisfy this query"""
        programs = rosetta.type_graph.get_transitions(self.generate_cypher()[0])
        return len(programs) > 0
    def generate_cypher(self,end_value=None):
        """generate a cypher query to generate paths through the data sources. Optionally, callers can
        pass a specified end_value for the type-graph traversal."""
        cypherbuffer = ['MATCH']
        paths_parts = []
        for t_number, transition in enumerate(self.transitions):
            paths_parts.append( transition.generate_cypher_pathstring(t_number) )
        cypherbuffer.append( ',\n'.join(paths_parts) )
        cypherbuffer.append( 'WHERE' )
        curie_prefix = self.start_value.split(':')[0]
        cypherbuffer.append('n0.name="{}" AND'.format(curie_prefix))
        if end_value is not None:
            end_index = len(self.transitions)
            curie_prefix = end_value.split(':')[0]
            cypherbuffer.append('n{}.name="{}" AND'.format(end_index, curie_prefix))
        # NONE (r in relationships(p0) WHERE type(r) = "UNKNOWN"
        no_unknowns = []
        for t_number, transition in enumerate(self.transitions):
            no_unknowns.append( 'NONE (r in relationships(p{}) WHERE type(r) = "UNKNOWN")'.format(t_number) )
        cypherbuffer.append( '\nAND '.join(no_unknowns) )
        # WITH (list of paths) (previous list of lengths) reduce () as dx, reduce() as synx WHERE [conditions on dx]
        with_parts = []
        pathstring = ','.join([ 'p{0}'.format(i) for i in range(len(self.transitions)) ] )
        for t_number, transition in enumerate(self.transitions):
            with_parts.append( transition.generate_cypher_withstring(t_number, pathstring) )
        cypherbuffer.append( '\n'.join(with_parts) )
        #SUM UP
        dvars = [ 'd{0}'.format(i) for i in range(len(self.transitions)) ]
        svars = [ 'Syn{0}'.format(i) for i in range(len(self.transitions)) ] 
        dstring = ','.join( dvars )
        sstring = ','.join( svars )
        dsum = '+'.join( dvars )
        ssum = '+'.join( svars )
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

#This example query shows how to go from Disease name to Disease, but having to go through one other kind of node first (since d1 > 1)
q1='''MATCH  p=(startNode{name:"NAME.DISEASE"})-[*1..6]->(endNode:Disease)
      WHERE NONE (r in relationships(p) WHERE type(r) = "UNKNOWN")
      WITH p,
           reduce(weight=0, r in relationships(p) | CASE type(r)
                                                   WHEN "SYNONYM" THEN weight
                                                   ELSE weight + 1
                                                   END 
           ) as d1,
           reduce(weight=0, r in relationships(p) | CASE type(r)
                                                    WHEN "SYNONYM" THEN weight + 1
                                                    ELSE weight 
           END  ) as Syn1
      WHERE d1 > 1
      RETURN p AS shortestPath, d1, Syn1
      ORDER BY d1 ASC, Syn1 ASC
      LIMIT 5'''
#Go from Disease to Gene to Pathway, Nothing in between
q2='''MATCH  p1=(n1:Disease)-[*1..4]->(n2:Gene), p2=(n2:Gene)-[*1..4]->(n3:Pathway)
      WHERE NONE (r in relationships(p1) WHERE type(r) = "UNKNOWN")
      AND NONE (r in relationships(p2) WHERE type(r) = "UNKNOWN")
      WITH p1, p2,
           reduce(weight=0, r in relationships(p1) | CASE type(r)
                                                   WHEN "SYNONYM" THEN weight
                                                   ELSE weight + 1
                                                   END 
           ) as d1,
           reduce(weight=0, r in relationships(p1) | CASE type(r)
                                                    WHEN "SYNONYM" THEN weight + 1
                                                    ELSE weight 
           END  ) as Syn1
      WHERE d1 = 1
      WITH p1, p2, d1, Syn1,
           reduce(weight=0, r in relationships(p2) | CASE type(r)
                                                   WHEN "SYNONYM" THEN weight
                                                   ELSE weight + 1
                                                   END 
           ) as d2,
           reduce(weight=0, r in relationships(p2) | CASE type(r)
                                                    WHEN "SYNONYM" THEN weight + 1
                                                    ELSE weight 
           END  ) as Syn2
      WHERE d2 = 1
      WITH p1, p2, d1, d2, Syn1, Syn2,
           d1 + d2 as TD,
           Syn1 + Syn2 as TS
      RETURN p1 , p2, d1, Syn1, d2, Syn2, TD, TS
      ORDER BY TD ASC, TS ASC
      LIMIT 5'''

