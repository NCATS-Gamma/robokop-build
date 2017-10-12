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
        """Given an object and a term in MONDO, determine whether the term is an ancestor of the object.
        
        The object is a KNode representing a disease.
        Some complexity arises because the identifier for the node may not be the id of the concept in mondo.
        the XRefs in mondo are checked for the object if it is not intially found, but this may return more 
        than one entity if multiple mondo entries map to the same.  

        Returns: boolean representing whether any mondo objects derived from the subject have the term as an
                         ancestor.
                 The list of Mondo identifiers for the object, which have the term as an ancestor"""
        #TODO: The return signature is funky, fix it.
        obj_id = obj.identifier
        if self.ont.has_node(obj_id):
            obj_ids = [obj_id]
        else:
            obj_ids = self.ont.xrefs(obj_id, bidirectional=True)
        return_objects=[]
        for obj_id in obj_ids:
            ancestors = self.ont.ancestors(obj_id)
            if GENETIC_DISEASE in ancestors:
                return_objects.append( obj_id )
        return len(return_objects) > 0, return_objects
    def is_genetic_disease(self,obj):
        """Checks mondo to find whether the subject has DOID:630 as an ancestor"""
        return self.has_ancestor(obj, GENETIC_DISEASE)
    def is_monogenic_disease(self,obj):
        """Checks mondo to find whether the subject has DOID:0050177 as an ancestor"""
        return self.has_ancestor(obj, MONOGENIC_DISEASE)
