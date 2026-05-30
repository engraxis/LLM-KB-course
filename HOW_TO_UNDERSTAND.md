# How to Understand This Project

**LLM + Knowledge Graph**, read this before touching any notebook.

---

## Table of Contents

1. [Major Libraries and What They Do](#1-major-libraries-and-what-they-do)
2. [What Is a Knowledge Graph](#2-what-is-a-knowledge-graph)
3. [Why Two Separate Data Files](#3-why-two-separate-data-files)
4. [How to Build the Knowledge Graph](#4-how-to-build-the-knowledge-graph)
5. [Why Connect a KG with an LLM](#5-why-connect-a-kg-with-an-llm)
6. [Why Neo4j and What Is Its Role](#6-why-neo4j-and-what-is-its-role)
7. [Key Concepts Glossary](#7-key-concepts-glossary)
8. [Overall Data Flow](#8-overall-data-flow)
9. [Pipeline A — Local RDF and Pandas (Notebooks 01–04)](#9-pipeline-a--local-rdf-and-pandas-notebooks-0104)
10. [Pipeline B — Neo4j Graph Construction (Notebooks 05–08)](#10-pipeline-b--neo4j-graph-construction-notebooks-0508)
11. [Pipeline C — LLM Integration (Notebook 09 and Triple Viewer)](#11-pipeline-c--llm-integration-notebook-09-and-triple-viewer)

---

## 1. Major Libraries and What They Do

Understanding the role of each tool before reading code will save a lot of confusion.

### Python Libraries

#### `rdflib`
- **What it is:** A Python library for working with RDF (Resource Description Framework) data.
- **What it does here:** Parses the `data/hp.owl` file — a large ontology file — into an in-memory graph of triples. You can then query which triples exist for a given concept, look up labels, follow `subClassOf` links, or serialize parts of the graph back to text formats like Turtle.
- **Analogy:** Think of it as a specialized JSON parser, but instead of loading JSON into a Python dictionary, it loads an OWL file into a graph you can traverse.
- **Used in:** Notebooks 01–04.

#### `pandas`
- **What it is:** The standard Python library for tabular data (like Excel in Python).
- **What it does here:** Reads `data/phenotype_local.hpoa` — a tab-separated file — into a DataFrame. Used to explore, clean, filter, and transform the annotation data (280,730 rows of disease-to-phenotype links).
- **Used in:** Notebooks 02–03.

#### `neo4j` (Python driver)
- **What it is:** The official Python driver for the Neo4j graph database.
- **What it does here:** Acts as the bridge between Python code and the running Neo4j database. Every Cypher query you see in the notebooks (like `MATCH`, `MERGE`, `LOAD CSV`) is a string that Python sends to Neo4j over the network. Neo4j executes it; Python just sends and receives.
- **Important distinction:** This library does NOT do graph computation itself. It is purely a messenger. The actual graph work happens inside Neo4j.
- **Used in:** Notebooks 05–08.

#### `openai` (Azure OpenAI SDK)
- **What it is:** The OpenAI Python SDK configured to call Microsoft Azure-hosted GPT models.
- **What it does here:** Sends biomedical text (PubMed abstracts) to a GPT model along with a system prompt that instructs it to extract structured entity-relation triples. Receives the model's response and parses the triples.
- **Used in:** Notebook 09 and `triple_viewer/app.py`.

#### `flask`
- **What it is:** A lightweight Python web framework.
- **What it does here:** Powers the `triple_viewer` application — a local web UI running at `http://127.0.0.1:5001`. It handles HTTP routes, session management (storing your API key), and renders HTML templates. You interact with it in a browser, not a notebook.
- **Used in:** `triple_viewer/app.py`.

---

### Neo4j Server-Side Plugins

These are **not Python libraries**. They are plugins installed inside the Neo4j database engine. Python triggers them by sending Cypher commands like `CALL n10s.something(...)`, but the code runs entirely inside the database server.

#### `n10s` — Neosemantics

- **What it is:** A Neo4j plugin that bridges the RDF world and the property-graph world.
- **What it does here:**
  - **Importing:** Reads `hp.owl` and translates its 905,482 RDF triples into Neo4j nodes and relationships. Without n10s you would need to write custom code to parse the OWL file and manually create nodes — n10s does this automatically.
  - **Inference:** Provides `n10s.inference.nodesInCategory()`, a Cypher procedure that traverses the `SUBCLASSOF` hierarchy in both directions, enabling ontology-aware queries (see [Section 10](#10-pipeline-b--neo4j-graph-construction-notebooks-0508)).
- **Why it matters:** It is what makes the OWL ontology "alive" inside Neo4j as a queryable graph.

#### `APOC` — Awesome Procedures On Cypher

- **What it is:** A large utility library for Neo4j providing hundreds of procedures that core Cypher lacks.
- **What it does here:**
  - `apoc.periodic.iterate()` — processes large numbers of nodes/relationships in batches of 1,000 to avoid running out of memory.
  - `apoc.text.regexGroups()` — extracts substrings using regular expressions (used to parse the biocuration field `HPO:probinson[2021-06-21]` into author and date).
  - `apoc.text.replace()` — string replacement (used to convert URIs like `http://.../obo/HP_0100651` into readable IDs like `HP:0100651`).

---

### Quick Role Summary

| Tool | Type | Role |
|---|---|---|
| `rdflib` | Python library | Parse and query OWL/RDF files locally |
| `pandas` | Python library | Load and clean tabular annotation data |
| `neo4j` driver | Python library | Send Cypher queries to Neo4j |
| `openai` SDK | Python library | Call Azure GPT to extract triples from text |
| `flask` | Python library | Serve the Triple Viewer web UI |
| `n10s` | Neo4j plugin | Import OWL into Neo4j; ontology inference |
| `APOC` | Neo4j plugin | Batch processing, regex, string utilities inside Neo4j |

---

## 2. What Is a Knowledge Graph

### The Core Idea: Triples

A Knowledge Graph (KG) is a structured representation of knowledge where everything is expressed as **triples**:

```
Subject  →  Predicate  →  Object
```

This is a statement with three parts — like a sentence. For example:

```
HP:0100651  rdfs:label    "Type I diabetes mellitus"
HP:0100651  subClassOf    HP:0000819
OMIM:619340 hasPhenotype  HP:0011097
```

Read as:
- "HP:0100651 has the label *Type I diabetes mellitus*"
- "Type I Diabetes is a subclass of *Diabetes mellitus* (HP:0000819)"
- "Disease OMIM:619340 has the phenotype HP:0011097 (Epileptic seizure)"

A knowledge graph is simply a large collection of such statements — in this project, hundreds of thousands of them. Together they form a web of connected facts you can traverse and query.

### RDF — The Standard for Triples

**RDF (Resource Description Framework)** is the W3C web standard for encoding triples. Every node in an RDF graph gets a unique **URI** (like a URL) as its permanent identity. This means two different databases can both refer to the same concept — `http://purl.obolibrary.org/obo/HP_0100651` always means "Type I Diabetes Mellitus" regardless of which system uses it.

### OWL — Ontologies Built on RDF

**OWL (Web Ontology Language)** is built on top of RDF and adds logical structure:
- **Classes** (e.g., `HP:0100651` is an `owl:Class`)
- **Hierarchies** via `rdfs:subClassOf` (Type I Diabetes is a kind of Diabetes)
- **Definitions, synonyms, cross-references** as annotation properties

The `hp.owl` file in this project is an OWL ontology — a formal, machine-readable vocabulary of every known human phenotypic abnormality.

### What a KG Gives You That a Database Does Not

A relational database stores rows and tables. A knowledge graph stores interconnected facts you can traverse like a map. For example:

- **Relational query:** "Give me all diseases where `hpo_id = HP:0011097`"
- **Graph query:** "Give me all diseases associated with *any descendant* of HP:0000707 (Nervous system abnormality), following the entire phenotype hierarchy"

The second query is only natural in a graph. This is the core value of this project.

---

## 3. Why Two Separate Data Files

This project uses two complementary data files that serve entirely different purposes. Understanding why they are separate is key to understanding the project.

### File 1: `data/hp.owl` — The Vocabulary

This file answers: **"What does a term mean, and how does it relate to other terms?"**

It defines the HPO ontology — the controlled vocabulary itself:
- Every phenotype term has a unique ID (`HP:0100651`), a label, a definition, synonyms, and cross-references to other medical databases (SNOMED, UMLS).
- The terms are organized in a strict hierarchy via `subClassOf`: *Type I Diabetes* → *Diabetes mellitus* → *Abnormality of glucose homeostasis* → *Abnormality of metabolism* → ...
- It contains ~17,000 such classes and 905,482 RDF triples in total.

**Analogy:** Think of it as a medical dictionary with a hierarchical index.

### File 2: `data/phenotype_local.hpoa` — The Clinical Annotations

This file answers: **"Which diseases actually exhibit which phenotypes, and what is the evidence?"**

It contains curated clinical knowledge:
- Each of its 280,730 rows says: "Disease X is associated with phenotype HP:XXXXXXX"
- Each row also carries evidence (from which paper, how strong), frequency (how often is the symptom seen), when it was curated, and by whom.

**Example row:**
```
OMIM:619340  Developmental and epileptic encephalopathy 96
             HP:0011097   PMID:31675180   PCS   1/2   P   HPO:probinson[2021-06-21]
```
This says: disease `OMIM:619340` shows phenotype `HP:0011097` (epileptic seizure), observed in 1 out of 2 patients in a published clinical study, annotated by Peter Robinson on 21 June 2021.

**Analogy:** Think of it as a clinical database of patient observations that references the dictionary.

### Why Two Files and Not One?

| | `hp.owl` | `phenotype_local.hpoa` |
|---|---|---|
| **Purpose** | Define the vocabulary | Record clinical observations |
| **Maintained by** | HPO Consortium (ontologists) | HPO Curators (clinicians) |
| **Changes when** | A new phenotype is discovered or renamed | A new paper links a disease to a phenotype |
| **Contains** | Definitions, hierarchies, synonyms | Disease IDs, evidence, frequency, provenance |

Keeping them separate means the vocabulary can be updated without invalidating the annotations, and vice versa. Together, they form a complete knowledge graph: the ontology provides the **structure and meaning**, the annotation file provides the **clinical facts**.

---

## 4. How to Build the Knowledge Graph

Building the KG in this project happens in three stages, each adding a new layer:

### Stage 1 — Import the Ontology (the vocabulary layer)

The `hp.owl` file is fed to the **n10s plugin** inside Neo4j. n10s reads every `owl:Class` and creates a Neo4j node for it, and reads every `rdfs:subClassOf` and creates a `SUBCLASSOF` relationship. After this step you have a graph of ~17,000 phenotype nodes connected in a hierarchy.

```
HP:0000001 (All)
    └── HP:0000118 (Phenotypic abnormality)
            └── HP:0000707 (Nervous system abnormality)
                    └── HP:0001250 (Seizure)
                            └── HP:0011097 (Epileptic spasm)
```

### Stage 2 — Import the Annotations (the facts layer)

Neo4j's `LOAD CSV` reads the HPOA annotation file and:
1. Creates `HpoDisease` nodes for each disease (e.g., `OMIM:619340`)
2. Creates `HAS_PHENOTYPIC_FEATURE` relationships linking each disease to its phenotype nodes (already loaded in Stage 1)
3. Enriches each relationship with evidence, frequency, source URL, curator name, and date

After this step, diseases and phenotypes are connected:

```
OMIM:619340 -[HAS_PHENOTYPIC_FEATURE {evidence:"PCS", frequency:"1/2"}]→ HP:0011097
```

### Stage 3 — Enrich with LLM Extraction (the literature layer)

Notebook 09 and the Triple Viewer use an LLM to read PubMed abstracts and extract new entity-relation triples from unstructured text. These could be loaded back into Neo4j to extend the KG with facts mined from scientific literature — the implied final step of the course.

---

## 5. Why Connect a KG with an LLM

### The Problem with KGs Alone

Knowledge graphs like this HPO graph are:
- **Curated** — each fact was manually reviewed. This makes them highly reliable, but slow to update.
- **Structured** — facts are formal triples. You can query them precisely.
- **Incomplete** — millions of papers are published every year. Manual curation cannot keep up.

### The Problem with LLMs Alone

Large Language Models like GPT are:
- **Broad** — trained on vast text, they know about many topics.
- **Fluent** — can answer questions in natural language.
- **Hallucination-prone** — they sometimes invent plausible-sounding but wrong facts, especially for specific clinical or scientific details.
- **Unstructured** — their knowledge is implicit in weights, not queryable as facts.

### Why Combining Them Is Powerful

| Need | KG provides | LLM provides |
|---|---|---|
| Precise factual queries | Yes — structured, verified | No — may hallucinate |
| Natural language Q&A | No — returns structured data | Yes |
| Extracting facts from new papers | No — manual curation needed | Yes — fast extraction |
| Reasoning over hierarchies | Yes — ontology traversal | Unreliable |
| Explaining a result in plain language | No | Yes |

**In this project, the combination works two ways:**

1. **KG → LLM:** The knowledge graph provides a reliable factual backbone. You can query Neo4j for verified facts about a disease, then pass those facts to the LLM as context for answering a natural language question. The LLM generates fluent text but is grounded in curated data, reducing hallucinations.

2. **LLM → KG:** The LLM reads new PubMed abstracts and extracts structured triples (`[entity1, TYPE, RELATION, entity2, TYPE]`). These extracted triples can be loaded into Neo4j to extend the knowledge graph automatically. The LLM acts as a fast first-pass curator.

---

## 6. Why Neo4j and What Is Its Role

### Why Not Just Use pandas or a SQL Database?

You could store all this data in a CSV file or a SQL database. For simple lookups ("what phenotypes does disease X have?") that would work fine. But this project needs more:

1. **Hierarchy traversal:** "Find all diseases associated with any phenotype that is a descendant of *Nervous system abnormality*." In SQL this requires recursive CTEs and is awkward. In a graph database it is one `SUBCLASSOF*` path query.

2. **Ontology-aware inference:** Using the n10s `nodesInCategory` procedure, you can ask: "Find all diseases related to *Growth abnormality*, including indirect ones via the ontology hierarchy." This is semantic reasoning — it knows that *Short stature* is a subcategory of *Growth abnormality* and finds diseases annotated to *Short stature* too.

3. **Provenance on relationships:** Each `HAS_PHENOTYPIC_FEATURE` relationship carries ~15 properties (evidence type, frequency, source URL, curator, date). SQL can store this in a junction table, but traversing it alongside hierarchy queries becomes complex. In Neo4j, properties on relationships are first-class.

4. **Integrating RDF with a property graph:** The n10s plugin translates the OWL ontology directly into Neo4j's native graph format. There is no equivalent for SQL.

### Neo4j's Role in the KG

| Role | How Neo4j fulfills it |
|---|---|
| Store the ontology | n10s imports `hp.owl` → HpoPhenotype nodes + SUBCLASSOF rels |
| Store clinical facts | LOAD CSV imports HPOA → HpoDisease nodes + HAS_PHENOTYPIC_FEATURE rels |
| Enable hierarchy queries | Cypher path patterns (`[:SUBCLASSOF*]`) |
| Enable semantic inference | `n10s.inference.nodesInCategory()` traverses the full hierarchy |
| Enable provenance queries | Relationship properties store evidence, frequency, curator, date |

### Neo4j's Role in the LLM Pipeline

Neo4j acts as the **factual backbone** that the LLM can query:

- Before asking the LLM a question about a disease, you can first query Neo4j for all verified phenotypes of that disease, the evidence codes, the hierarchy position of each phenotype.
- This retrieved context is then passed to the LLM prompt, so the LLM is reasoning over known facts rather than its own (potentially hallucinated) memory.
- Conversely, triples extracted by the LLM from new papers can be loaded back into Neo4j via MERGE queries, extending the graph.

This architecture — retrieve verified facts from the graph, augment the LLM prompt with them — is the core pattern of **Graph-Augmented RAG** (Retrieval Augmented Generation with a knowledge graph as the retrieval source).

---

## 7. Key Concepts Glossary

| Term | Plain-language meaning |
|---|---|
| **Triple** | A three-part statement: (Subject, Predicate, Object). The atomic unit of a knowledge graph. |
| **RDF** | A W3C standard for encoding knowledge as triples, where every entity has a URI. |
| **OWL** | A language built on RDF for defining ontologies — adding class hierarchies, logic, and constraints. |
| **Ontology** | A formal vocabulary: defines concepts, their meanings, and how they relate to each other. |
| **HPO** | Human Phenotype Ontology — a standardized vocabulary of ~17,000 human clinical symptoms. |
| **HPOA** | HPO Annotations — a curated database linking diseases to HPO phenotype terms with evidence. |
| **OMIM** | Online Mendelian Inheritance in Man — a database of genetic diseases, referenced by ID (e.g., OMIM:619340). |
| **Turtle** | A human-readable text format for RDF triples. Easier to read than the XML-based OWL format. |
| **URI** | Uniform Resource Identifier — a unique web-style address that identifies a concept globally (e.g., `http://purl.obolibrary.org/obo/HP_0100651`). |
| **Cypher** | The query language for Neo4j — like SQL but for graphs. Uses `MATCH`, `MERGE`, `RETURN`. |
| **Bolt** | The network protocol Neo4j uses. The Python driver sends Cypher over Bolt. |
| **MERGE** | A Cypher command meaning "create this node/relationship if it does not exist, otherwise match it." Prevents duplicates. |
| **Reification** | Making a relationship itself a node so it can carry properties. Used in nb04 with a blank node to attach source + date to a disease-phenotype link. |
| **Evidence codes** | IEA = inferred from electronic annotation (auto-extracted), PCS = published clinical study, TAS = author statement from a knowledge base. |
| **Aspect codes** | P = phenotypic abnormality, I = inheritance mode (indicates what sub-ontology a phenotype belongs to). |
| **Semantic inference** | Finding facts that are not directly stated but can be derived by following ontology hierarchies. |
| **RAG** | Retrieval Augmented Generation — a pattern where an LLM's response is grounded in retrieved facts, reducing hallucinations. |
| **Triple extraction** | Using an LLM to convert free-text sentences into structured `[entity, TYPE, RELATION, entity, TYPE]` triples. |

---

## 8. Overall Data Flow

The diagram below shows how every component connects, from raw files to the final LLM integration.

```
════════════════════════════════════════════════════════════════════════════
RAW INPUT FILES
════════════════════════════════════════════════════════════════════════════

 data/hp.owl                data/phenotype_local.hpoa       data/pubmed/*.txt
 ─────────────               ─────────────────────────       ────────────────
 OWL ontology               TSV annotation file             PubMed abstracts
 905,482 triples            280,730 rows                    plain text
 ~17,000 phenotype          disease → HPO term links        biomedical articles
 classes + hierarchy        with evidence & provenance

════════════════════════════════════════════════════════════════════════════
PIPELINE A — LOCAL PYTHON  (Notebooks 01–04, no database)
════════════════════════════════════════════════════════════════════════════

 hp.owl ──[rdflib.Graph.parse()]──► in-memory RDF graph
                                          │
                 phenotype_local.hpoa ──[pandas.read_csv()]──► df_hpoa
                                          │
                              nb03: join both in Python
                              ├── regex: parse biocuration field
                              ├── URI lookup: HP:0410050 → rdfs:label
                              └──► readable_tuple
                                   ('OMIM:222100', 'Type I diabetes...',
                                    'HP:0410050', 'Decreased level of...',
                                    'Nicole Vasilevsky', '2018-02-23',
                                    'PMID:9357814')
                                          │
                              nb04: rdflib (writing mode)
                              Build 11-triple RDF graph:
                               OMIM:222100 ──hasAnnotation──► [blank node]
                               [blank node] ──hasPhenotypicFeature──► HP:0410050
                               [blank node].source = "PMID:9357814"
                               [blank node].createdBy = "Nicole Vasilevsky"
                              Serialize → Turtle (printed to screen)

════════════════════════════════════════════════════════════════════════════
PIPELINE B — NEO4J GRAPH  (Notebooks 05–08, persistent database)
════════════════════════════════════════════════════════════════════════════

 nb05: neo4j driver
 ├── CREATE DATABASE hpo
 ├── CREATE CONSTRAINT :Resource(uri)     ← required by n10s
 ├── CREATE INDEX :HpoDisease(id)
 ├── CREATE INDEX :HpoPhenotype(id)
 └── CALL n10s.graphconfig.init()
       handleVocabUris=IGNORE
       applyNeo4jNaming=true

 ── [MANUAL STEP in Neo4j Browser] ─────────────────────────────────────
 CALL n10s.rdf.import.fetch('file:///...hp.owl', 'RDF/XML')
 n10s translates every owl:Class   → :Resource node
                  rdfs:subClassOf  → :SUBCLASSOF relationship
 Result: ~17,000 HpoPhenotype nodes arranged in hierarchy
 ────────────────────────────────────────────────────────────────────────

 nb06: neo4j driver + APOC
 ├── Inspect: node counts, label distribution, sample data
 └── Enrich HP nodes:
     SET n:HpoPhenotype
     SET n.id = apoc.text.replace(n.uri,'(.*)obo/','')
                → replace('_',':') → "HP:0100651"

 nb07: neo4j driver (LOAD CSV) + APOC
 ├── LOAD CSV 'https://mng.bz/qRyr'
 ├── MERGE (:HpoDisease {id: row[0]})          12,996 disease nodes
 ├── MERGE (dis)-[:HAS_PHENOTYPIC_FEATURE]
         ->(phe:HpoPhenotype)                   disease→phenotype links
 ├── SET rel.evidence, rel.onset,
         rel.frequency, rel.source ...         raw metadata
 └── CALL apoc.periodic.iterate(...)
     batchSize: 1000
     ├── apoc.text.regexGroups(biocuration)    parse "HPO:probinson[2021-06-21]"
     ├── rel.createdBy   = "probinson"
     ├── rel.creationDate = "2021-06-21"
     ├── rel.evidenceName = "Published clinical study"
     └── rel.url = "https://pubmed.ncbi.nlm.nih.gov/31675180"

 ┌────────────────────────────────────────────────────────────────────┐
 │  NEO4J DATABASE  "hpo"  (final state after nb07)                   │
 │                                                                    │
 │  :HpoPhenotype nodes  (~17,000)                                    │
 │    { uri, id:"HP:0100651", label:"Type I diabetes mellitus" }      │
 │                                                                    │
 │  :HpoDisease nodes  (12,996)                                       │
 │    { id:"OMIM:619340", label:"Developmental and epileptic..." }    │
 │                                                                    │
 │  :SUBCLASSOF relationships  (ontology hierarchy)                   │
 │    HP:0100651 -[SUBCLASSOF]→ HP:0000819 (Diabetes mellitus)       │
 │                                                                    │
 │  :HAS_PHENOTYPIC_FEATURE relationships  (disease → phenotype)      │
 │    OMIM:619340 -[HAS_PHENOTYPIC_FEATURE]→ HP:0011097              │
 │    { evidence:"PCS", frequency:"1/2", createdBy:"probinson",       │
 │      creationDate:"2021-06-21", url:"https://pubmed.../31675180" } │
 └────────────────────────────────────────────────────────────────────┘

 nb08: neo4j driver + n10s inference
 ├── Direct query:
 │   MATCH (d:HpoDisease)-[:HAS_PHENOTYPIC_FEATURE]
 │         ->(:HpoPhenotype {label:'Growth abnormality'})
 │   → finds only diseases annotated to THAT EXACT node
 │
 └── Inferred query:
     CALL n10s.inference.nodesInCategory(cat, {
       inCatRel:'HAS_PHENOTYPIC_FEATURE',
       subCatRel:'SUBCLASSOF'
     })
     → traverses full SUBCLASSOF hierarchy downward
     → finds diseases annotated to ANY descendant phenotype
     → far more diseases discovered via ontology reasoning

════════════════════════════════════════════════════════════════════════════
PIPELINE C — LLM INTEGRATION  (Notebook 09 + Triple Viewer)
════════════════════════════════════════════════════════════════════════════

 data/pubmed/39549628.txt          data/prompt/system_prompt_typed.txt
 ──────────────────────            ───────────────────────────────────
 "The molecular mechanisms         12 fixed entity types:
  of steroid hormone effects        GENE, DISEASE, BACTERIA,
  on cognitive function..."         CHEMICAL, MIRNA, PATHWAY, ...
           │                                  │
           └──────────────┬───────────────────┘
                          │
                   nb09: openai.AzureOpenAI
                   system_prompt + user_prompt
                   {document_text} → replaced with article text
                          │
                          ▼
                  Azure OpenAI API
                  (gpt-5.4-llm-kb-lessons)
                          │
                          ▼
              Extracted triples (structured output):
              [testosterone, STEROID_HORMONE, REGULATE, cognitive impairment, DISEASE]
              [INS, GENE, REGULATE, cognitive function, PHENOTYPE]
              [Lactobacillus amylovorus, BACTERIA, ASSOCIATED_WITH, cognitive impairment, DISEASE]
              [minocycline, DRUG, TREATS, dementia, DISEASE]
              ...
                          │
                          ▼  (same logic, browser UI)
              triple_viewer/app.py  (Flask, port 5001)
              ├── Load pubmed text + choose prompt
              ├── Call Azure OpenAI
              ├── parse_triples() — regex on response text
              ├── highlight_entities() — color-code entities in text
              │   (DISEASE=red, CHEMICAL=blue, GENE=green, etc.)
              ├── Render interactive relation graph
              └── Show token cost breakdown

 ══ FUTURE INTEGRATION (implied by requirements.txt) ══════════════════
 LLM-extracted triples
         │
         ▼
 sentence-transformers → embeddings for similarity
 faiss-cpu → vector search over KG content
 Neo4j ← MERGE new nodes/rels from LLM extraction
 (connecting Pipelines B and C into a unified system)
```

---

## 9. Pipeline A — Local RDF and Pandas (Notebooks 01–04)

These four notebooks work **entirely in memory**. There is no database. The goal is to learn what the raw data looks like and practice working with RDF and annotation data in Python before loading anything into Neo4j.

---

### Notebook 01 — Parse the Ontology, Inspect Triples

**File:** [notebooks/01-rdflib-hp-class-triples.ipynb](notebooks/01-rdflib-hp-class-triples.ipynb)

**Learning objectives:** Load an OWL ontology with rdflib. Understand what triples look like. Build a function that extracts all triples for a given class.

| | |
|---|---|
| **Input** | `data/hp.owl` — read from disk |
| **Library** | `rdflib` |
| **Output** | Turtle-format triples for `HP_0100651` printed to screen |

**What happens:**

1. `rdflib.Graph().parse(hp_owl_path)` loads the OWL file into memory — all 905,482 triples.
2. `resolve_class_uri()` takes a class ID string like `"HP_0100651"` or `"HP:0100651"`, normalizes it, and finds the matching URI in the graph.
3. `class_related_triples_as_turtle()` collects all triples where that class is the subject (and optionally all where it is the object), copies namespace bindings for readable output, and serializes them to Turtle.

**What the Turtle output looks like:**

```turtle
obo:HP_0100651 a owl:Class ;
    rdfs:label "Type I diabetes mellitus" ;
    obo:IAO_0000115 "A chronic condition in which the pancreas produces little
                     or no insulin..." ;
    oboInOwl:hasExactSynonym "Type 1 diabetes", "Juvenile diabetes mellitus" ;
    oboInOwl:id "HP:0100651" ;
    rdfs:subClassOf obo:HP_0000819 .
```

**Key takeaway:** This is the raw data that n10s will later import into Neo4j automatically. Each line above becomes one triple `(HP_0100651, predicate, value)`.

---

### Notebook 02 — Load the Annotation File, Sanity Check

**File:** [notebooks/02-load-phenotype-local-hpoa.ipynb](notebooks/02-load-phenotype-local-hpoa.ipynb)

**Learning objectives:** Load a TSV annotation file with pandas. Explore its schema and data quality.

| | |
|---|---|
| **Input** | `data/phenotype_local.hpoa` (280,730 rows, 12 columns) |
| **Library** | `pandas` |
| **Output** | `df_hpoa` DataFrame in memory |

**What happens:**

`pandas.read_csv()` reads the file with `sep='\t'` and `dtype='string'` to avoid mixed-type warnings. The notebook then inspects:
- Column names and dtypes
- Per-column missing value counts
- Completely empty columns (`qualifier`, `sex`, `modifier` are mostly empty)

**What the DataFrame looks like (one row):**

| database_id | disease_name | hpo_id | reference | evidence | frequency | aspect | biocuration |
|---|---|---|---|---|---|---|---|
| OMIM:619340 | Developmental and epileptic encephalopathy 96 | HP:0011097 | PMID:31675180 | PCS | 1/2 | P | HPO:probinson[2021-06-21] |

**Key takeaway:** The `biocuration` column bundles author and date together as `HPO:probinson[2021-06-21]`. This will need parsing in the next notebook.

---

### Notebook 03 — Extract a Clean Tuple, Resolve Labels

**File:** [notebooks/03-extract-hpoa-tuple-and-resolve-labels.ipynb](notebooks/03-extract-hpoa-tuple-and-resolve-labels.ipynb)

**Learning objectives:** Combine two data sources in Python. Parse free-text fields with regex. Resolve IDs to human-readable labels using the ontology.

| | |
|---|---|
| **Input** | `df_hpoa` (re-loaded) + `data/hp.owl` (re-parsed) + HPO website as fallback |
| **Libraries** | `pandas` + `rdflib` + `re` + `urllib` |
| **Output** | `readable_tuple` in memory |

**What happens:**

1. **Clean the DataFrame:** Rename columns. Parse `biocuration` with the regex `HPO:(\w+)\[(\d{4}-\d{2}-\d{2})\]` to extract `Author` and `Date`. Take the first value from the semicolon-separated `reference` column as `Source`.

2. **Select one example:** Filter to `OMIM:222100` + `HP:0410050` and build a target tuple.

3. **Resolve labels:** Convert `HP:0410050` to its OBO URI, search the rdflib graph for `(URI, rdfs:label, ?)`, and retrieve `"Decreased level of 1,5 anhydroglucitol in serum"`. For two terms where the graph lookup fails, fall back to scraping the HPO website.

**Final result:**
```python
readable_tuple = (
    'OMIM:222100',
    'Type I diabetes mellitus',
    'HP:0410050',
    'Decreased level of 1,5 anhydroglucitol in serum',
    'Nicole Vasilevsky',
    '2018-02-23',
    'PMID:9357814'
)
```

**Key takeaway:** This shows that the `.hpoa` file only contains IDs — the labels live in the `.owl` file. Resolving them requires querying the ontology, which is exactly what the graph will let you do at scale in Neo4j.

---

### Notebook 04 — Build a Custom RDF Phenotypic Annotation Graph

**File:** [notebooks/04-build-rdf-phenotypic-annotation-graph.ipynb](notebooks/04-build-rdf-phenotypic-annotation-graph.ipynb)

**Learning objectives:** Build an RDF graph programmatically. Understand reification (a relationship with properties). Serialize to Turtle.

| | |
|---|---|
| **Input** | The example tuple from notebook 03 (hard-coded) + `data/hp.owl` to verify the HP term exists |
| **Library** | `rdflib` (writing mode) |
| **Output** | 11-triple Turtle-serialized RDF graph printed to screen |

**What happens:**

A custom RDF graph is built from scratch using rdflib's programmatic API:

```python
EX = Namespace("http://example.org/kb/")

# Disease individual
g.add((EX.OMIM_222100, RDF.type, EX.Disease))

# Blank node = the annotation event itself
x = BNode()
g.add((EX.OMIM_222100, EX.hasAnnotation, x))
g.add((x, RDF.type, EX.PHENOTYPIC_ANNOTATION))
g.add((x, EX.hasPhenotypicFeature, obo.HP_0410050))

# Provenance on the blank node
g.add((x, EX.source, Literal("PMID:9357814")))
g.add((x, EX.createdBy, Literal("Nicole Vasilevsky")))
g.add((x, EX.creationDate, Literal("2018-02-23", datatype=XSD.date)))
```

The blank node pattern (`BNode`) is called **reification** — instead of a direct `OMIM:222100 → HP:0410050` edge, you create an intermediate node that represents the annotation event and can carry properties (source, author, date).

**Key takeaway:** This small 11-triple graph mirrors the data model Neo4j will use at scale in notebook 07, where the provenance data becomes properties on the `HAS_PHENOTYPIC_FEATURE` relationship rather than a blank node.

---

## 10. Pipeline B — Neo4j Graph Construction (Notebooks 05–08)

These notebooks build and populate the actual graph database. Neo4j Desktop must be running locally with the **n10s** and **APOC** plugins enabled.

**Important:** Between notebooks 05 and 06, you must manually run the OWL import in the Neo4j Browser — the step that loads `hp.owl` into the graph. Notebook 05 sets up the schema; notebook 06 assumes the import has already been done.

---

### Notebook 05 — Connect to Neo4j, Create Schema

**File:** [notebooks/05-connect-neo4j-kb-llm-hpo.ipynb](notebooks/05-connect-neo4j-kb-llm-hpo.ipynb)

**Learning objectives:** Connect to Neo4j from Python. Create constraints, indexes, and initialize n10s configuration.

| | |
|---|---|
| **Input** | Running Neo4j at `neo4j://127.0.0.1:7687`, empty `hpo` database |
| **Library** | `neo4j` Python driver |
| **Output** | Schema-ready `hpo` database with constraints, indexes, and n10s config |

**What happens:**

The `neo4j.GraphDatabase.driver()` establishes a connection. All subsequent operations are Cypher strings sent to the server:

```cypher
-- Create the database
CREATE DATABASE hpo IF NOT EXISTS

-- Uniqueness constraints (n10s requires the uri one)
CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS
  FOR (r:Resource) REQUIRE r.uri IS UNIQUE

-- Indexes for fast lookups during HPOA loading
CREATE INDEX disease_id IF NOT EXISTS FOR (n:HpoDisease) ON (n.id)
CREATE INDEX phenotype_id IF NOT EXISTS FOR (n:HpoPhenotype) ON (n.id)

-- Initialize n10s RDF configuration
CALL n10s.graphconfig.init()
CALL n10s.graphconfig.set({ handleVocabUris: "IGNORE" })
CALL n10s.graphconfig.set({ applyNeo4jNaming: true })
```

The entire schema setup is guarded: if the graph already has nodes (node count > 0), all steps are skipped safely, so the notebook can be re-run without errors.

**What `handleVocabUris: "IGNORE"` means:** When n10s imports the OWL file, it encounters long namespace prefixes in predicates (e.g., `http://www.w3.org/2000/01/rdf-schema#label`). With `IGNORE`, it uses only the local name (`label`), producing shorter, cleaner property names in Neo4j.

---

### Notebook 06 — Verify HPO Load, Enrich Phenotype Nodes

**File:** [notebooks/06-check-hpo-database-populated.ipynb](notebooks/06-check-hpo-database-populated.ipynb)

**Learning objectives:** Query a loaded graph. Use APOC for string manipulation. Enrich nodes with derived properties and labels.

| | |
|---|---|
| **Input** | Neo4j `hpo` database populated with `hp.owl` via n10s (done manually) |
| **Libraries** | `neo4j` driver + APOC plugin (server-side) |
| **Output** | All HP nodes gain the `HpoPhenotype` label and a readable `id` property |

**What happens:**

First, inspection queries confirm the OWL was loaded correctly (counts, sample data, label distribution). Then the enrichment:

```cypher
MATCH (n:Resource)
WHERE n.uri STARTS WITH 'http://purl.obolibrary.org/obo/HP'
SET n:HpoPhenotype,
    n.id = replace(
             apoc.text.replace(n.uri, '(.*)obo/', ''),
             '_', ':'
           )
```

This transforms `http://purl.obolibrary.org/obo/HP_0100651` into the label `HpoPhenotype` and the id `HP:0100651`. This is critical for notebook 07, which will match annotation rows by `phe.id = row[3]` (where `row[3]` is `HP:0011097` from the HPOA file).

---

### Notebook 07 — Load HPOA Annotations into Neo4j

**File:** [notebooks/07-load-hpoa-annotation-data.ipynb](notebooks/07-load-hpoa-annotation-data.ipynb)

**Learning objectives:** Use `LOAD CSV` to import data into Neo4j. Create relationship properties. Use APOC for batch processing and regex extraction.

| | |
|---|---|
| **Input** | HPOA file from URL (Neo4j fetches it directly) + existing `HpoPhenotype` nodes |
| **Libraries** | `neo4j` driver + APOC plugin (server-side) |
| **Output** | 12,996 `HpoDisease` nodes + `HAS_PHENOTYPIC_FEATURE` relationships with full metadata |

**What happens (four Cypher steps):**

**Step 1 — Create disease nodes:**
```cypher
LOAD CSV FROM 'https://mng.bz/qRyr' AS row FIELDTERMINATOR '\t'
WITH row SKIP 5
MERGE (dis:Resource:HpoDisease {id: row[0]})
  ON CREATE SET dis.label = row[1]
```
`MERGE` ensures no duplicates if multiple phenotype annotations exist for the same disease.

**Step 2 — Create relationships:**
```cypher
MATCH (dis:HpoDisease) WHERE dis.id = row[0]
MATCH (phe:HpoPhenotype) WHERE phe.id = row[3]
MERGE (dis)-[:HAS_PHENOTYPIC_FEATURE]->(phe)
```
This is where the two data sources come together — `HpoDisease` nodes (from HPOA) are linked to `HpoPhenotype` nodes (from `hp.owl`) using their shared HPO term IDs.

**Step 3 — Set raw metadata on relationships:**
```cypher
FOREACH(_ IN CASE WHEN row[5] IS NOT NULL THEN [1] ELSE [] END |
  SET rel.evidence = row[5])
-- ... same pattern for onset, frequency, sex, modifier, aspect, biocuration
```
The `FOREACH` trick is a null-safe conditional SET — it only sets the property if the column is not empty.

**Step 4 — Enrich with APOC (batch processing):**
```cypher
CALL apoc.periodic.iterate(
  "MATCH (dis:HpoDisease)-[rel:HAS_PHENOTYPIC_FEATURE]->(phe:HpoPhenotype) RETURN rel",
  "SET rel.createdBy   = apoc.text.regexGroups(rel.biocuration, 'HPO:(\\w+)\\[')[0][1],
       rel.creationDate = apoc.text.regexGroups(rel.biocuration, '\\[(\\d{4}-\\d{2}-\\d{2})\\]')[0][1],
       rel.evidenceName = CASE
         WHEN rel.evidence = 'IEA' THEN 'Inferred from electronic annotation'
         WHEN rel.evidence = 'PCS' THEN 'Published clinical study'
         WHEN rel.evidence = 'TAS' THEN 'Traceable author statement'
       END,
       rel.url = CASE
         WHEN rel.source STARTS WITH 'PMID:' THEN
           'https://pubmed.ncbi.nlm.nih.gov/' + apoc.text.replace(rel.source,'(.*)PMID:','')
       END",
  {batchSize: 1000}
)
```
This converts the raw `HPO:probinson[2021-06-21]` string into `createdBy="probinson"` and `creationDate="2021-06-21"`, expands evidence codes to full names, and builds clickable PubMed URLs.

---

### Notebook 08 — Semantic Inference Over the HPO Graph

**File:** [notebooks/08-semantic-inference-hpo.ipynb](notebooks/08-semantic-inference-hpo.ipynb)

**Learning objectives:** Understand the difference between direct queries and ontology-aware inference. Use `n10s.inference` procedures.

| | |
|---|---|
| **Input** | Fully populated Neo4j `hpo` graph |
| **Libraries** | `neo4j` driver + n10s plugin (server-side) |
| **Output** | Read-only query results showing semantic inference |

**What happens:**

The key demonstration is comparing two queries for the same question: "Which diseases are related to Growth abnormality?"

**Direct query (misses descendants):**
```cypher
MATCH (cat:HpoPhenotype {label: 'Growth abnormality'})
MATCH (d:HpoDisease)-[:HAS_PHENOTYPIC_FEATURE]->(cat)
RETURN d.label
```
This only finds diseases directly annotated to the *Growth abnormality* node itself. It misses diseases annotated to *Short stature*, *Tall stature*, *Overgrowth*, etc. — all of which are subtypes of *Growth abnormality*.

**Inferred query (follows full hierarchy):**
```cypher
MATCH (cat:HpoPhenotype {label: 'Growth abnormality'})
CALL n10s.inference.nodesInCategory(cat, {
    inCatRel: 'HAS_PHENOTYPIC_FEATURE',
    subCatRel: 'SUBCLASSOF'
}) YIELD node AS dis
WHERE dis:HpoDisease
RETURN dis.label
```
`n10s.inference.nodesInCategory` traverses all `SUBCLASSOF` links downward from *Growth abnormality*, then for each descendant phenotype finds any `HAS_PHENOTYPIC_FEATURE` relationship pointing to a disease node. It discovers hundreds of diseases instead of just a handful.

**Key takeaway:** This is the payoff of loading an ontology into the graph. The hierarchy provides the semantic structure for inference that a plain annotation table cannot support.

---

## 11. Pipeline C — LLM Integration (Notebook 09 and Triple Viewer)

This pipeline is **independent of the Neo4j database**. It demonstrates a second approach to building knowledge graphs: using an LLM to extract structured facts from unstructured scientific text.

---

### Notebook 09 — Connect to Azure OpenAI, Extract Triples from PubMed

**File:** [notebooks/09-connect-azure-openai-llm.ipynb](notebooks/09-connect-azure-openai-llm.ipynb)

**Learning objectives:** Connect to Azure OpenAI from Python. Design prompts for structured information extraction. Extract typed entity-relation triples from biomedical text.

| | |
|---|---|
| **Input** | `data/pubmed/39549628.txt` + prompt files + Azure API key (entered interactively) |
| **Library** | `openai` Python SDK |
| **Output** | Extracted triples printed to screen + token usage |

**What the prompt files do:**

- `data/prompt/system_prompt_generic.txt` — open-schema prompt. The model chooses entity type names freely. Good for exploratory extraction.
- `data/prompt/system_prompt_typed.txt` — closed-schema prompt. Defines 12 fixed entity types (GENE, DISEASE, BACTERIA, CHEMICAL, MIRNA, PATHWAY, TRANSCRIPTION_FACTOR, etc.) and a vocabulary of relation types. Used for the gut-brain axis domain. Produces more consistent, comparable output.
- `data/prompt/user_prompt.txt` — a single-line template: `"Extract entities and relations from the following document.\n\nDocument:\n{document_text}"`. The `{document_text}` placeholder is replaced at runtime.

**What the LLM returns (from the PubMed abstract about steroid hormones):**

```
[testosterone, STEROID_HORMONE, REGULATE, cognitive impairment, DISEASE]
[INS, GENE, REGULATE, cognitive function, PHENOTYPE]
[hsa-miR-335-5p, MIRNA, PLAYS_ROLE_IN, protective effects, BIOLOGICAL_PROCESS]
[Lactobacillus amylovorus, BACTERIA, ASSOCIATED_WITH, cognitive impairment, DISEASE]
[minocycline, DRUG, TREATS, dementia, DISEASE]
```

Each triple is in the format `[entity1, TYPE1, RELATION, entity2, TYPE2]` — five fields, machine-parseable.

**Key takeaway:** LLM extraction is fast and scales to any new paper instantly. The tradeoff is quality — the LLM may miss some facts or occasionally invent one. The curated Neo4j graph provides the reliable ground truth; LLM extraction provides rapid coverage of new literature.

---

### Triple Viewer — `triple_viewer/app.py`

**File:** [triple_viewer/app.py](triple_viewer/app.py)

**What it is:** A local Flask web application (port 5001) that wraps notebook 09's logic in a visual, interactive browser interface.

| | |
|---|---|
| **Input** | User selects a PubMed `.txt` file + a system prompt + enters Azure API key |
| **Library** | `flask` + `openai` |
| **Output** | Browser UI with highlighted text, interactive triple graph, cost breakdown |

**What it does:**

1. **Text loading:** User selects one of the `data/pubmed/*.txt` files.
2. **Prompt selection:** User chooses a system prompt (`generic` for open types, `typed` for the 12-type vocabulary).
3. **LLM call:** On clicking Extract, the app calls Azure OpenAI with the selected document and prompt, then parses the response with a regex: `\[([^\]]+)\]` matching the `[e1, T1, REL, e2, T2]` format.
4. **Entity highlighting:** The function `highlight_entities()` scans the original document text for each extracted entity and wraps it in a colored `<mark>` HTML tag. Different entity types get different colors (e.g., DISEASE = red, GENE = green, CHEMICAL = blue). Longest spans are matched first to prevent sub-span collisions.
5. **Graph visualization:** Extracted triples are rendered as an interactive edge-node graph in the browser.
6. **Cost tracking:** Records prompt/completion/cached token counts and calculates dollar cost at hard-coded rates ($2.50 input / $15.00 output / $0.25 cached per 1M tokens).

**Where it fits in the big picture:**

The triple viewer is a standalone teaching tool for the LLM extraction half of the course. It does not currently write to or read from Neo4j. The natural next step — loading extracted triples into the graph via `MERGE` queries — is implied by the `sentence-transformers` and `faiss-cpu` entries in `requirements.txt`, suggesting a future module on semantic search and LLM-to-graph integration.

---

*End of document.*