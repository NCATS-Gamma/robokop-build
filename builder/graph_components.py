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
    def get_exportable(self):
        """Returns information to make a simpler node in networkx.  Helps with finicky graphml writer"""
        export_properties = { 'identifier'   : self.identifier, \
                              'node_type'    : self.node_type,  \
                              'layer_number' : self.layer_number }
        if self.label is not None:
            export_properties['label'] = self.label
        for key in self.properties:
            export_properties[key] = 'See JSON for details'
        return self.get_shortname(), export_properties


class KEdge():
    """Used as the edge object in KnowledgeGraph.

    Instances of this class should be returned from worldgraph/greenT"""
    def __init__(self, edge_source, edge_type, properties = None):
        self.edge_source = edge_source
        self.edge_type = edge_type
        if properties is not None:
            self.properties = properties
        else:
            self.properties = {}
    def to_json(self):
        """Used to serialize a node to JSON."""
        j = { 'edge_source' : self.edge_source, \
              'edge_type'   : self.edge_type }
        for key in self.properties:
            j[key] = self.properties[key]
        return j
    def get_exportable(self):
        """Returns information to make a simpler node in networkx.  Helps with finicky graphml writer"""
        export_properties = { 'edge_type'   : self.edge_type,  \
                              'edge_source' : self.edge_source }
        for key in self.properties:
            export_properties[key] = 'See JSON for details'
        return export_properties

  


##
# We want to be able to serialize our knowledge graph to json.  That means being able to serialize KNode/KEdge.
# We could sublcass JSONEncoder (and still might), but for now, this set of functions allows the default
# encoder to find the functions that return serializable versions of KNode and KEdge
##

@singledispatch
def elements_to_json(x):
    """Used by default in dumping JSON. For use by json.dump; should not usually be called by users."""
    #The singledispatch decorator allows us to register serializers in our edge and node classes.
    return str(x)
 
@elements_to_json.register(KNode)
def node_to_json(knode):
    """Routes JSON serialization requests to KNode member function.  Not for external use."""
    return knode.to_json()

@elements_to_json.register(KEdge)
def node_to_json(kedge):
    """Routes JSON serialization requests to KEdge member function.  Not for external use."""
    return kedge.to_json()

# END JSON STUFF

