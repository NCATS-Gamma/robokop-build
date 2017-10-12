import requests
import logging

def translate(subject):
    """Convert a subject with a DOID into a Pharos Disease ID"""
    #TODO: Import from PHAROS
    pmap = {'DOID:1470': 455, 'DOID:4325': 2742, 'DOID:11476': 4885, 'DOID:12365': 202, 'DOID:10573': 807, \
            'DOID:9270': 6493, 'DOID:526':7468, 'DOID:1498':1887, 'DOID:13810': 10692}
    doid = subject[0]
    return pmap[doid]


def get_target_hgnc(target_id):
    """Convert a pharos target id into an HGNC ID.

    The call does not return the actual name for the gene, so we do not provide it.
    There are numerous other synonyms that we could also cache, but I don't see much benefit here"""
    r = requests.get('https://pharos.nih.gov/idg/api/v1/targets(%d)/synonyms' % target_id)
    result = r.json()
    for synonym in result:
        if synonym['label'] == 'HGNC':
            return synonym['term']
    return None

#TODO: assuming a DOID, not really valid
#TODO: clean up, getting ugly
def disease_get_gene(subject):
    """Given a subject node (with a DOID), return targets"""
    pharosid = translate(subject)
    r = requests.get('https://pharos.nih.gov/idg/api/v1/diseases(%d)?view=full' % pharosid)
    result = r.json()
    original_edge_nodes=[]
    for link in result['links']:
        if link['kind'] != 'ix.idg.models.Target':
            logging.getLogger('application').info('Pharos disease returning new kind: %s' % link['kind'])
        else:
            pharos_target_id = int(link['refid'])
            pharos_properties = { 'edge_source':'pharos', 'properties':link['properties'] }
            original_edge_nodes.append( (pharos_properties, pharos_target_id) )
    #Pharos returns target ids in its own numbering system. Collect other names for it.
    resolved_edge_nodes = []
    for edge, pharos_target_id  in original_edge_nodes:
        hgnc = get_target_hgnc(pharos_target_id)
        if hgnc is not None:
            resolved_edge_nodes.append((edge,(hgnc,{})))
        else:
            logging.getLogger('application').warn('Did not get HGNC for pharosID %d' % pharos_target_id)
    return resolved_edge_nodes

#Poking around on the website there are about 10800 ( a few less )
def build_disease_translation():
    """Write to disk a table mapping Pharos disease ID to DOID (and other?) so we can reverse lookup"""
    pass

def test_disese_gene_for_output():
    """Call a function so that we can examine the output"""
    pharosid=455
    r = requests.get('https://pharos.nih.gov/idg/api/v1/diseases(%d)?view=full' % pharosid)
    result = r.json()
    import json
    with open('testpharos.txt','w') as outf:
        json.dump(result,outf,indent=4)

def test_hgnc_for_output():
    """Call a function so that we can examine the output"""
    pharosid=91
    r = requests.get('https://pharos.nih.gov/idg/api/v1/targets(%d)/synonyms' % pharosid)
    result = r.json()
    import json
    with open('testpharos.txt','w') as outf:
        json.dump(result,outf,indent=4)
    
if __name__ == '__main__':
    test_hgnc_for_output()
