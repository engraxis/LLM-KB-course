"""
Triple Viewer – Entity & Relation Visualizer
=============================================
A lightweight Flask app that highlights entities in a document and
draws a knowledge-graph of extracted triples.

Run:
    cd triple_viewer
    pip install flask openai
    python app.py

Then open http://127.0.0.1:5001
"""

import re
from pathlib import Path
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from markupsafe import Markup

app = Flask(__name__)
app.secret_key = "triple-viewer-dev-key"  # needed for session

# ── Locate sample data shipped with the project ────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBMED_DIR = PROJECT_ROOT / "data" / "pubmed"
PROMPT_DIR = PROJECT_ROOT / "data" / "prompt"

# ── Azure OpenAI settings (same as notebook 09) ────────────────────────
AZURE_ENDPOINT = "https://gianm-m6osfju4-eastus2.openai.azure.com/"
AZURE_API_VERSION = "2024-12-01-preview"
AZURE_DEPLOYMENT = "gpt-5.4-llm-kb-lessons"
AZURE_MODEL_NAME = "gpt-5.4"

# ── GPT-5.4 pricing (USD per 1 M tokens) ───────────────────────────────
PRICE_INPUT_PER_M   = 2.50     # standard input tokens
PRICE_OUTPUT_PER_M  = 15.00    # output / completion tokens
PRICE_CACHED_PER_M  = 0.25     # cached input tokens

SAMPLE_TRIPLES = """\
[Steroid hormones, CHEMICAL, REGULATE, cognitive impairment, DISEASE]
[testosterone, STEROID_HORMONE, REGULATE, cognitive impairment, DISEASE]
[estrogen, STEROID_HORMONE, REGULATE, cognitive impairment, DISEASE]
[progesterone, STEROID_HORMONE, REGULATE, cognitive impairment, DISEASE]
[Steroid hormones, CHEMICAL, REGULATE, INS, GENE]
[Steroid hormones, CHEMICAL, REGULATE, TNF, GENE]
[Steroid hormones, CHEMICAL, REGULATE, STAT3, GENE]
[Steroid hormones, CHEMICAL, REGULATE, ESR1, GENE]
[hsa-miR-335-5p, MIRNA, INVOLVED_IN, cognitive impairment, DISEASE]
[hsa-miR-16-5p, MIRNA, INVOLVED_IN, cognitive impairment, DISEASE]
[hsa-miR-26b-5p, MIRNA, INVOLVED_IN, cognitive impairment, DISEASE]
[capsaicin, CHEMICAL, TREATS, cognitive impairment, DISEASE]
[minocycline, CHEMICAL, TREATS, cognitive impairment, DISEASE]
[dopamine, CHEMICAL, TREATS, cognitive impairment, DISEASE]
[sertraline, CHEMICAL, TREATS, cognitive impairment, DISEASE]
[Lactobacillus amylovorus, ORGANISM, CONTRIBUTES_TO, cognitive impairment, DISEASE]
[Steroid hormones, CHEMICAL, TREATS, dementia, DISEASE]
[Steroid hormones, CHEMICAL, TREATS, Alzheimer's disease, DISEASE]"""

