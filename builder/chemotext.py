from greent.chemotext import Chemotext
from greent.oxo import OXO
import json

def convert_to_mesh(term):
    """Use OXO to covnvert an id(doid, etc) to MeSH"""
    oxo = OXO()
    response = oxo.query([ term ])
    #ugly, and probably wrong
    search_results = response['_embedded']['searchResults'][0]['mappingResponseList']
    meshes = []
    for result in search_results:
        if result['targetPrefix'] == 'MeSH':
            meshes.append( result )
    return meshes

def term_to_term(term_a,term_b, limit = 10):
    """Given two terms, find articles in chemotext that connect them"""
    meshes_a = convert_to_mesh(term_a)
    meshes_b = convert_to_mesh(term_b)
    ctext = Chemotext( )
    articles=[]
    for ma in meshes_a:
        label_a = ma['label']
        for mb in meshes_b:
            label_b = mb['label']
            response = ctext.query( query="MATCH (d:Term)-[r1]-(a:Art)-[r2]-(t:Term) WHERE d.name='%s' AND t.name='%s' RETURN a LIMIT %d" % (label_a, label_b, limit))
            for result in response['results']:
                for data in result['data']:
                    articles += data['row']
    return 'chemotext',  articles

if __name__ == '__main__':
    print( term_to_term('DOID:4325', 'DOID:14504') )
    #print term_to_term('DOID:4325', 'http://www.orpha.net/ORDO/Orphanet_646')
