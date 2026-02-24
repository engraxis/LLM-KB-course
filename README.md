# Knowledge Graphs and LLMs in Action — Course Template

This repository provides a clean, best-practices template for teaching with Jupyter notebooks, inspired by [github.com/alenegro81/knowledge-graphs-and-llms-in-action/tree/main/chapters/ch03](https://github.com/alenegro81/knowledge-graphs-and-llms-in-action/tree/main/chapters/ch03).

## Structure

- `notebooks/` — Jupyter notebooks (01–07) covering RDF parsing, Neo4j graph construction, and HPO data integration.
- `notebook-solutions/` — Reference solutions for selected notebooks.
- `data/` — Datasets: `hp.owl` (HPO ontology) and `phenotype_local.hpoa` (phenotype annotations).
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

## Teaching Best Practices
- Each notebook starts with learning objectives and ends with exercises.
- Code is well-commented and modular.
- Data is small and shareable, or scripts are provided to download/generate it.
- Environment is fully reproducible.

## Next Steps
- Run notebooks 01–04 to parse RDF data locally with rdflib.
- Run notebook 05 to set up the Neo4j `hpo` database (constraints, indexes, n10s config).
- Run notebook 06 to verify the graph is populated and enrich phenotype nodes.
- Run notebook 07 to load HPOA annotation data and enrich disease–phenotype relationships.

