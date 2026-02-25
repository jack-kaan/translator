from copy import deepcopy
from datetime import datetime
import random

from core.pipeline import CATEGORIES, CORE_NODE_IDS, clone_initial_edges, clone_initial_nodes
from core.state import default_methodology_context, default_reference_form, default_rq_draft, default_workflow_builder


def make_id(prefix="id"):
    return f"{prefix}-{int(datetime.utcnow().timestamp() * 1000)}-{random.randint(1000, 999999)}"


def truncate(value, length=90):
    if len(value) <= length:
        return value
    return f"{value[: length - 3]}..."


def build_sample_payload(project_id):
    nodes = clone_initial_nodes()
    edges = clone_initial_edges()

    sample_sentences = [
        "Digital ethnography reveals recursive trust formation in distributed graduate research teams.",
        "Multilingual drafting friction increases cognitive load when citation formats shift between journals.",
        "Prior studies suggest mentor feedback cadence predicts completion probability.",
        "Observed cohorts show weekly feedback loops correlate with higher methodological consistency.",
        "A mixed design combining interview coding and survey triangulation reduced interpretation drift.",
        "Convenience sampling introduced regional bias and language-specific exclusion effects.",
        "Transparent coding memos improved inter-rater agreement across two coding rounds.",
        "Future work should test causality with longitudinal institutional datasets.",
    ]
    raw_text = " ".join(sample_sentences)
    ref_id = make_id("ref")

    sentence_units = []
    for idx, text in enumerate(sample_sentences):
        sentence_units.append(
            {
                "id": make_id("sentence"),
                "doc_id": ref_id,
                "node_id": CORE_NODE_IDS["NORM"],
                "paragraph_id": f"p-{idx // 4}",
                "index": idx,
                "raw_text": text,
                "translated_text": text,
                "start_offset": idx * 120,
                "end_offset": idx * 120 + len(text),
                "citation_span": "",
                "highlighted": idx < 6,
                "note": "",
            }
        )

    categories_by_idx = [
        "core-concept",
        "core-concept",
        "methodology",
        "methodology",
        "result",
        "limitation",
        "citable-claim",
        "citable-claim",
    ]

    sentence_artifacts = []
    for idx, unit in enumerate(sentence_units):
        sentence_artifacts.append(
            {
                "id": make_id("artifact"),
                "node_id": CORE_NODE_IDS["EXTRACT"],
                "type": "highlight",
                "source_sentence_ids": [unit["id"]],
                "abstract_text": "",
                "tag": "amber" if idx % 2 == 0 else "cyan",
                "confidence": 1.0,
            }
        )
        sentence_artifacts.append(
            {
                "id": make_id("artifact"),
                "node_id": CORE_NODE_IDS["EXTRACT"],
                "type": "category",
                "source_sentence_ids": [unit["id"]],
                "abstract_text": "",
                "tag": categories_by_idx[idx],
                "confidence": 0.92,
            }
        )

    sentence_artifacts.append(
        {
            "id": make_id("artifact"),
            "node_id": CORE_NODE_IDS["EXTRACT"],
            "type": "abstract",
            "source_sentence_ids": [sentence_units[0]["id"], sentence_units[1]["id"], sentence_units[2]["id"]],
            "abstract_text": "Trust formation and multilingual drafting friction jointly shape research progression.",
            "tag": "abstract",
            "confidence": 0.88,
        }
    )

    category_map = {}
    for artifact in sentence_artifacts:
        if artifact["type"] != "category":
            continue
        tag = artifact["tag"]
        if tag not in category_map:
            category_map[tag] = []
        category_map[tag].extend(artifact["source_sentence_ids"])

    for key, values in category_map.items():
        category_map[key] = list(dict.fromkeys(values))

    evidence_links = list(
        dict.fromkeys(
            sid
            for artifact in sentence_artifacts
            for sid in artifact.get("source_sentence_ids", [])
        )
    )

    theory_draft = [
        "Theoretical Background Draft",
        "",
        "1. core-concept: trust formation + multilingual friction",
        "2. methodology: feedback cadence and triangulation strategy",
        "3. limitation: convenience sampling and regional bias",
        "",
        "Evidence Snapshots",
    ]
    theory_draft.extend([f"- [{u['id']}] {truncate(u['translated_text'])}" for u in sentence_units[:6]])

    questions = [
        {
            "id": make_id("rq"),
            "text": "How does mentor feedback cadence moderate methodological consistency in multilingual teams?",
        },
        {
            "id": make_id("rq"),
            "text": "Which mechanisms link coding memo transparency to inter-rater agreement?",
        },
        {
            "id": make_id("rq"),
            "text": "What mixed-method design best validates trust formation dynamics across institutions?",
        },
    ]
    selected_question_ids = [questions[0]["id"], questions[2]["id"]]
    selected_rqs = [q for q in questions if q["id"] in selected_question_ids]

    methodology_draft = [
        "Methodology Draft",
        "",
        "Selected Research Questions",
    ]
    methodology_draft.extend([f"- {q['text']}" for q in selected_rqs])
    methodology_draft.extend(
        [
            "",
            "Template: mixed",
            "Required Data Sources: interview, survey, institutional archive",
            "",
            "Analytic Plan",
            "Step1 thematic coding -> Step2 quantized codebook -> Step3 triangulation regression.",
            "",
            "Validity Checks",
            "inter-rater reliability, member checking, cross-source consistency.",
            "",
            f"Evidence Links ({len(evidence_links)})",
        ]
    )
    methodology_draft.extend([f"- {sid}" for sid in evidence_links[:8]])

    extract_branch_id = f"n-extract-{make_id('branch')}"
    theory_branch_id = f"n-theory-{make_id('branch')}"
    question_branch_id = f"n-question-{make_id('branch')}"
    method_branch_id = f"n-method-{make_id('branch')}"

    branch_nodes = [
        {
            "id": extract_branch_id,
            "x": 980,
            "y": 430,
            "icon": "box",
            "label": "Sentence Extract Parallel Branch",
            "desc": "Alternative extraction channel",
            "type": "extract",
            "status": "completed",
        },
        {
            "id": theory_branch_id,
            "x": 1290,
            "y": 430,
            "icon": "brain",
            "label": "Theory Builder Branch",
            "desc": "Competing explanatory frame",
            "type": "theory",
            "status": "completed",
        },
        {
            "id": question_branch_id,
            "x": 1600,
            "y": 430,
            "icon": "search",
            "label": "RQ Generator Branch",
            "desc": "Alternative question stream",
            "type": "question",
            "status": "completed",
        },
        {
            "id": method_branch_id,
            "x": 1910,
            "y": 430,
            "icon": "branch",
            "label": "Methodology Branch",
            "desc": "Comparative method path",
            "type": "methodology",
            "status": "ready",
        },
    ]

    branch_edges = [
        {"id": make_id("edge"), "from_id": CORE_NODE_IDS["NORM"], "to_id": extract_branch_id, "label": "parallel-units", "mode": "vertical"},
        {"id": make_id("edge"), "from_id": CORE_NODE_IDS["EXTRACT"], "to_id": theory_branch_id, "label": "alt-theory", "mode": "parallel"},
        {"id": make_id("edge"), "from_id": extract_branch_id, "to_id": CORE_NODE_IDS["THEORY"], "label": "merge-up", "mode": "parallel"},
        {"id": make_id("edge"), "from_id": theory_branch_id, "to_id": CORE_NODE_IDS["QUESTION"], "label": "alt-rq-feed", "mode": "parallel"},
        {"id": make_id("edge"), "from_id": CORE_NODE_IDS["THEORY"], "to_id": question_branch_id, "label": "secondary-stream", "mode": "parallel"},
        {"id": make_id("edge"), "from_id": question_branch_id, "to_id": CORE_NODE_IDS["METHOD"], "label": "rq-merge", "mode": "parallel"},
        {"id": make_id("edge"), "from_id": CORE_NODE_IDS["QUESTION"], "to_id": method_branch_id, "label": "vertical-method", "mode": "vertical"},
        {"id": make_id("edge"), "from_id": question_branch_id, "to_id": method_branch_id, "label": "parallel-method", "mode": "parallel"},
    ]

    all_nodes = nodes + branch_nodes
    all_edges = edges + branch_edges
    node_execution_state = {}
    now = datetime.utcnow().isoformat() + "Z"
    for node in all_nodes:
        node_execution_state[node["id"]] = {
            "ok": node["id"] != method_branch_id,
            "message": "sample loaded" if node["id"] != method_branch_id else "ready",
            "at": now,
        }

    rq_draft = default_rq_draft()
    rq_draft["id"] = make_id("rqdraft")
    rq_draft["questions"] = deepcopy(questions)
    rq_draft["selected_question_ids"] = deepcopy(selected_question_ids)
    rq_draft["rationale_refs"] = evidence_links[:5]
    rq_draft["theory_support_ids"] = evidence_links[:5]

    method_context = default_methodology_context()
    method_context["id"] = make_id("method")
    method_context["selected_rqs"] = deepcopy(selected_rqs)
    method_context["method_template_type"] = "mixed"
    method_context["required_data_sources"] = "interview, survey, archive"
    method_context["analytic_plan"] = "thematic coding -> triangulation -> explanatory modeling"
    method_context["validity_checks"] = "inter-rater reliability + member checking + robustness checks"
    method_context["draft_text"] = "\n".join(methodology_draft)
    method_context["risk_log"] = [
        "Regional sampling bias remains possible.",
        "Citation translation drift must be manually audited.",
    ]

    form = default_reference_form()
    form["source_type"] = "upload"
    form["manual_text"] = raw_text
    form["title"] = "Sample Workflow: Node-based Research Assistant"
    form["authors"] = "Lee, Kim, Park"
    form["year"] = "2025"
    form["doi"] = "10.1234/sample.workflow.2025.001"
    form["journal"] = "Journal of Research Workflow Systems"

    builder = default_workflow_builder()
    builder["template_type"] = "extract"
    builder["placement"] = "parallel"
    builder["from_id"] = CORE_NODE_IDS["EXTRACT"]
    builder["to_id"] = theory_branch_id
    builder["edge_mode"] = "parallel"

    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "reference_form": form,
        "reference_upload": {"name": "", "type": "", "bytes": None},
        "reference_document": {
            "id": ref_id,
            "project_id": project_id,
            "source_type": "upload",
            "source_url": "",
            "file_hash": make_id("hash"),
            "title": form["title"],
            "authors": form["authors"],
            "year": form["year"],
            "journal": form["journal"],
            "doi": form["doi"],
            "raw_text": raw_text,
            "extracted_at": now,
            "language_detected": "en",
            "recommendation_citation": "Lee, Kim, Park (2025). Sample Workflow: Node-based Research Assistant.",
        },
        "translated_text": raw_text,
        "sentence_units": sentence_units,
        "sentence_artifacts": sentence_artifacts,
        "selected_sentence_ids": [sentence_units[0]["id"], sentence_units[1]["id"]],
        "sentence_view_mode": "highlight",
        "highlight_color": "amber",
        "category_bucket": CATEGORIES[0],
        "theory_background": {
            "id": make_id("theory"),
            "node_id": CORE_NODE_IDS["THEORY"],
            "concepts": list(category_map.keys()),
            "category_map": category_map,
            "evidence_links": evidence_links,
            "draft_text": "\n".join(theory_draft),
            "revision_history": [{"id": make_id("rev"), "at": now, "by": "sample", "note": "sample bootstrap"}],
        },
        "rq_tab": "review",
        "manual_question_input": "",
        "research_question_draft": rq_draft,
        "methodology_context": method_context,
        "node_execution_state": node_execution_state,
        "workflow_builder": builder,
        "selected_node_id": CORE_NODE_IDS["METHOD"],
    }
