from pprint import PrettyPrinter
from greent.client import GraphQL
from collections import namedtuple

translator = GraphQL ("https://stars-app.renci.org/greent/graphql")    
Translation = namedtuple ('Translation', [ 'thing', 'domain_a', 'domain_b', 'description' ])
Translation.__new__.__defaults__ = (None, None, None, None, '')
translations = [
#    Translation ("Imatinib", "http://chem2bio2rdf.org/drugbank/resource/Generic_Name", "http://chem2bio2rdf.org/uniprot/resource/gene", "Drug->Target"), \
#    Translation ("CDC25A", "http://chem2bio2rdf.org/uniprot/resource/gene", "http://chem2bio2rdf.org/kegg/resource/kegg_pathway", "Target->Pathway"),\
#    Translation ("CACNA1A", "http://chem2bio2rdf.org/uniprot/resource/gene", "http://pharos.nih.gov/identifier/disease/name", "Target->Disease"), \
#    Translation ("Cerebellar Ataxia", "http://pharos.nih.gov/identifier/disease/name", "http://chem2bio2rdf.org/uniprot/resource/gene", "Disease->Target"), \
    Translation ("Asthma", "http://identifiers.org/mesh/disease/name", "http://identifiers.org/mesh/drug/name", "Disease->Drug"), \
#    Translation ("DOID:2841", "http://identifiers.org/doid", "http://identifiers.org/mesh/disease/id", "DOID->MeSH"),\
#    Translation ("DOID:1470", "http://identifiers.org/doid", "http://chem2bio2rdf.org/uniprot/resource/gene", "DOID->Target"),\
#    Translation ("MESH:D001249", "http://identifiers.org/mesh", "http://identifiers.org/doi", "MeSH->*") \
]

def create_app():
    from greent import app
    app = app.create_app(graphiql=True)
    app.config['TESTING'] = True
    app.config['LIVESERVER_PORT'] = 5001
    return app
                                                            
def test_translations ():
    pp = PrettyPrinter (indent=4)
    for index, translation in enumerate (translations):
        name = "-- Translate {0} -> thing: {1} in domain {2} to domain {3}.".format(translation.description, translation.thing, translation.domain_a, translation.domain_b)
        print ("{0}".format (name))
        pp.pprint (translator.translate (
            thing=translation.thing,
            domain_a=translation.domain_a,
            domain_b=translation.domain_b))

def main():
    test_translations()
    

if __name__ == '__main__':
    main()