# ── Colour palette per entity type ──────────────────────────────────────
TYPE_COLORS = {
    # Diseases & conditions
    "DISEASE":                "#ff9999",
    "DISORDER":               "#ff9999",
    "CONDITION":              "#ff9999",
    "NEUROLOGICAL_DISORDER":  "#ff8080",
    "PSYCHIATRIC_CONDITION":  "#ff8080",
    "GASTROINTESTINAL_DISORDER": "#ff8080",
    # Chemicals & drugs
    "CHEMICAL":               "#99ccff",
    "DRUG":                   "#85bfff",
    "COMPOUND":               "#85bfff",
    "PHARMACEUTICAL_AGENT":   "#85bfff",
    # Hormones
    "STEROID_HORMONE":        "#b3e6b3",
    "HORMONE":                "#a3d9a3",
    # Genes & transcription factors
    "GENE":                   "#ffd699",
    "TRANSCRIPTION_FACTOR":   "#ffc266",
    # RNA
    "MIRNA":                  "#e6ccff",
    "MICRORNA":               "#e6ccff",
    "RNA":                    "#d9b3ff",
    # Proteins
    "PROTEIN":                "#c2f0f0",
    "RECEPTOR":               "#a8e8e8",
    "ENZYME":                 "#a8e8e8",
    # Organisms & microbiota
    "ORGANISM":               "#ffcceb",
    "BACTERIA":               "#ffb3d9",
    "MICROBIOTA":             "#ffb3d9",
    "GUT_MICROBIOTA":         "#ffb3d9",
    "SPECIES":                "#ffb3d9",
    # Metabolites & molecules
    "METABOLITE":             "#e6e6b3",
    "NEUROTRANSMITTER":       "#d6d699",
    "MOLECULE":               "#d6d699",
    # Biological processes & pathways
    "BIOLOGICAL_PROCESS":     "#c2d9f2",
    "PATHWAY":                "#b3cce6",
    "SIGNALING_PATHWAY":      "#b3cce6",
    "MOLECULAR_MECHANISM":    "#b3cce6",
    "PROCESS":                "#c2d9f2",
    # Phenotype / symptom
    "PHENOTYPE":              "#f2c2c2",
    "SYMPTOM":                "#f2c2c2",
    # Anatomy & body parts
    "ANATOMY":                "#c2e0c6",
    "TISSUE":                 "#c2e0c6",
    "ORGAN":                  "#c2e0c6",
    # Therapeutic / intervention
    "THERAPY":                "#d4c2f0",
    "INTERVENTION":           "#d4c2f0",
    "TREATMENT":              "#d4c2f0",
}
DEFAULT_COLOR = "#dddddd"

# Fallback palette for types not in TYPE_COLORS — cycled automatically
_EXTRA_COLORS = [
    "#f0b27a", "#7dcea0", "#85c1e9", "#f1948a",
    "#bb8fce", "#82e0aa", "#f7dc6f", "#aed6f1",
    "#d7bde2", "#a9dfbf", "#fadbd8", "#d5f5e3",
]


def color_for_type(etype: str) -> str:
    """Return a colour for an entity type, assigning one dynamically if needed."""
    upper = etype.upper()
    if upper not in TYPE_COLORS:
        idx = len(TYPE_COLORS) % len(_EXTRA_COLORS)
        TYPE_COLORS[upper] = _EXTRA_COLORS[idx]
    return TYPE_COLORS[upper]


# ── Triple parser ───────────────────────────────────────────────────────
TRIPLE_RE = re.compile(
    r"\[\s*"
    r"([^,\]]+?)\s*,\s*"   # entity1
    r"([^,\]]+?)\s*,\s*"   # type1
    r"([^,\]]+?)\s*,\s*"   # relation
    r"([^,\]]+?)\s*,\s*"   # entity2
    r"([^,\]]+?)\s*"        # type2
    r"]"
)


def parse_triples(raw: str) -> list[dict]:
    """Return list of dicts with keys e1, t1, rel, e2, t2."""
    triples = []
    for m in TRIPLE_RE.finditer(raw):
        triples.append({
            "e1":  m.group(1).strip(),
            "t1":  m.group(2).strip().upper(),
            "rel": m.group(3).strip(),
            "e2":  m.group(4).strip(),
            "t2":  m.group(5).strip().upper(),
        })
    return triples


# ── Entity highlighter ──────────────────────────────────────────────────
def highlight_entities(text: str, triples: list[dict]) -> str:
    """Return HTML with entity spans wrapped in coloured <mark> tags."""

    # Collect unique (span, type) pairs
    entities: dict[str, str] = {}
    for t in triples:
        entities.setdefault(t["e1"], t["t1"])
        entities.setdefault(t["e2"], t["t2"])

    # Sort longest-first so longer spans get matched before sub-spans
    sorted_spans = sorted(entities.keys(), key=len, reverse=True)

    # Build a list of (start, end, span_text, entity_type)
    annotations: list[tuple[int, int, str, str]] = []
    for span_text in sorted_spans:
        etype = entities[span_text]
        escaped = re.escape(span_text)
        # Use word-boundary lookarounds so "INS" does not match
        # inside "against", but "INS," or "(INS)" still tag "INS".
        pattern = re.compile(r"(?<!\w)" + escaped + r"(?!\w)", re.IGNORECASE)
        for m in pattern.finditer(text):
            annotations.append((m.start(), m.end(), span_text, etype))

    # Remove overlapping annotations (keep longest / earliest)
    annotations.sort(key=lambda a: (a[0], -(a[1] - a[0])))
    filtered: list[tuple[int, int, str, str]] = []
    last_end = -1
    for start, end, span_text, etype in annotations:
        if start >= last_end:
            filtered.append((start, end, span_text, etype))
            last_end = end

    # Build highlighted HTML
    parts: list[str] = []
    cursor = 0
    for start, end, span_text, etype in filtered:
        # Append un-annotated text before this span
        if start > cursor:
            from markupsafe import escape
            parts.append(str(escape(text[cursor:start])))
        color = color_for_type(etype)
        from markupsafe import escape
        parts.append(
            f'<mark class="entity" style="background:{color};" '
            f'title="{etype}">{escape(text[start:end])}'
            f'<sub class="entity-label">{etype}</sub></mark>'
        )
        cursor = end
    # Remaining text
    if cursor < len(text):
        from markupsafe import escape
        parts.append(str(escape(text[cursor:])))

    return "".join(parts)


