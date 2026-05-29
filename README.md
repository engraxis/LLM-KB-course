# Knowledge Graphs and LLMs in Action — Course Template

This repository provides a clean, best-practices template for teaching with Jupyter notebooks, inspired by [github.com/alenegro81/knowledge-graphs-and-llms-in-action/tree/main/chapters/ch03](https://github.com/alenegro81/knowledge-graphs-and-llms-in-action/tree/main/chapters/ch03).

## Structure

- `notebooks/` — Jupyter notebooks (01–09) covering RDF parsing, Neo4j graph construction, HPO data integration, semantic inference, and Azure OpenAI integration.
- `notebook-solutions/` — Reference solutions for selected notebooks.
- `triple_viewer/` — Flask app to inspect entity highlights and visualize extracted triples from PubMed-like text.
- `data/` — Local inputs: HPO ontology/annotation data, prompt templates, and example PubMed abstracts.
- `environment.yml` / `requirements.txt` — Environment files for reproducibility.

## Prerequisites

- Python 3.11+
- Neo4j Desktop (Enterprise) with the **Neosemantics (n10s)** and **APOC** plugins installed.
- Packages: `neo4j`, `rdflib` (see `requirements.txt`).

## Setup

1. Clone this repository.
2. Create the environment:
   - With conda: `conda env create -f environment.yml && conda activate kg-llm-course`
   - Or with pip: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. Start JupyterLab: `jupyter lab`

## Notebook Guide

Run notebooks in order, since later notebooks build on earlier outputs and graph state.

| # | Notebook | What you do |
|---|----------|-------------|
| 01 | `notebooks/01-rdflib-hp-class-triples.ipynb` | Parse `data/hp.owl` with `rdflib` and inspect class-level triples from the HPO ontology. |
| 02 | `notebooks/02-load-phenotype-local-hpoa.ipynb` | Load local HPOA annotations into pandas and explore schema/quality checks. |
| 03 | `notebooks/03-extract-hpoa-tuple-and-resolve-labels.ipynb` | Build annotation tuples and resolve term labels from ontology IDs. |
| 04 | `notebooks/04-build-rdf-phenotypic-annotation-graph.ipynb` | Create an RDF phenotypic-annotation graph from cleaned annotation records. |
   The config only allows apoc.* — n10s is not included. Edit those two lines to add n10s.*:
   Open the conf file: /conf/neo4j.conf"
   Find these two lines and change them to:
   confdbms.security.procedures.unrestricted=apoc.*,n10s.*
   dbms.security.procedures.allowlist=apoc.*,n10s.*
| 05 | `notebooks/05-connect-neo4j-kb-llm-hpo.ipynb` | Connect to Neo4j, set constraints/indexes, and initialize Neosemantics (`n10s`). |
| 06 | `notebooks/06-check-hpo-database-populated.ipynb` | Validate that the Neo4j HPO graph is populated and inspect key node/relationship statistics. |
| 07 | `notebooks/07-load-hpoa-annotation-data.ipynb` | Load disease-phenotype annotation data into Neo4j and enrich relationship metadata. |
| 08 | `notebooks/08-semantic-inference-hpo.ipynb` | Run semantic/inference-oriented checks over the HPO knowledge graph and inspect inferred structure. |
| 09 | `notebooks/09-connect-azure-openai-llm.ipynb` | Connect the graph workflow to Azure OpenAI for LLM-assisted extraction/integration steps. |

## Triple Viewer

`triple_viewer/` is a lightweight local UI for experimenting with extracted triples:

- Load a sample abstract from `data/pubmed/` (or upload your own text).
- Paste/inspect extracted triples in bracket format: `[entity1, TYPE1, RELATION, entity2, TYPE2]`.
- Highlight detected entities in-text with type colors.
- Visualize relation edges as an interactive graph.
- Optionally call Azure OpenAI extraction from the app by providing an API key in-session.

### Run Triple Viewer

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r triple_viewer/requirements.txt
python triple_viewer/app.py
```

Then open `http://127.0.0.1:5001`.

## Teaching Best Practices
- Each notebook starts with learning objectives and ends with exercises.
- Code is well-commented and modular.
- Data is small and shareable, or scripts are provided to download/generate it.
- Environment is fully reproducible.

## Suggested Learning Flow
- Start with notebooks `01`-`04` for local RDF + annotation processing.
- Continue with notebooks `05`-`07` for Neo4j schema setup and data ingestion.
- Use notebook `08` for inference-focused exploration on the graph.
- Use notebook `09` and `triple_viewer/` to integrate and evaluate LLM-driven extraction workflows.

