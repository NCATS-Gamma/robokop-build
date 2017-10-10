import requests
import urllib
from ontobio.ontol_factory import OntologyFactory

def gene_get_disease(hgnc):
    ehgnc = urllib.parse.quote_plus(hgnc[0])
    r = requests.get('https://api.monarchinitiative.org/api/bioentity/gene/%s/diseases' % ehgnc).json()
    for association in r['associations']:
        obj = association['object']
    #TODO: Return smarter reps of edge, node
    objects = [ ('biolink',association['object']) for association in r['associations'] ]
    return objects

GENETIC_DISEASE='DOID:630'
MONOGENIC_DISEASE='DOID:0050177'

def gene_get_genetic_condition(gene):
    disease_relations = gene_get_disease(gene)
    ofactory = OntologyFactory()
    ont = ofactory.create('mondo')
    #This seems to be required to make the ontology actually load:
    _ = ont.get_level(0)
    relations = []
    for relation, obj in disease_relations:
        obj_id = obj['id']
        if ont.has_node(obj_id):
            obj_ids = [obj_id]
        else:
            obj_ids = ont.xrefs(obj_id, bidirectional=True)
        for obj_id in obj_ids:
            ancestors = ont.ancestors(obj_id)
            if GENETIC_DISEASE in ancestors:
                relations.append( ('biolink',obj_id) )
    return relations