# ── Available PubMed files ──────────────────────────────────────────────
def available_pubmed_files() -> list[str]:
    if PUBMED_DIR.exists():
        return sorted(f.name for f in PUBMED_DIR.glob("*.txt"))
    return []


# ── Available prompt files ──────────────────────────────────────────────
def available_prompt_files() -> list[str]:
    """Return system prompt filenames from data/prompt (exclude user_prompt)."""
    if PROMPT_DIR.exists():
        return sorted(
            f.name for f in PROMPT_DIR.glob("*.txt")
            if "user_prompt" not in f.name.lower()
        )
    return []


def available_user_prompt_files() -> list[str]:
    """Return user prompt filenames from data/prompt."""
    if PROMPT_DIR.exists():
        return sorted(
            f.name for f in PROMPT_DIR.glob("*.txt")
            if "user_prompt" in f.name.lower()
        )
    return []


def get_azure_client():
    """Create an AzureOpenAI client from the session key. Returns None if no key."""
    api_key = session.get("azure_api_key", "").strip()
    if not api_key:
        return None
    from openai import AzureOpenAI
    return AzureOpenAI(
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_ENDPOINT,
        api_key=api_key,
    )


# ── Routes ──────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    files = available_pubmed_files()
    system_prompts = available_prompt_files()
    user_prompts = available_user_prompt_files()

    # Defaults for GET
    doc_text = ""
    triples_raw = SAMPLE_TRIPLES
    highlighted = ""
    triples = []
    selected_file = ""
    selected_system_prompt = system_prompts[0] if system_prompts else ""
    selected_user_prompt = user_prompts[0] if user_prompts else ""
    llm_error = ""
    llm_usage = None
    has_api_key = bool(session.get("azure_api_key", "").strip())

    if request.method == "GET":
        # Pre-load the first available PubMed file
        if files:
            selected_file = files[0]
            doc_text = (PUBMED_DIR / selected_file).read_text(encoding="utf-8")
            triples_raw = SAMPLE_TRIPLES

    if request.method == "POST":
        # ── Handle API key submission ───────────────────────────────
        if request.form.get("action") == "save_key":
            session["azure_api_key"] = request.form.get("api_key", "")
            has_api_key = bool(session.get("azure_api_key", "").strip())

        # ── Handle clear key ────────────────────────────────────────
        if request.form.get("action") == "clear_key":
            session.pop("azure_api_key", None)
            has_api_key = False

        # ── Resolve document text ───────────────────────────────────
        uploaded = request.files.get("doc_upload")
        if uploaded and uploaded.filename:
            doc_text = uploaded.read().decode("utf-8", errors="replace")
            selected_file = uploaded.filename
        else:
            selected_file = request.form.get("selected_file", "")
            if selected_file and (PUBMED_DIR / selected_file).exists():
                doc_text = (PUBMED_DIR / selected_file).read_text(encoding="utf-8")
            else:
                doc_text = request.form.get("doc_text", "")

        triples_raw = request.form.get("triples_raw", "")
        selected_system_prompt = request.form.get("selected_system_prompt", selected_system_prompt)
        selected_user_prompt = request.form.get("selected_user_prompt", selected_user_prompt)

        # ── Handle LLM extraction ──────────────────────────────────
        if request.form.get("action") == "extract":
            has_api_key = bool(session.get("azure_api_key", "").strip())
            if not has_api_key:
                llm_error = "Please enter your Azure OpenAI API key first."
            elif not doc_text.strip():
                llm_error = "Please select or upload a document before extracting."
            else:
                try:
                    client = get_azure_client()
                    # Load system prompt
                    sys_path = PROMPT_DIR / selected_system_prompt
                    system_content = sys_path.read_text(encoding="utf-8").strip() if sys_path.exists() else ""
                    # Load user prompt template and inject document
                    usr_path = PROMPT_DIR / selected_user_prompt
                    if usr_path.exists():
                        user_template = usr_path.read_text(encoding="utf-8").strip()
                        if "{document_text}" in user_template:
                            user_content = user_template.replace("{document_text}", doc_text)
                        else:
                            user_content = user_template + "\n\nDocument:\n" + doc_text
                    else:
                        user_content = "Extract entities and relations from the following document.\n\nDocument:\n" + doc_text

                    response = client.chat.completions.create(
                        model=AZURE_DEPLOYMENT,
                        messages=[
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": user_content},
                        ],
                        temperature=0.3,
                    )
                    triples_raw = response.choices[0].message.content or ""
                    # Capture token usage & cost estimate
                    if response.usage:
                        u = response.usage
                        prompt_tok = u.prompt_tokens or 0
                        completion_tok = u.completion_tokens or 0
                        total_tok = u.total_tokens or 0
                        # Some responses include cached token counts
                        cached_tok = getattr(u, "cached_tokens", 0) or 0
                        # Non-cached input tokens
                        standard_input_tok = prompt_tok - cached_tok

                        input_cost = standard_input_tok * PRICE_INPUT_PER_M / 1_000_000
                        cached_cost = cached_tok * PRICE_CACHED_PER_M / 1_000_000
                        output_cost = completion_tok * PRICE_OUTPUT_PER_M / 1_000_000
                        total_cost = input_cost + cached_cost + output_cost

                        llm_usage = {
                            "model": response.model or AZURE_MODEL_NAME,
                            "prompt_tokens": prompt_tok,
                            "completion_tokens": completion_tok,
                            "total_tokens": total_tok,
                            "cached_tokens": cached_tok,
                            "input_cost": input_cost,
                            "cached_cost": cached_cost,
                            "output_cost": output_cost,
                            "total_cost": total_cost,
                        }
                except Exception as exc:
                    llm_error = f"LLM call failed: {type(exc).__name__}: {exc}"

        # ── Handle Visualize ────────────────────────────────────────
        if request.form.get("action") in ("visualize", "extract"):
            triples = parse_triples(triples_raw)
            if triples:
                highlighted = highlight_entities(doc_text, triples)

    # Build a colour map containing only the types that appear in the
    # current triples so the legend stays relevant.
    used_types: dict[str, str] = {}
    for t in triples:
        for tp in (t["t1"], t["t2"]):
            if tp not in used_types:
                used_types[tp] = color_for_type(tp)

    return render_template(
        "index.html",
        files=files,
        selected_file=selected_file,
        doc_text=doc_text,
        triples_raw=triples_raw,
        highlighted=Markup(highlighted),
        triples=triples,
        type_colors=used_types,
        default_color=DEFAULT_COLOR,
        system_prompts=system_prompts,
        user_prompts=user_prompts,
        selected_system_prompt=selected_system_prompt,
        selected_user_prompt=selected_user_prompt,
        has_api_key=has_api_key,
        llm_error=llm_error,
        llm_usage=llm_usage,
        azure_endpoint=AZURE_ENDPOINT,
        azure_deployment=AZURE_DEPLOYMENT,
        azure_model=AZURE_MODEL_NAME,
        price_input=PRICE_INPUT_PER_M,
        price_output=PRICE_OUTPUT_PER_M,
        price_cached=PRICE_CACHED_PER_M,
    )


@app.route("/file_content")
def file_content():
    """Return the text content of a PubMed file (AJAX helper)."""
    filename = request.args.get("name", "").strip()
    if not filename:
        return jsonify({"text": "", "error": "No filename provided"})
    path = PUBMED_DIR / filename
    if not path.exists() or not path.is_file():
        return jsonify({"text": "", "error": f"File not found: {filename}"})
    text = path.read_text(encoding="utf-8")
    return jsonify({"text": text, "error": ""})


if __name__ == "__main__":
    print("Triple Viewer running at http://127.0.0.1:5001")
    app.run(debug=True, port=5001)


