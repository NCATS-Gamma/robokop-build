import requests
import urllib
from mondo import Mondo
from reasoner.graph_components import KNode,KEdge
import logging

def gene_get_disease(gene_node):
    """Given a gene specified as an HGNC curie, return associated diseases. """
    #TODO: we're assuming that gene_node.identifier is a valid curie for calling inti biolink - validate
    ehgnc = urllib.parse.quote_plus(gene_node.identifier)
    logging.getLogger('application').debug('Biolink: %s' % ehgnc)
    print ('https://api.monarchinitiative.org/api/bioentity/gene/%s/diseases' % ehgnc)
    r = requests.get('https://api.monarchinitiative.org/api/bioentity/gene/%s/diseases' % ehgnc).json()
    edge_nodes = []
    #TODO:  Do I just want to suck in everything?  It's probably smarter, but for now it's mostly nulls
    #       and there's some stuff I'm completely unclear on (evidence graph).  In the long run, though,
    #       probably yes.
    for association in r['associations']:
        if 'publications' in association and association['publications'] is not None:
            pubs = [ {'id': pub['id']} for pub in association['publications'] ]
        else:
            pubs = []
        obj = KNode(association['object']['id'], 'D', association['object']['label'] )
        rel = { 'typeid': association['relation']['id'], 'label':association['relation']['label'] }
        props = { 'publications': pubs, 'relation':rel }
        edge = KEdge( 'biolink', 'queried', props )
        edge_nodes.append( (edge , obj ) )
    #TODO: WARN if no edges found?
    #TODO: DEBUG number of edges found / query.id
    return edge_nodes

def gene_get_genetic_condition(gene):
    """Given a gene specified as an HGNC curie, return associated genetic conditions.
    
    A genetic condition is specified as a disease that descends from a ndoe for genetic disease in MONDO."""
    disease_relations = gene_get_disease(gene)
    checker = Mondo()
    relations = []
    for relation, obj in disease_relations:
        is_genetic_condition, new_object_ids = checker.is_genetic_disease(obj)
        if is_genetic_condition:
            obj.properties['mondo_identifiers'] = new_object_ids
            relations.append( (relation,obj) )
    return relations

def test():
    """What do we get back for HBB"""
    print('hi')
    relations = gene_get_disease(('HGNC:4827',))
    checker = Mondo()
    for p, a in relations:
        igc, nid = checker.is_genetic_disease(a)
        print(a['id'], igc, nid)

def test_output():
    ehgnc = urllib.parse.quote_plus("HGNC:6136")
    r = requests.get('https://api.monarchinitiative.org/api/bioentity/gene/%s/diseases' % ehgnc).json()
    import json
    with open('testbiolink.json','w') as outf:
        json.dump(r, outf, indent=4)


if __name__ == '__main__':
    test_output()
