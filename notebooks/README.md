# Notebooks

Each notebook starts with a markdown cell listing learning objectives, contains
well-commented code and explanations, and (where applicable) ends with exercises.

## Index

| # | Notebook | Description |
|---|----------|-------------|
| 01 | `01-rdflib-hp-class-triples.ipynb` | Parse the HPO ontology (`hp.owl`) with rdflib and extract class triples. |
| 02 | `02-load-phenotype-local-hpoa.ipynb` | Load the local `phenotype.hpoa` annotation file into a DataFrame. |
| 03 | `03-extract-hpoa-tuple-and-resolve-labels.ipynb` | Extract annotation tuples and resolve HPO term labels. |
| 04 | `04-build-rdf-phenotypic-annotation-graph.ipynb` | Build an RDF graph of phenotypic annotations. |
| 05 | `05-connect-neo4j-kb-llm-hpo.ipynb` | Connect to Neo4j, create constraints/indexes, and initialize n10s config (only on empty graph). |
| 06 | `06-check-hpo-database-populated.ipynb` | Verify the HPO database is populated: node/rel counts, label distribution, samples, and enrich phenotype nodes. |
| 07 | `07-load-hpoa-annotation-data.ipynb` | Load HPOA disease annotations, create disease–phenotype relationships, and enrich with metadata. |

