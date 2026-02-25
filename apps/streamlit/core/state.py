from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from core.pipeline import CATEGORIES, CORE_NODE_IDS, METHOD_TEMPLATES, clone_initial_edges, clone_initial_nodes

NodeStatus = Literal["idle", "ready", "completed", "blocked"]
EdgeMode = Literal["horizontal", "vertical", "parallel"]


@dataclass
class Node:
    id: str
    type: str
    label: str
    desc: str
    status: NodeStatus
    x: int
    y: int


@dataclass
class Edge:
    id: str
    from_id: str
    to_id: str
    label: str
    mode: EdgeMode


@dataclass
class ReferenceDocument:
    id: str
    project_id: str
    source_type: str
    source_url: str
    file_hash: str
    title: str
    authors: str
    year: str
    journal: str
    doi: str
    raw_text: str
    extracted_at: str
    language_detected: str


@dataclass
class SentenceUnit:
    id: str
    doc_id: str
    node_id: str
    paragraph_id: str
    index: int
    raw_text: str
    translated_text: str
    start_offset: int
    end_offset: int
    citation_span: str
    highlighted: bool = False
    note: str = ""


@dataclass
class SentenceArtifact:
    id: str
    node_id: str
    type: str
    source_sentence_ids: List[str] = field(default_factory=list)
    abstract_text: str = ""
    tag: str = ""
    confidence: float = 0.0


@dataclass
class TheoryBackground:
    id: str
    node_id: str
    concepts: List[str] = field(default_factory=list)
    category_map: Dict[str, List[str]] = field(default_factory=dict)
    evidence_links: List[str] = field(default_factory=list)
    draft_text: str = ""
    revision_history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ResearchQuestionDraft:
    id: Optional[str]
    node_id: str
    questions: List[Dict[str, str]] = field(default_factory=list)
    selected_question_ids: List[str] = field(default_factory=list)
    rationale_refs: List[str] = field(default_factory=list)
    theory_support_ids: List[str] = field(default_factory=list)


@dataclass
class MethodologyContext:
    id: Optional[str]
    node_id: str
    selected_rqs: List[Dict[str, str]] = field(default_factory=list)
    method_template_type: str = METHOD_TEMPLATES[0]
    required_data_sources: str = ""
    analytic_plan: str = ""
    validity_checks: str = ""
    risk_log: List[str] = field(default_factory=list)
    draft_text: str = ""


def default_reference_form():
    return {
        "source_type": "upload",
        "source_url": "",
        "manual_text": "",
        "title": "",
        "authors": "",
        "year": "",
        "journal": "",
        "doi": "",
    }


def default_api_config():
    return {
        "project_id": "project-demo",
        "mode": "mock",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "target_language": "en",
        "api_key": "",
        "api_base_url": "",
    }


def default_rq_draft():
    return {
        "id": None,
        "node_id": CORE_NODE_IDS["QUESTION"],
        "questions": [],
        "selected_question_ids": [],
        "rationale_refs": [],
        "theory_support_ids": [],
    }


def default_methodology_context():
    return {
        "id": None,
        "node_id": CORE_NODE_IDS["METHOD"],
        "selected_rqs": [],
        "method_template_type": METHOD_TEMPLATES[0],
        "required_data_sources": "",
        "analytic_plan": "",
        "validity_checks": "",
        "risk_log": [],
        "draft_text": "",
    }


def default_workflow_builder():
    return {
        "template_type": "reference",
        "placement": "parallel",
        "from_id": CORE_NODE_IDS["REF"],
        "to_id": CORE_NODE_IDS["RAW"],
        "edge_mode": "horizontal",
        "edge_label": "",
    }


def init_session_state(session_state):
    defaults = {
        "nodes": clone_initial_nodes(),
        "edges": clone_initial_edges(),
        "selected_node_id": CORE_NODE_IDS["REF"],
        "api_config": default_api_config(),
        "api_log": [],
        "reference_form": default_reference_form(),
        "reference_upload": {"name": "", "type": "", "bytes": None},
        "reference_document": None,
        "translated_text": "",
        "sentence_units": [],
        "sentence_artifacts": [],
        "selected_sentence_ids": [],
        "sentence_view_mode": "translated",
        "highlight_color": "amber",
        "category_bucket": CATEGORIES[0],
        "theory_background": None,
        "rq_tab": "auto",
        "manual_question_input": "",
        "research_question_draft": default_rq_draft(),
        "methodology_context": default_methodology_context(),
        "node_execution_state": {},
        "workflow_builder": default_workflow_builder(),
    }

    for key, value in defaults.items():
        if key not in session_state:
            session_state[key] = deepcopy(value)

    node_ids = [row["id"] for row in session_state["nodes"]]
    builder = session_state["workflow_builder"]
    if node_ids:
        if builder.get("from_id") not in node_ids:
            builder["from_id"] = node_ids[0]
        if builder.get("to_id") not in node_ids:
            builder["to_id"] = node_ids[min(1, len(node_ids) - 1)]
    if session_state.get("selected_node_id") not in node_ids and node_ids:
        session_state["selected_node_id"] = node_ids[0]


