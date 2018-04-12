import pytest
from builder.builder import export_node
from greent.graph_components import KNode
from greent.conftest import rosetta,conf
from greent import node_types

TEST_ID = "FAKEY:MCFAKERSON"
ORIGINAL_SYNONYMS = set(["ORIGINAL_SYN", "ORIGINAL_SYN_2"])

@pytest.fixture(scope='function')
def session(rosetta):
    driver = rosetta.type_graph.driver
    session = driver.session()
    yield session
    session.close()

def get_node(identifier,session):
    result = session.run("MATCH (a {id: {identifier}}) RETURN a", {"identifier":identifier} )
    record = result.peek()
    if record is None:
        return None
    return record['a']

def create_node(session):
    #Make sure we're clean
    session.run("MATCH (a {id:{id}}) DETACH DELETE a", {"id": TEST_ID})
    original = get_node(TEST_ID, session)
    assert original is None
    node = KNode(TEST_ID, node_types.DISEASE)
    node.add_synonyms(ORIGINAL_SYNONYMS)
    export_node(node,session)

def test_create(session):
    create_node(session)
    rounder = get_node(TEST_ID, session)
    assert rounder is not None
    labels = rounder.labels
    assert len(labels) == 1
    assert list(labels)[0] == node_types.DISEASE

def test_add_label(session):
    #Add a node with type disease
    create_node(session)
    #Now, have the same identifier, but a subclass
    node = KNode(TEST_ID, node_types.GENETIC_CONDITION)
    #export, and pull the node
    export_node(node,session)
    rounder = get_node(TEST_ID,session)
    assert len(rounder.labels) == 2
    assert node_types.DISEASE in rounder.labels
    assert node_types.GENETIC_CONDITION in rounder.labels

def test_also_overwrite_synonyms(session):
    """If we have a node with synonyms, and we have different synonyms and write that node again, we will overwrite the synonyms"""
     #Add a node with type disease
    create_node(session)
    #Now, have the same identifier, but new synonyms set.  The original synonyms are ORIGINAL_SYNONYMS
    node = KNode(TEST_ID, node_types.GENETIC_CONDITION)
    FINAL_SYN = "FINAL_SYN"
    node.add_synonyms(set([FINAL_SYN]))
    export_node(node,session)
    rounder = get_node(TEST_ID,session)
    assert len(rounder.labels) == 2
    assert node_types.DISEASE in rounder.labels
    assert node_types.GENETIC_CONDITION in rounder.labels
    assert len(rounder.properties['equivalent_identifiers']) == 2
    assert TEST_ID in rounder.properties['equivalent_identifiers']
    assert FINAL_SYN in rounder.properties['equivalent_identifiers']

def test_just_overwrite_name(session):
    """If we have a node with synonyms, and we have different synonyms and write that node again, we will overwrite the synonyms"""
     #Add a node with type disease
    create_node(session)
    #Now, have the same identifier, but new synonyms set.  The original synonyms are ORIGINAL_SYNONYMS
    node = KNode(TEST_ID, node_types.GENETIC_CONDITION, label="Sweet new label")
    node.add_synonyms(ORIGINAL_SYNONYMS)
    export_node(node,session)
    rounder = get_node(TEST_ID,session)
    assert len(rounder.labels) == 2
    assert node_types.DISEASE in rounder.labels
    assert node_types.GENETIC_CONDITION in rounder.labels
    assert rounder.properties['name'] == 'Sweet new label'

