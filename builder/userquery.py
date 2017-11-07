from reasoner.node_types import node_types, DRUG_NAME, DISEASE_NAME

#Allowed user-level types
#TODO: Line up with steve, have in one place?

class Transition():
    def __init__(self, last_type, next_type, min_path_length, max_path_length):
        self.in_type = last_type
        self.out_type = next_type
        self.min_path_length = min_path_length
        self.max_path_length = max_path_length
    def get_fstring(self,ntype):
        if ntype == DRUG_NAME or ntype == DISEASE_NAME:
            return 'n{0}{{name:"{1}"}}'
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

class LinearUserQuery():
    """A class for constructing linear paths through a series of knowledge sources.

    We have a set of knowledge sources that can be considered as a graph.  Each edge in the graph represents
    an endpoint in the sources (i.e. a service call) that takes (usually) one node and returns one or more nodes.
    These endpoints are typed, such as a service that takes drug ids and returns genes ids.

    To execute queries, we need to define a path through this graph, but the user should not be tasked with this.
    Instead, the user generates a high-level description of the kind of path that they want to execute, and
    it gets turned into a cypher query on the knowledge source graph.  

    This class represents the user-level query"""
    def __init__(self, start_value, start_type):
        """Create an instance of UserQuery. Takes a starting value and the type of that value"""
        #Value for the original node
        self.start_value = start_value
        self.end_value = None
        #List of user-level types that we must pass through
        self.node_types=[ ]
        self.add_node( start_type )
        self.transitions = [ ]
    def get_start_node( self ):
        node = self.node_types[0]
        return '{0}:{1}'.format(node,self.start_value), node
    def get_terminal_types( self ):
        return self.node_types[0], self.node_types[-1]
    def add_node(self,node_type):
        """Add a node to the node list, validating the type"""
        if node_type not in node_types:
            raise Exception('node type must be one of reasoner.node_types')
        self.node_types.append(node_type)
    def add_transition(self, next_type, min_path_length=1, max_path_length=1, end_value=None):
        """Add another required node type to the path.

        When a new node is added to the user query, the user is asserting that the returned path must go through a node of this type.
        The default is that the next node should be directly related to the previous. That is, no other node types should be between 
        the previous node and the current node.   There may be other nodes, but they will represent synonyms of the previous or
        current node.  This is defined using the max_path_length input, which defaults to 1.

        On the other hand, a user may wish to define that some number of other node types must be between one node and another.
        This can be specified by the min_path_length, which also defaults to 1.  If indirect edges are demanded, this parameter is set
        higher.

        If this is the final transition, a value for the terminal node may be added.  Attempting to add more transitions after setting
        an end value will result in an exception.  If this is the terminal node, but it does not have a specified value, then no 
        end_value needs to be specified.

        arguments: next_type: type of the output node from the transition.  Must be an element of reasoner.node_types.
                   min_path_length: The minimum number of non-synonym transitions to get from the previous node to the added node
                   max_path_length: The maximum number of non-synonym transitions to get from the previous node to the added node
                   end_value: Value of this node (if this is the terminal node, otherwise None)
        """
        #validate some inputs
        #TODO: subclass Exception
        if min_path_length > max_path_length:
            raise Exception('Maximum path length cannot be shorter than minimum path length')
        if self.end_value is not None:
            raise Exception('Cannot add more transitions to a path with a terminal node')
        #Add the node to the type list
        self.add_node( next_type )
        #Add the transition
        t = Transition( self.node_types[-2], next_type, min_path_length, max_path_length)
        self.transitions.append(t)
    def generate_cypher(self):
        """generate a cypher query to generate paths through the data sources"""
        cypherbuffer = ['MATCH']
        # p0=(n0{name:"NAME.DISEASE})-[*1..6]->(n1:Disease)
        paths_parts = []
        for t_number, transition in enumerate(self.transitions):
            paths_parts.append( transition.generate_cypher_pathstring(t_number) )
        cypherbuffer.append( ',\n'.join(paths_parts) )
        cypherbuffer.append( 'WHERE' )
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
        return '\n'.join(cypherbuffer)


def test_1():
    """Try to generate a Question 1 style query using this general device and fully specifying path."""
    from reasoner.node_types import DISEASE, GENE, GENETIC_CONDITION
    query = LinearUserQuery("Ebola infection", DISEASE_NAME )
    query.add_transition(DISEASE)
    query.add_transition(GENE)
    query.add_transition(GENETIC_CONDITION)
    cypher = query.generate_cypher()
    print(cypher)

def test_2():
    """Try to generate a Question 1 style query using this general device without fully specifying path."""
    from reasoner.node_types import DISEASE, GENETIC_CONDITION
    query = LinearUserQuery("Ebola infection", DISEASE_NAME )
    query.add_transition(DISEASE)
    query.add_transition(GENETIC_CONDITION, min_path_length=2, max_path_length=2)
    cypher = query.generate_cypher()
    print(cypher)
    
def test_3a():
    """Try to generate a Question 2 style query using this general device fully specifying path."""
    from reasoner.node_types import DRUG, GENE, PROCESS, CELL, ANATOMY
    query = LinearUserQuery("imatinib", DRUG_NAME )
    query.add_transition(DRUG)
    query.add_transition(GENE)
    query.add_transition(PROCESS)
    query.add_transition(CELL)
    query.add_transition(ANATOMY)
    cypher = query.generate_cypher()
    print(cypher)

def test_3b():
    """Try to generate the other half of a Q2 query"""
    from reasoner.node_types import DISEASE, PHENOTYPE, ANATOMY
    query = LinearUserQuery("asthma", DISEASE_NAME )
    query.add_transition(DISEASE)
    query.add_transition(PHENOTYPE)
    query.add_transition(ANATOMY)
    cypher = query.generate_cypher()
    print(cypher)
 
if __name__ == '__main__':
    print('---Query 1: Specified---------')
    test_1()
    print('---Query 1: Un-specified---------')
    test_2()
    print('---Query 2: Part 1------------')
    test_3a()
    print('---Query 2: Part 2------------')
    test_3b()

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

