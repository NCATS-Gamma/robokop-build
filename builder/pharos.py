import requests
import logging
from csv import DictReader
from graph_components import KNode,KEdge

def translate(subject_node):
    """Convert a subject with a DOID into a Pharos Disease ID"""
    #TODO: This relies on a pretty ridiculous caching of a map between pharos ids and doids.  
    #      As Pharos improves, this will not be required, but for the moment I don't know a better way.
    pmap = {}
    with open('pharos.id.txt','r') as inf:
        rows = DictReader(inf,dialect='excel-tab')
        for row in rows:
            if row['DOID'] != '':
                pmap[row['DOID']] = row['PharosID']
    doid = subject_node.identifier
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
    """Given a subject node (with a DOID as the identifier), return targets"""
    pharosid = translate(subject)
    r = requests.get('https://pharos.nih.gov/idg/api/v1/diseases(%s)?view=full' % pharosid)
    result = r.json()
    original_edge_nodes=[]
    for link in result['links']:
        if link['kind'] != 'ix.idg.models.Target':
            logging.getLogger('application').info('Pharos disease returning new kind: %s' % link['kind'])
        else:
            pharos_target_id = int(link['refid'])
            #link['properties'] is a list rather than a dict
            pharos_edge = KEdge( 'pharos', 'queried', {'properties': link['properties']} )
            original_edge_nodes.append( (pharos_edge, pharos_target_id) )
    #Pharos returns target ids in its own numbering system. Collect other names for it.
    resolved_edge_nodes = []
    for edge, pharos_target_id  in original_edge_nodes:
        hgnc = get_target_hgnc(pharos_target_id)
        if hgnc is not None:
            hgnc_node = KNode(hgnc, 'G')
            resolved_edge_nodes.append((edge,hgnc_node))
        else:
            logging.getLogger('application').warn('Did not get HGNC for pharosID %d' % pharos_target_id)
    return resolved_edge_nodes

#Poking around on the website there are about 10800 ( a few less )
def build_disease_translation():
    """Write to disk a table mapping Pharos disease ID to DOID (and other?) so we can reverse lookup"""
    with open('pharos.id.txt','w') as pfile:
        pfile.write('PharosID\tDOID\n')
        for pharosid in range(1,10800):
            r = requests.get('https://pharos.nih.gov/idg/api/v1/diseases(%d)/synonyms' % pharosid).json()
            doids = []
            for synonym in r:
                if synonym['label'] == 'DOID':
                    doids.append(synonym['term'])
            if len(doids) > 1:
                print(doids)
                import json
                print( json.dumps(r,indent=4) )
                exit()
            elif len(doids) == 0:
                doids.append('')
            pfile.write('%d\t%s\n' % (pharosid, doids[0]))

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
    build_disease_translation()
