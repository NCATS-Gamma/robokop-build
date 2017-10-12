from greent.chemotext import Chemotext
from greent.oxo import OXO
import json
import logging

def OXOdise_term(term):
    """Convert IRIs into CURIEs.
    
    Sometimes biolink or other sources will give an id like: http://purl.obolibrary.org/obo/OMIM_603903. 
    OXO expects: OMIM:603903.
    At least for the ones we've seen so far, the format has been that the last element in the url is
    the curie, but with : replaced by _."""
    if not term.startswith('http'):
        return term
    iri_term = term.split('/')[-1]
    if iri_term.count('_') != 1:
        logging.getLogger('application').warn('Invalid term for OXO: %s' % term)
        return term
    return ':'.join(iri_term.split('_'))

def convert_to_mesh(term):
    """Use OXO to covnvert an id(doid, etc) to MeSH"""
    #Check to see if we already have a MeSH curie
    if term[:5].upper() == 'MESH':
        return [term]
    #sometimes terms are not good for OXO, like http://purl.obolibrary.org/obo/OMIM_603903. OXO expects OMIM:603903
    term = OXOdise_term(term)
    oxo = OXO()
    response = oxo.query([ term ])
    #ugly, and probably wrong
    search_results = response['_embedded']['searchResults'][0]['mappingResponseList']
    meshes = []
    for result in search_results:
        if result['targetPrefix'] == 'MeSH':
            meshes.append( result )
    if len(meshes) == 0:
        logging.getLogger('application').warn('No MeSH ID found for term: %s' % term)
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
