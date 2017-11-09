from greent import node_types
import logging

def add_mesh( nodes, greent ):
    """For each node, attempt to add mesh terms"""
    for node in nodes:
        add_mesh_to_node(node, greent)

def query_oxo( node, greent , distance=2):
    response = greent.oxo.query([ node.identifier ], distance=distance)
    search_results = response['_embedded']['searchResults'][0]['mappingResponseList']
    added = False
    for result in search_results:
        if result['targetPrefix'] == 'MeSH':
            added = True
            node.mesh_identifiers.append( result )
    return added

def add_mesh_to_node( node, greent ):
    split_curie = node.identifier.split(':')
    if greent.oxo.is_valid_curie_prefix( split_curie[0] ):
        added = query_oxo(node, greent)
        if not added:
            added = query_oxo(node, greent, distance=3)
            if not added:
                logging.getLogger('application').warn('No MeSH ID found for term: %s' % node.identifier)
                print(node.identifier)
    elif node.identifier.startswith('NAME.'):
        #We don't want mesh terms for these nodes - they represent query inputs, not real identified entities.
        return
    elif node.identifier.startswith('PUBCHEM'):
        #TODO:
        #We don't currently have a great way to convert pubchem to mesh.  We're going to try to just use the 
        # label (drugname) and hope for the best.
        node.mesh_identifiers.append( {'curie': '', 'label': node.label} )
    else:
        print( 'BAD CURIE:',split_curie[0] )

