from ontobio.ontol_factory import OntologyFactory

GENETIC_DISEASE='DOID:630'
MONOGENIC_DISEASE='DOID:0050177'

class Mondo():
    """Class to hold/query the mondo ontology""" 
    def __init__(self):
        ofactory = OntologyFactory()
        self.ont = ofactory.create('mondo')
        #This seems to be required to make the ontology actually load:
        _ = self.ont.get_level(0)
    def has_ancestor(self,obj, term):
        #obj_id = obj['id']
        obj_id = obj[0]
        if self.ont.has_node(obj_id):
            obj_ids = [obj_id]
        else:
            obj_ids = self.ont.xrefs(obj_id, bidirectional=True)
        for obj_id in obj_ids:
            ancestors = self.ont.ancestors(obj_id)
            if GENETIC_DISEASE in ancestors:
                return True,obj_id
        return False, obj_id
    def is_genetic_disease(self,obj):
        return self.has_ancestor(obj, GENETIC_DISEASE)
    def is_monogenic_disease(self,obj):
        return self.has_ancestor(obj, MONOGENIC_DISEASE)
