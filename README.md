# PROTOCOP
Prototype implementation of building a knowledge network by iteratively querying data sources.

## Introduction

The purpose of this tool is to rapidly test the efficacy of an edge-crawling technique to produce knowledge graphs.

Suppose that you have a knowledge graph in something like neo4j.  You can write a query that specifies a path through the data where each node has certain properties or types.  Now suppose, however, that your nodes are not in a single database, but are in a series of federated systems with interfaces that allow subject-object queries.

We still want to run the same kinds of queries, but we are going to operate at the single-edge level,
somewhat similar to [Linked DataFragments](http://linkeddatafragments.org/concept/).   We read in a path query and decompose it into a set of binary queries that can be sent to a known set of data sources.

Beyond this, we add the creation of supporting edges: for each pair of nodes along a result path, we query Chemotext, a Pubmed term co-occurrence database.  When terms co-occur in PubMed papers, we add edges between those terms in the path, indicating support for the path.

When Protocop has completed, it exports the network to a locally running neo4j instance where it can be viewed or further analyzed.

## Example

One potential query is "Find a genetic condition that may be protective against infection from the Ebola virus."   How could there be such a condition?  If there were a particular human gene needed for the Ebola virus to infect its host, then a genetic condition that degrades the performance of that gene may also offer protection against infection.  Therefore, we can interpret this in the following way:  "Find a path starting at Ebola Virus, going through a target, and then going to a node for an (unknown) genetic condition".

Our query can be schematically represented as: "(D;DOID:4325)-G-GC".  Each dash represents an edge, and the nodes are specified by their type. Here "G" stands for "Gene", "GC" is "Genetic Condition" and "D" is disease.  In addition, the first node in the query is specified by the ID for Ebola infection in the Disease Ontology, DOID:4325.

Protocop begins at its given node "DOID:4325", and queries its known data sources (in this case Pharos) for genes that are connected to that disease.  It then takes each of these genes and queries its data sources (here Biolink) to look for genetic conditions that are associated with that gene.

Once the graph is built and pruned, chemotext is queried to look for supporting edges.  In this case, one supporting edge is found connecting DOID:4325 (Ebola infection) with OMIM:257220 (Niemann-Pick Disease, Type C1). 

![Example network](example1.png)

In this image, the source node is displayed in red, the genes from the first query are in yellow, and the genetic conditions from the second query are in blue.  Edges from those queries are in black, and the edge for the support query is in green.


## Installation

Protocop depends on [greent](https://github.com/NCATS-Tangerine/greent) for managing data sources and type graphs.  Greent can be installed via pip or cloned from github.  If the latter, it must be added to your PYTHONPATH.

Protocop also expects that [neo4j](https://github.com/NCATS-Tangerine/greent) is running on localhost.  This is where results are stored. 

Protocop has numerous other dependencies.  The simplest way to satisfy them is using the conda environment.yml file in the distribution.  Instructions for creating a conda environment from this file are found [here](https://conda.io/docs/user-guide/tasks/manage-environments.html).

## Use

This package can be used from the command line, called programmatically, or behind the scenes as a component of [Protocop Rank](https://github.com/covartech/protocop-rank).  

### Command Line Usage

To use protocop you need to tell it several things: 
1. The name of a starting entity.  Currently this should either be a drug, a disease, or a phenotype.
2. Optionally the name of an ending entity. In the Ebola example above, this is not given.  
3. The types of support edges that will be added.  Currently, these are "chemotext": based on co-occurrences of MeSH terms in pubmed abstracts, "chemotext2": a word-to-vec model for fulltext pubmed articles, and "cdw": a count of co-occurences of indications in the Carolina Data Warehouse.  At least one must be used, but all may be used simultaneously.
4. The name of the label used to denote the network in neo4j.
5. The path taken through the knowledge sources.

The path is defined as a series of high-level data types (such as Disease or Gene).  Results to the
query will pass through nodes of these types in order.  The path is specified on the command line as a string where each character represents one of these types. The full list of types, and their codes are currently:
S: Substance (Drug)
G: Gene
P: Process (Pathway)
C: Cell Type
A: Anatomical Feature
T: Phenotype
D: Disease
X: Genetic Condition

So, to query for path starting at a Gene, going to a Drug, and there to a Disease, the path would be written as "GSD".

In addition to fully specifying a path, any transition between types may include other hidden transitions.  To allow for this, a parenthetical statement can be included between any two node symbols giving the minimum and maximum number of edges that may be crossed in going from the source node to the target node.

For instance, suppose that in going from Drug to Disease in the above example, you wanted to require another type of node to appear in between, but you don't want to specify what the type of that node is.  Then going from Drug to Disease will traverse two edges: one from Drug to the untyped node, and another from the untyped node to the Disease.  The full path query would then be "GS(2-2)D".  The first 2 in the parentheses is the minimum number of edges to cross in going from S to D, and the second two is the maximum.  So if you wanted to allow an untyped node between S and D, but not require it, the query would be written "GS(1-2)D".

If no parentheses come between node types, then a direct edge is used. This would be equivalent to including (1-1) between the node types.

Examples of command lines are included in the examples.sh file of the repository.

### Programmatic Interface

Rather than running directly on the command line, the builder.py function run can be used to programmatically execute protocop.
