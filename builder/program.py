import requests_cache
import logging
import traceback

from greent.graph_components import KNode,KEdge
from greent.util import LoggingUtil


logger = LoggingUtil.init_logging(__file__, level=logging.DEBUG)

class Program:

    def __init__(self, plan, query_definition, rosetta):
        self.concept_nodes = plan[0]
        self.transitions = plan[1]
        self.rosetta = rosetta
        self.unused_instance_nodes = set()
        self.all_instance_nodes = set()
        self.initialize_instance_nodes(query_definition)
        self.linked_results = []

    def initialize_instance_nodes(self,query_definition):
        t_node_ids = self.get_terminal_node_identifiers()
        new_nodes = [KNode(start_identifier, self.concept_nodes[t_node_ids[0]]) for start_identifier in query_definition.start_values]
        self.add_instance_nodes(new_nodes, t_node_ids[0])
        if len(t_node_ids) == 1:
            if query_definition.end_values is not None:
                raise Exception("We only have one set of terminal nodes in the query plan, but multiple sets of terminal instances")
            return
        if len(t_node_ids) == 2:
            if query_definition.end_values is None:
                raise Exception("We have multiple terminal nodes in the query plan but only one set of terminal instances")
            end_nodes = [KNode(start_identifier, self.concept_nodes[t_node_ids[-1]]) for start_identifier in query_definition.end_values]
            self.add_instance_nodes(end_nodes)
            return
        raise Exception("We don't yet support more than 2 instance-specified nodes")

    def get_terminal_node_identifiers(self):
        nodeset = set(self.concept_nodes.keys())
        for transition in self.transitions:
            nodeset.remove(transition['to'])
        terminal_node_identifiers = list(nodeset)
        terminal_node_identifiers.sort()
        return terminal_node_identifiers

    def add_instance_nodes(self, nodelist, context):
        """We've got a new set of nodes (either initial nodes or from a query).  They are attached
        to a particular concept in our query plan. We make sure that they're synonymized and then
        add them to both all_instance_nodes as well as the unused_instance_nodes"""
        for node in nodelist:
            self.rosetta.synonymizer.synonymize(node)
        self.all_instance_nodes.update(nodelist)
        self.unused_instance_nodes.update([(node,context) for node in nodelist ])

    def run_program(self):
        """Loop over unused nodes, send them to the appropriate operator, and collect the results.
        Keep going until there's no nodes left to process."""
        while len(self.unused_instance_nodes) > 0:
            source_node, context = iter(self.unused_instance_nodes).next()
            link = self.transitions(context)
            next_context = link['to']
            op = self.rosetta.get_ops(link['op'])
            try:
                results = None
                log_text = "  -- {0}({1})".format('op', source_node.identifier)
                logger.debug(log_text)
                with requests_cache.enabled("rosetta_cache"):
                    results = op(source_node)
                newnodes = []
                for r in results:
                    edge = r[0]
                    if isinstance(edge, KEdge):
                        edge.predicate = link['link']
                        edge.source_node = source_node
                        edge.target_node = r[1]
                        self.linked_results.append(edge)
                        newnodes.append(r[1])
                self.add_instance_nodes(newnodes)
            except Exception as e:
                traceback.print_exc()
                logger.error("Error invoking> {0}".format(log_text))
        return self.linked_results

    def get_results(self):
        return self.linked_results

