from functools import singledispatch

class KNode():
    """Used as the node object in KnowledgeGraph.
    
    Instances of this class can be passed to WorldGraph/greent as query subjects/objects."""
    def __init__(self,identifier,node_type,label=None):
        self.identifier = identifier
        self.label = label
        self.node_type = node_type
        #This is only going to make sense for linear paths...Need to rethink probably
        self.layer_number = None
        self.properties = {}
    def __hash__(self):
        """Class needs __hash__ in order to be used as a node in networkx"""
        return self.identifier.__hash__()
    def to_json(self):
        """Used to serialize a node to JSON."""
        #The decorator makes sure this gets called in JSON encoding
        j = { 'identifier': self.identifier, \
              'node_type' : self.node_type }
        if self.layer_number is not None:
            j['layer_number'] = self.layer_number
        for key in self.properties:
            j[key] = self.properties[key]
        return j
    def get_shortname(self):
        """Return a short user-readable string suitable for display in a list"""
        if self.label is not None:
            return '%s (%s)' % (self.label, self.identifier)
        return self.identifier


class KEdge():
    """Used as the edge object in KnowledgeGraph.

    Instances of this class should be returned from worldgraph/greenT"""
    def __init__(self):
        pass
        
@singledispatch
def elements_to_json(x):
    """Used by default in dumping JSON. For use by json.dump; should not usually be called by users."""
    #The singledispatch decorator allows us to register serializers in our edge and node classes.
    return str(x)
 
@elements_to_json.register(KNode)
def node_to_json(knode):
    """Routes JSON serialization requests to KNode member function.  Not for external use."""
    return knode.to_json()