def selected_node(state):
    sid = state.get("selected_node_id")
    for node in state.get("nodes", []):
        if node["id"] == sid:
            return node
    return None


def build_artifact_index(artifacts):
    index = {}
    for artifact in artifacts:
        for sid in artifact.get("source_sentence_ids", []):
            if sid not in index:
                index[sid] = {}
            if artifact["type"] not in index[sid]:
                index[sid][artifact["type"]] = []
            index[sid][artifact["type"]].append(artifact)
    return index


def compute_pipeline_status(state):
    reference_document = state.get("reference_document")
    translated_text = state.get("translated_text", "")
    sentence_units = state.get("sentence_units", [])
    sentence_artifacts = state.get("sentence_artifacts", [])
    theory_background = state.get("theory_background")
    rq_draft = state.get("research_question_draft", {})
    method_context = state.get("methodology_context", {})

    approved_count = len(rq_draft.get("selected_question_ids", []))
    evidence_count = len((theory_background or {}).get("evidence_links", []))
    category_count = len([a for a in sentence_artifacts if a.get("type") == "category"])

    completed = {
        CORE_NODE_IDS["REF"]: bool(reference_document and reference_document.get("raw_text")),
        CORE_NODE_IDS["RAW"]: bool(translated_text),
        CORE_NODE_IDS["NORM"]: len(sentence_units) > 0,
        CORE_NODE_IDS["EXTRACT"]: len(sentence_artifacts) > 0,
        CORE_NODE_IDS["THEORY"]: bool(theory_background and theory_background.get("draft_text")),
        CORE_NODE_IDS["QUESTION"]: len(rq_draft.get("questions", [])) > 0,
        CORE_NODE_IDS["METHOD"]: bool(method_context and method_context.get("draft_text")),
    }

    ready_method = approved_count > 0 and category_count > 0 and evidence_count >= 3
    ready = {
        CORE_NODE_IDS["REF"]: True,
        CORE_NODE_IDS["RAW"]: completed[CORE_NODE_IDS["REF"]],
        CORE_NODE_IDS["NORM"]: completed[CORE_NODE_IDS["RAW"]] or completed[CORE_NODE_IDS["REF"]],
        CORE_NODE_IDS["EXTRACT"]: completed[CORE_NODE_IDS["NORM"]],
        CORE_NODE_IDS["THEORY"]: completed[CORE_NODE_IDS["EXTRACT"]],
        CORE_NODE_IDS["QUESTION"]: completed[CORE_NODE_IDS["THEORY"]],
        CORE_NODE_IDS["METHOD"]: ready_method,
    }

    per_node = {}
    execution = state.get("node_execution_state", {})
    for node in state.get("nodes", []):
        nid = node["id"]
        if nid in completed:
            if completed[nid]:
                per_node[nid] = "completed"
            elif ready[nid]:
                per_node[nid] = "ready"
            else:
                per_node[nid] = "blocked"
        else:
            if execution.get(nid, {}).get("ok"):
                per_node[nid] = "completed"
            else:
                per_node[nid] = "ready"

    return {
        "completed": completed,
        "ready": ready,
        "ready_method": ready_method,
        "per_node": per_node,
        "counters": {
            "approved_count": approved_count,
            "evidence_count": evidence_count,
            "category_count": category_count,
        },
    }


def apply_node_status(state, status):
    for node in state.get("nodes", []):
        node["status"] = status["per_node"].get(node["id"], "ready")


def methodology_lock(state, status):
    counters = status["counters"]
    reasons = []
    if counters["approved_count"] < 1:
        reasons.append("Need at least one approved research question")
    if counters["category_count"] < 1:
        reasons.append("Need categorized sentence artifacts")
    if counters["evidence_count"] < 3:
        reasons.append("Need at least three evidence links")
    return {"locked": not status["ready_method"], "reasons": reasons}
