import pytest
from greent.graph_components import KNode
from greent import node_types
from builder.userquery import UserQuery, TwoSidedLinearUserQuery, TwoSidedLinearUserQuerySet, OneSidedLinearUserQuerySet


@pytest.fixture(scope='module')
def rosetta():
    from greent.rosetta import Rosetta
    return Rosetta()


def test_simple_query(rosetta):
    disease_name = 'test_name'
    did = 'DOID:123'
    disease_identifiers = [did]
    name_node = KNode('{}:{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    qd = UserQuery(disease_identifiers, node_types.DISEASE, name_node)
    qd.add_transition(node_types.GENE)
    qd.add_transition(node_types.GENETIC_CONDITION)
    assert qd.compile_query(rosetta)
    cyphers = qd.generate_cypher()
    assert len(cyphers) == 1
    start_nodes = qd.get_start_node()
    assert len(start_nodes) == 1
    assert start_nodes[0][0] == did
    lookups = qd.get_lookups()
    assert len(lookups) == 1
    assert lookups[0].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    reverse = qd.get_reversed()
    assert len(reverse) == 1
    assert not reverse[0]

def test_simple_query_with_unspecified(rosetta):
    disease_name = 'test_name'
    did = 'DOID:123'
    disease_identifiers = [did]
    name_node = KNode('{}:{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    qd = UserQuery(disease_identifiers, node_types.DISEASE, name_node)
    qd.add_transition(node_types.UNSPECIFIED)
    qd.add_transition(node_types.GENETIC_CONDITION)
    assert qd.compile_query(rosetta)
    cyphers = qd.generate_cypher()
    assert len(cyphers) == 1
    start_nodes = qd.get_start_node()
    assert len(start_nodes) == 1
    assert start_nodes[0][0] == did
    lookups = qd.get_lookups()
    assert len(lookups) == 1
    assert lookups[0].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    reverse = qd.get_reversed()
    assert len(reverse) == 1
    assert not reverse[0]

def test_simple_query_with_unspecified_at_end(rosetta):
    disease_name = 'test_name'
    did = 'DOID:123'
    disease_identifiers = [did]
    name_node = KNode('{}:{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    qd = UserQuery(disease_identifiers, node_types.DISEASE, name_node)
    qd.add_transition(node_types.GENE)
    qd.add_transition(node_types.UNSPECIFIED)
    assert qd.compile_query(rosetta)
    cyphers = qd.generate_cypher()
    assert len(cyphers) == 1
    start_nodes = qd.get_start_node()
    assert len(start_nodes) == 1
    assert start_nodes[0][0] == did
    lookups = qd.get_lookups()
    assert len(lookups) == 1
    assert lookups[0].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    reverse = qd.get_reversed()
    assert len(reverse) == 1
    assert not reverse[0]



def test_failing_query(rosetta):
    """IN the current set of edges, there is no gene->anatomy service. If we add one this teset will fail"""
    disease_name = 'test_name'
    did = 'DOID:123'
    disease_identifiers = [did]
    name_node = KNode('{}:{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    qd = UserQuery(disease_identifiers, node_types.DISEASE, name_node)
    qd.add_transition(node_types.GENE)
    qd.add_transition(node_types.ANATOMY)
    assert not qd.compile_query(rosetta)


def test_query_set_same_id_type(rosetta):
    disease_name = 'test_name'
    disease_identifiers = ['DOID:123', 'DOID:456']
    name_node = KNode('{}:{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    qd = UserQuery(disease_identifiers, node_types.DISEASE, name_node)
    qd.add_transition(node_types.GENE)
    qd.add_transition(node_types.GENETIC_CONDITION)
    assert qd.compile_query(rosetta)
    cyphers = qd.generate_cypher()
    assert len(cyphers) == 2
    start_nodes = qd.get_start_node()
    assert len(start_nodes) == 2
    assert start_nodes[0][0] == disease_identifiers[0]
    assert start_nodes[1][0] == disease_identifiers[1]
    lookups = qd.get_lookups()
    assert len(lookups) == 2
    assert lookups[0].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    assert lookups[1].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    reverse = qd.get_reversed()
    assert len(reverse) == 2
    assert not reverse[0]
    assert not reverse[1]


def test_query_set_different_valid_ids(rosetta):
    disease_name = 'test_name'
    disease_identifiers = ['DOID:123', 'EFO:456']
    name_node = KNode('{}:{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    qd = UserQuery(disease_identifiers, node_types.DISEASE, name_node)
    qd.add_transition(node_types.GENE)
    qd.add_transition(node_types.GENETIC_CONDITION)
    assert qd.compile_query(rosetta)
    cyphers = qd.generate_cypher()
    assert len(cyphers) == 2
    start_nodes = qd.get_start_node()
    assert len(start_nodes) == 2
    assert start_nodes[0][0] == disease_identifiers[0]
    assert start_nodes[1][0] == disease_identifiers[1]
    lookups = qd.get_lookups()
    assert len(lookups) == 2
    assert lookups[0].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    assert lookups[1].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    reverse = qd.get_reversed()
    assert len(reverse) == 2
    assert not reverse[0]
    assert not reverse[1]


def test_query_set_different_one_valid_ids(rosetta):
    disease_name = 'test_name'
    disease_identifiers = ['DOID:123', 'FAKEYFAKEY:456']
    name_node = KNode('{}:{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    qd = UserQuery(disease_identifiers, node_types.DISEASE, name_node)
    qd.add_transition(node_types.GENE)
    qd.add_transition(node_types.GENETIC_CONDITION)
    assert qd.compile_query(rosetta)
    #generate_cypher is no longer relevant
    #cyphers = qd.generate_cypher()
    #assert len(cyphers) == 1
    start_nodes = qd.get_start_node()
    assert len(start_nodes) == 1
    assert start_nodes[0][0] == disease_identifiers[0]
    lookups = qd.get_lookups()
    assert len(lookups) == 1
    assert lookups[0].identifier == '{}:{}'.format(node_types.DISEASE_NAME, disease_name)
    reverse = qd.get_reversed()
    assert len(reverse) == 1
    assert not reverse[0]


def test_two_sided_query_compose(rosetta):
    """Create a 2sided query, composing it by hand.Mimics what should happen
    automatically in a 2 sided user query"""
    drug_name = 'test_drug'
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    drug_identifiers = ['CTD:123']
    disease_name = 'test_disease'
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    disease_identifiers = ['DOID:123']
    # This will create a OneSidedQuerySet
    queryl = UserQuery(drug_identifiers, node_types.DRUG, drug_name_node)
    queryl.add_transition(node_types.GENE)
    queryl.add_transition(node_types.PROCESS)
    queryl.add_transition(node_types.CELL)
    queryl.add_transition(node_types.ANATOMY)
    # this is another
    queryr = UserQuery(disease_identifiers, node_types.DISEASE, disease_name_node)
    queryr.add_transition(node_types.PHENOTYPE)
    queryr.add_transition(node_types.ANATOMY)
    # The individual queries check out
    assert queryl.compile_query(rosetta)
    assert queryr.compile_query(rosetta)
    # The two sided checks out
    twolq = TwoSidedLinearUserQuery(queryl.query, queryr.query)
    assert twolq.compile_query(rosetta)
    twolqs = TwoSidedLinearUserQuerySet()
    twolqs.add_query(twolq, rosetta)
    # the two sided set checks out
    assert twolqs.compile_query(rosetta)


def test_generate_set(rosetta):
    drug_name = 'test_drug'
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    drug_identifiers = ['CTD:123']
    disease_name = 'test_disease'
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    disease_identifiers = ['DOID:123']
    query = UserQuery(drug_identifiers, node_types.DRUG, drug_name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.PROCESS)
    query.add_transition(node_types.CELL)
    query.add_transition(node_types.ANATOMY)
    query.add_transition(node_types.PHENOTYPE)
    query.add_transition(node_types.DISEASE, end_values=disease_identifiers)
    query.add_end_lookup_node(disease_name_node)
    d = query.definition
    l, r = d.generate_paired_query(4)
    assert len(l.transitions) == 4
    assert len(r.transitions) == 2
    lq = OneSidedLinearUserQuerySet(l)
    rq = OneSidedLinearUserQuerySet(r)
    # print(lq.generate_cypher()[0])
    # print()
    # print(rq.generate_cypher()[0])
    print(rq.generate_cypher()[0])
    assert lq.compile_query(rosetta)
    assert rq.compile_query(rosetta)


def test_query_two_sided_queryset(rosetta):
    drug_name = 'test_drug'
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    drug_identifiers = ['CTD:123']
    disease_name = 'test_disease'
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    disease_identifiers = ['DOID:123']
    query = UserQuery(drug_identifiers, node_types.DRUG, drug_name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.PROCESS)
    query.add_transition(node_types.CELL)
    query.add_transition(node_types.ANATOMY)
    query.add_transition(node_types.PHENOTYPE)
    query.add_transition(node_types.DISEASE, end_values=disease_identifiers)
    query.add_end_lookup_node(disease_name_node)
    assert query.compile_query(rosetta)


def test_query_two(rosetta):
    drug_name = 'test_drug'
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    drug_identifiers = ['CTD:Adapalene', 'PHAROS.DRUG:95769', 'PUBCHEM:60164']
    disease_name = 'test_disease'
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    disease_identifiers = ['DOID:123']
    query = UserQuery(drug_identifiers, node_types.DRUG, drug_name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.PROCESS)
    query.add_transition(node_types.CELL)
    query.add_transition(node_types.ANATOMY)
    query.add_transition(node_types.PHENOTYPE)
    query.add_transition(node_types.DISEASE, end_values=disease_identifiers)
    query.add_end_lookup_node(disease_name_node)
    assert query.compile_query(rosetta)


def test_d_unknown_d(rosetta):
    drug_name = 'test_drug'
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    drug_ids = ['CTD:Lisinopril', 'PHAROS.DRUG:128029', 'PUBCHEM:5362119']
    disease_name = 'test_disease'
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    disease_ids = ['DOID:4325']
    query = UserQuery(drug_ids, node_types.DRUG, drug_name_node)
    query.add_transition(node_types.DISEASE, min_path_length=1, max_path_length=2, end_values=disease_ids)
    query.add_end_lookup_node(disease_name_node)
    assert query.compile_query(rosetta)


def test_dgd(rosetta):
    drug_name = 'test_drug'
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    drug_ids = ['CTD:Lisinopril', 'PHAROS.DRUG:128029', 'PUBCHEM:5362119']
    disease_name = 'test_disease'
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    disease_ids = ['DOID:4325']
    query = UserQuery(drug_ids, node_types.DRUG, drug_name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.DISEASE, end_values=disease_ids)
    query.add_end_lookup_node(disease_name_node)
    assert query.compile_query(rosetta)


def build_question2(drug_name, disease_name, drug_ids, disease_ids):
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    query = UserQuery(drug_ids, node_types.DRUG, drug_name_node)
    query.add_transition(node_types.GENE)
    query.add_transition(node_types.PROCESS)
    query.add_transition(node_types.CELL)
    query.add_transition(node_types.ANATOMY)
    query.add_transition(node_types.PHENOTYPE)
    query.add_transition(node_types.DISEASE, end_values=disease_ids)
    return query


def test_query_two_from_builder(rosetta):
    drug_name = 'test_drug'
    drug_name_node = KNode('{}.{}'.format(node_types.DRUG_NAME, drug_name), node_types.DRUG_NAME)
    drug_ids = ['CTD:Adapalene', 'PHAROS.DRUG:95769', 'PUBCHEM:60164']
    disease_name = 'test_disease'
    disease_name_node = KNode('{}.{}'.format(node_types.DISEASE_NAME, disease_name), node_types.DISEASE_NAME)
    disease_ids = ['DOID:123']
    query = build_question2(drug_name, disease_name, drug_ids, disease_ids)
    assert query.compile_query(rosetta)
