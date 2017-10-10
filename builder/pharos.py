import requests

def translate(subject):
    """Convert a subject with a DOID into a Pharos Disease ID"""
    #TODO: Import from PHAROS
    pmap = {'DOID:1470': 455, 'DOID:4325': 2742, 'DOID:11476': 4885}
    doid = subject[0]
    return pmap[doid]


def get_target_hgnc(target_id):
    r = requests.get('https://pharos.nih.gov/idg/api/v1/targets(%d)/synonyms' % target_id)
    result = r.json()
    for synonym in result:
        if synonym['label'] == 'HGNC':
            return synonym['term']
    return None

#TODO: assuming a DOID, not really valid
def disease_get_gene(subject):
    """Given a subject node (with a DOID), return targets"""
    pharosid = translate(subject)
    r = requests.get('https://pharos.nih.gov/idg/api/v1/diseases(%d)?view=full' % pharosid)
    result = r.json()
    targetids=[]
    for link in result['links']:
        if link['kind'] != 'ix.idg.models.Target':
            print ('new things. waaa %s' % link['kind'])
        else:
            targetids.append(int(link['refid']))
    relations = []
    for tid in targetids:
        hgnc = get_target_hgnc(tid)
        if hgnc is not None:
            relations.append(('pharos',hgnc))
    return relations
