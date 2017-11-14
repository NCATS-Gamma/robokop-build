import json
import os
import logging
from greent.graph_components import KEdge
from greent import node_types


def get_supporter(greent):
    return CDWSupport(greent)

class CDWSupport():

    def __init__(self,greent):
        self.oxo = greent.oxo
        self.total = 269332
        self.read_icd9()

    def prepare(self,nodes):
        for node in nodes:
            if node.node_type == node_types.DISEASE or node.node_type == node_types.GENETIC_CONDITION:
                split_curie = node.identifier.split(':')
                if self.oxo.is_valid_curie_prefix( split_curie[0] ):
                    results = self.oxo.get_specific_synonym_expanding( node.identifier, 'ICD9CM' )
                    if len(results) == 0:
                        logging.getLogger('application').warn('No ICD9 found for term: %s' % node.identifier)
                    else:
                        for r in results:
                            logging.getLogger('application').debug('ICD9 for {}: {}'.format( node.identifier, r['curie']))
                            if ( '-' in r['curie'] ):
                                logging.getLogger('application').warn('ICD9 has a dash: {}'.format(r['curie']) )
                            node.synonyms.add( r['curie'] )

    def read_icd9(self):
        #TODO: see that the files are available or pull them
        fname = os.path.join( os.path.dirname(__file__), 'AllDxCounts.txt')
        self.icd9_codes=set()
        with open(fname, 'r') as infile:
            h = infile.readline()
            for line in infile:
                x = line.strip().split('|')
                icd_code = x[0]
                self.icd9_codes.add(icd_code)
        self.icd9_paircounts = {}
        fname = os.path.join( os.path.dirname(__file__), 'ICD_Combo_Chi2.txt')
        with open(fname,'r') as infile:
            h = infile.readline()
            for line in infile:
                x = line.strip().split('\t')
                k1 = ( x[0], x[1] )
                k2 = ( x[1], x[0] )
                data = {
                'c1' : x[3],
                'c2' : x[4],
                'c'  : x[6],
                'e'  : float(x[3]) * float(x[4]) / self.total,  #expected counts
                'p'  : x[9]}
                self.icd9_paircounts[k1] = data
                self.icd9_paircounts[k2] = data

    def make_edge(self,cooc_list):
        k,c = cooc_list[0]
        #TODO: fix this up with details
        c[ 'icd9': list(k) ]
        ke= KEdge( 'cdw', 'term_to_term', c,  is_support = True )
        ke.source_node = node_a
        ke.target_node = node_b
        return ke

    def term_to_term(self,node_a,node_b,limit = 10000):
        """Given two diseases, check the co-occurrence """
        icd9_a = list(filter( lambda x: x.startswith('ICD9'), node_a.synonyms ) )
        icd9_b = list(filter( lambda x: x.startswith('ICD9'), node_b.synonyms ) )
        if (len(icd9_a) == 0)  or (len(icd9_b) == 0):
            #can't do co-occurence unless we get icd9 codes
            return
        co_occurrences = []
        for icd9a in icd9_a:
            if icd9a not in icd9_codes():
                logging.getLogger('application').debug('Dont have data for {}'.format(icd9a))
                continue
            for icd9b in icd9_b:
                if icd9b not in icd9_codes():
                    logging.getLogger('application').debug('Dont have data for {}'.format(icd9b))
                    continue
                #Now we have nodes that both have ICD9 codees and the both map to our results!
                k = (icd9a, icd9b)
                if k not in icd9_paircounts:
                    #There were less than 11 shared counts.
                    co_occurences.append( (k, {'c1': None, 'c2': None, 'c': '<11', 'p':None}) )
                else:
                    co_occurences.append( (k, icd9_paircounts[k] ) )
        if len(co_occurences) > 0:
            return self.make_edge(co_occurences)
        return None

