import json
import logging
from greent.graph_components import KEdge
from greent import node_types
import mesh

def get_supporter(greent):
    return ChemotextSupport(greent)

CHEMOTEXT_MESH_KEY = 'chemotext_mesh_label'

class ChemotextSupport():

    def __init__(self,greent):
        self.greent = greent
        self.ctext = greent.chemotext

    def prepare(self,nodes):
        mesh.add_mesh( nodes, self.greent )
        self.add_chemotext_terms( nodes )

    def add_chemotext_terms(self,nodes):
        """For each mesh term in a node, find out what chemotext calls that thing so we can query for it"""
        for node in nodes:
            for mesh_info in node.mesh_identifiers:
                label = mesh_info['label']
                cterm = self.ctext.get_chemotext_term( label )
                if cterm is None:
                    logging.getLogger('application').warn("Cannot find chemotext synonym for %s (%s)" % (label,mesh_info['curie']))
                else:
                    logging.getLogger('application').debug('node: {}, chemotext: {}'.format(node.identifier, cterm) )
                    mesh_info[ CHEMOTEXT_MESH_KEY ] = cterm

    def get_mesh_labels(self,node):
        labels = set()
        mids = node.mesh_identifiers
        for mid in mids:
            if CHEMOTEXT_MESH_KEY in mid:
                labels.add(mid[CHEMOTEXT_MESH_KEY])
        return labels

    def term_to_term(self,node_a,node_b,limit = 10000):
        """Given two terms, find articles in chemotext that connect them, and return as a KEdge.
        If nothing is found, return None"""
        meshes_a = self.get_mesh_labels(node_a)
        meshes_b = self.get_mesh_labels(node_b)
        articles=[]
        from datetime import datetime
        start = datetime.now()
        for label_a in meshes_a:
            for label_b in meshes_b:
                response = self.ctext.query( query="MATCH (d:Term)-[r1]-(a:Art)-[r2]-(t:Term) WHERE d.name='%s' AND t.name='%s' RETURN a LIMIT %d" % (label_a, label_b, limit))
                for result in response['results']:
                    for data in result['data']:
                        articles += data['row']
        end = datetime.now()
        logging.getLogger('application').debug('chemotext: {} to {}: {} ({})'.format(meshes_a, meshes_b, len(articles), end-start))
        if len(articles) > 0:
            ke= KEdge( 'chemotext', 'term_to_term', { 'publications': articles }, is_support = True )
            ke.source_node = node_a
            ke.target_node = node_b
            return ke
        return None


def test():
    from greent.rosetta import Rosetta
    rosetta = Rosetta()
    gt = rosetta.core
    support = ChemotextSupport(gt)
    from greent.graph_components import KNode
    node = KNode('HP:0000964', node_type = node_types.PHENOTYPE, label='Eczema')
    node.mesh_identifiers.append( { 'curie': 'MeSH:D004485', 'label': 'Eczema' } )
    support.add_chemotext_terms( [node] )
    import json
    print( json.dumps( node.mesh_identifiers[0] ,indent=4) )

if __name__ == '__main__':
    test()
