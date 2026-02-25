import hashlib
import random
import re
from datetime import datetime

import requests

from core.pipeline import CORE_NODE_IDS, get_template_map
from core.sample_data import build_sample_payload
from core.state import (
    default_methodology_context,
    default_reference_form,
    default_rq_draft,
    methodology_lock,
    selected_node,
)


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def make_id(prefix="id"):
    return f"{prefix}-{int(datetime.utcnow().timestamp() * 1000)}-{random.randint(1000, 999999)}"


def hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def detect_language(text):
    if re.search(r"[\uac00-\ud7a3]", text):
        return "ko"
    if re.search(r"[a-zA-Z]", text):
        return "en"
    return "und"


def strip_html(html):
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def split_sentences(text):
    normalized = text.replace("\r", " ").replace("\n", " ").strip()
    if not normalized:
        return []
    first = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
    if len(first) > 1:
        return first
    return [s.strip() for s in re.split(r"[;,]", normalized) if s.strip()]


def extract_citation(text):
    matches = re.findall(r"\([^)]+\)|\[[^\]]+\]|10\.\d{4,9}/[A-Za-z0-9._-]+", text)
    return "; ".join(matches) if matches else ""


def infer_metadata(text):
    lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    doi_match = re.search(r"10\.\d{4,9}/[A-Za-z0-9._-]+", text)
    journal = next((line for line in lines if re.search(r"journal|conference|proceedings|review", line, re.IGNORECASE)), "")
    authors = next((line for line in lines if "," in line and len(line) < 140 and "://" not in line), "")
    return {
        "title": lines[0] if lines else "Untitled",
        "authors": authors,
        "year": year_match.group(0) if year_match else "",
        "journal": journal,
        "doi": doi_match.group(0) if doi_match else "",
    }


def truncate(text, length=120):
    if len(text) <= length:
        return text
    return f"{text[: length - 3]}..."


def reset_sentence_order(units):
    units = sorted(units, key=lambda row: row["index"])
    for idx, row in enumerate(units):
        row["index"] = idx
        row["paragraph_id"] = f"p-{idx // 8}"
    return units


def _first_node_id_by_type(state, node_type, fallback):
    for node in state.get("nodes", []):
        if node.get("type") == node_type:
            return node["id"]
    return fallback


def _mark_execution(state, node_id, ok, message):
    execution = state.setdefault("node_execution_state", {})
    execution[node_id] = {"ok": ok, "message": message, "at": now_iso()}


def _remove_single_artifact(state, artifact_type, sentence_id):
    artifacts = state.get("sentence_artifacts", [])
    state["sentence_artifacts"] = [
        artifact
        for artifact in artifacts
        if not (
            artifact.get("type") == artifact_type
            and len(artifact.get("source_sentence_ids", [])) == 1
            and artifact["source_sentence_ids"][0] == sentence_id
        )
    ]


def load_sample_workflow_action(state):
    payload = build_sample_payload(state["api_config"]["project_id"])
    for key, value in payload.items():
        state[key] = value
    return True, "Sample workflow loaded: parallel/vertical/multi edges are ready."


def create_node_from_builder(state):
    builder = state.get("workflow_builder", {})
    template_type = builder.get("template_type")
    template = get_template_map().get(template_type)
    if not template:
        return False, "Select a valid node template."

    nodes = state.get("nodes", [])
    selected = selected_node(state) or (nodes[-1] if nodes else None)
    same_type_count = len([node for node in nodes if node.get("type") == template_type])
    new_id = f"n-{template_type}-{make_id('node')}"

    anchor_x = selected["x"] if selected else 360
    anchor_y = selected["y"] if selected else 200
    placement = builder.get("placement", "parallel")
    if placement == "vertical":
        x = anchor_x
        y = anchor_y + 180
    elif placement == "horizontal":
        x = anchor_x + 320
        y = anchor_y
    else:
        x = anchor_x + 320
        y = anchor_y + ((same_type_count % 4) - 1.5) * 130

    new_node = {
        "id": new_id,
        "x": int(x),
        "y": int(y),
        "icon": template["icon"],
        "label": f"{template['label']} {same_type_count + 1}",
        "desc": template["desc"],
        "type": template_type,
        "status": "ready",
    }
    state["nodes"] = nodes + [new_node]
    state["selected_node_id"] = new_id
    state["workflow_builder"]["to_id"] = new_id
    if not state["workflow_builder"].get("from_id"):
        state["workflow_builder"]["from_id"] = new_id
    return True, f"Node created: {new_node['label']}"


def connect_nodes_from_builder(state):
    builder = state.get("workflow_builder", {})
    from_id = builder.get("from_id")
    to_id = builder.get("to_id")
    nodes = state.get("nodes", [])
    if from_id == to_id:
        return False, "Source and target must be different."
    if not any(node["id"] == from_id for node in nodes):
        return False, "Select a valid source node."
    if not any(node["id"] == to_id for node in nodes):
        return False, "Select a valid target node."

    edges = state.get("edges", [])
    siblings = [edge for edge in edges if edge["from_id"] == from_id and edge["to_id"] == to_id]
    mode = builder.get("edge_mode", "horizontal")
    label = builder.get("edge_label", "").strip() or f"{mode}-{len(siblings) + 1}"
    edge = {
        "id": make_id("edge"),
        "from_id": from_id,
        "to_id": to_id,
        "label": label,
        "mode": mode,
    }
    state["edges"] = edges + [edge]
    state["workflow_builder"]["edge_label"] = ""
    return True, "Connection added."


def set_highlight_for_sentence(state, sentence_id, color_tag):
    _remove_single_artifact(state, "highlight", sentence_id)
    state["sentence_artifacts"] = state.get("sentence_artifacts", []) + [
        {
            "id": make_id("artifact"),
            "node_id": CORE_NODE_IDS["EXTRACT"],
            "type": "highlight",
            "source_sentence_ids": [sentence_id],
            "abstract_text": "",
            "tag": color_tag,
            "confidence": 1.0,
        }
    ]
    return True, "Sentence highlight updated."


def set_category_for_sentence(state, sentence_id, category):
    _remove_single_artifact(state, "category", sentence_id)
    state["sentence_artifacts"] = state.get("sentence_artifacts", []) + [
        {
            "id": make_id("artifact"),
            "node_id": CORE_NODE_IDS["EXTRACT"],
            "type": "category",
            "source_sentence_ids": [sentence_id],
            "abstract_text": "",
            "tag": category,
            "confidence": 0.9,
        }
    ]
    return True, "Sentence category updated."


def highlight_selected_sentences(state):
    selected_ids = state.get("selected_sentence_ids", [])
    if not selected_ids:
        return False, "Select sentence blocks first."
    for sentence_id in selected_ids:
        set_highlight_for_sentence(state, sentence_id, state.get("highlight_color", "amber"))
    return True, f"Box highlight applied: {len(selected_ids)} sentence(s)."


def move_selected_to_category(state):
    selected_ids = state.get("selected_sentence_ids", [])
    if not selected_ids:
        return False, "Select sentence blocks first."
    category = state.get("category_bucket", "core-concept")
    for sentence_id in selected_ids:
        set_category_for_sentence(state, sentence_id, category)
    return True, f"Category moved: {category}"


def split_selected_sentence(state):
    selected_ids = state.get("selected_sentence_ids", [])
    if not selected_ids:
        return False, "Select at least one sentence."
    sentence_id = selected_ids[0]
    units = state.get("sentence_units", [])
    target = next((row for row in units if row["id"] == sentence_id), None)
    if not target:
        return False, "Selected sentence was not found."

    parts = [p.strip() for p in re.split(r"[,;]\s*", target["translated_text"]) if len(p.strip()) > 1]
    if len(parts) < 2:
        return False, "Split requires at least two parts."

    index = next((i for i, row in enumerate(units) if row["id"] == sentence_id), -1)
    if index < 0:
        return False, "Sentence index not found."

    replacements = []
    for offset, part in enumerate(parts):
        replacements.append(
            {
                "id": make_id("sentence"),
                "doc_id": target["doc_id"],
                "node_id": target["node_id"],
                "paragraph_id": target["paragraph_id"],
                "index": target["index"] + offset / 10,
                "raw_text": part,
                "translated_text": part,
                "start_offset": target["start_offset"],
                "end_offset": target["start_offset"] + len(part),
                "citation_span": extract_citation(part),
                "highlighted": False,
                "note": "",
            }
        )

    next_units = list(units)
    next_units[index:index + 1] = replacements
    state["sentence_units"] = reset_sentence_order(next_units)
    state["sentence_artifacts"] = [
        artifact
        for artifact in state.get("sentence_artifacts", [])
        if sentence_id not in artifact.get("source_sentence_ids", [])
    ]
    state["selected_sentence_ids"] = [sid for sid in selected_ids if sid != sentence_id]
    return True, "Sentence split applied."


def merge_selected_sentences(state):
    selected_ids = state.get("selected_sentence_ids", [])
    if len(selected_ids) < 2:
        return False, "Merge requires at least two selected sentences."

    units = state.get("sentence_units", [])
    selected_rows = sorted(
        [row for row in units if row["id"] in selected_ids],
        key=lambda row: row["index"],
    )
    if len(selected_rows) < 2:
        return False, "Selected sentence rows were not found."

    anchor = selected_rows[0]
    first_index = next((i for i, row in enumerate(units) if row["id"] == anchor["id"]), -1)
    if first_index < 0:
        return False, "Anchor sentence index not found."

    merged_row = {
        "id": make_id("sentence"),
        "doc_id": anchor["doc_id"],
        "node_id": anchor["node_id"],
        "paragraph_id": anchor["paragraph_id"],
        "index": anchor["index"],
        "raw_text": " ".join(row["raw_text"] for row in selected_rows),
        "translated_text": " ".join(row["translated_text"] for row in selected_rows),
        "start_offset": min(row["start_offset"] for row in selected_rows),
        "end_offset": max(row["end_offset"] for row in selected_rows),
        "citation_span": "; ".join([row["citation_span"] for row in selected_rows if row.get("citation_span")]),
        "highlighted": False,
        "note": f"merged:{','.join(str(row['index'] + 1) for row in selected_rows)}",
    }

    remaining = [row for row in units if row["id"] not in selected_ids]
    remaining.insert(first_index, merged_row)
    state["sentence_units"] = reset_sentence_order(remaining)
    state["sentence_artifacts"] = state.get("sentence_artifacts", []) + [
        {
            "id": make_id("artifact"),
            "node_id": CORE_NODE_IDS["EXTRACT"],
            "type": "merged",
            "source_sentence_ids": list(selected_ids),
            "abstract_text": merged_row["translated_text"],
            "tag": "merged",
            "confidence": 0.88,
        }
    ]
    state["selected_sentence_ids"] = []
    return True, "Sentence merge applied."


def abstract_selected_sentences(state):
    selected_ids = state.get("selected_sentence_ids", [])
    if not selected_ids:
        return False, "Select sentence blocks first."
    units = state.get("sentence_units", [])
    text = " ".join(
        row["translated_text"] for row in units if row["id"] in selected_ids
    )
    summary = " ".join(text.split()[:40])
    state["sentence_artifacts"] = state.get("sentence_artifacts", []) + [
        {
            "id": make_id("artifact"),
            "node_id": CORE_NODE_IDS["EXTRACT"],
            "type": "abstract",
            "source_sentence_ids": list(selected_ids),
            "abstract_text": summary,
            "tag": "abstract",
            "confidence": 0.86,
        }
    ]
    return True, "Abstract artifact created."


def add_snippet_from_selected(state):
    selected_ids = state.get("selected_sentence_ids", [])
    if not selected_ids:
        return False, "Select sentence blocks first."
    units = state.get("sentence_units", [])
    text = " ".join(
        row["translated_text"] for row in units if row["id"] in selected_ids
    )
    state["sentence_artifacts"] = state.get("sentence_artifacts", []) + [
        {
            "id": make_id("artifact"),
            "node_id": CORE_NODE_IDS["EXTRACT"],
            "type": "snippet",
            "source_sentence_ids": list(selected_ids),
            "abstract_text": truncate(text, 180),
            "tag": "snippet",
            "confidence": 0.9,
        }
    ]
    return True, "Snippet artifact created."


def run_reference_input(state, api_client):
    form = state.get("reference_form", default_reference_form())
    upload = state.get("reference_upload", {})
    has_upload = form.get("source_type") == "upload" and bool(upload.get("bytes"))
    has_url = form.get("source_type") == "url" and bool(form.get("source_url", "").strip())
    has_manual = bool(form.get("manual_text", "").strip())
    current = selected_node(state)
    execution_id = current["id"] if current else CORE_NODE_IDS["REF"]

    if not has_upload and not has_url and not has_manual:
        message = "Upload file, provide URL, or paste manual text first."
        _mark_execution(state, execution_id, False, message)
        return False, message

    if not api_client.call(
        "POST /api/projects/{projectId}/references",
        {
            "projectId": state["api_config"]["project_id"],
            "provider": state["api_config"]["provider"],
            "runtime_token": api_client.create_runtime_token(),
        },
    ).get("ok"):
        message = "Reference source initialization API failed."
        _mark_execution(state, execution_id, False, message)
        return False, message

    raw_text = ""
    notices = []
    if has_upload:
        name = upload.get("name", "")
        upload_type = upload.get("type", "")
        file_bytes = upload.get("bytes") or b""
        is_text = name.lower().endswith((".txt", ".md", ".csv", ".json")) or upload_type.startswith("text/")
        if is_text:
            raw_text = file_bytes.decode("utf-8", errors="ignore")
        else:
            raw_text = f"[Binary upload placeholder] {name}"
            notices.append("Binary upload fallback used.")
        api_client.call(
            "POST /api/projects/{projectId}/references/{refId}/upload",
            {"filename": name, "runtime_token": api_client.create_runtime_token()},
        )

    if not raw_text and has_url:
        try:
            response = requests.get(form["source_url"], timeout=15)
            response.raise_for_status()
            body = response.text
            if re.search(r"login|sign in|forbidden|captcha|access denied", body, re.IGNORECASE):
                raise ValueError("blocked page")
            content_type = response.headers.get("content-type", "")
            raw_text = strip_html(body) if "text/html" in content_type else body
            api_client.call(
                "POST /api/projects/{projectId}/references/{refId}/fetch-url",
                {
                    "sourceUrl": form["source_url"],
                    "runtime_token": api_client.create_runtime_token(),
                },
            )
        except Exception:
            notices.append("URL fetch failed. Use upload/manual fallback.")

    if has_manual:
        raw_text = f"{raw_text}\n\n{form['manual_text']}".strip()

    if not raw_text.strip():
        message = "No readable text extracted."
        _mark_execution(state, execution_id, False, message)
        return False, message

    meta = infer_metadata(raw_text)
    doc = {
        "id": make_id("ref"),
        "project_id": state["api_config"]["project_id"],
        "source_type": form.get("source_type", "upload"),
        "source_url": form.get("source_url", ""),
        "file_hash": hash_text(raw_text),
        "title": form.get("title") or meta["title"],
        "authors": form.get("authors") or meta["authors"],
        "year": form.get("year") or meta["year"],
        "journal": form.get("journal") or meta["journal"],
        "doi": form.get("doi") or meta["doi"],
        "raw_text": raw_text,
        "extracted_at": now_iso(),
        "language_detected": detect_language(raw_text),
        "recommendation_citation": f"{(form.get('authors') or meta['authors'] or 'Unknown').strip()} ({form.get('year') or meta['year'] or 'n.d.'}). {form.get('title') or meta['title']}",
    }

    state["reference_document"] = doc
    state["translated_text"] = ""
    state["sentence_units"] = []
    state["sentence_artifacts"] = []
    state["selected_sentence_ids"] = []
    state["theory_background"] = None
    state["rq_tab"] = "auto"
    state["manual_question_input"] = ""
    state["research_question_draft"] = default_rq_draft()
    method_context = default_methodology_context()
    method_context["method_template_type"] = state["methodology_context"].get("method_template_type", method_context["method_template_type"])
    state["methodology_context"] = method_context
    state["selected_node_id"] = _first_node_id_by_type(state, "translate", CORE_NODE_IDS["RAW"])

    message = "Reference Input Node completed."
    if notices:
        message = f"{message} {' '.join(notices)}"
    _mark_execution(state, execution_id, True, message)
    return True, message


def run_raw_translate(state, api_client):
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["RAW"]
    document = state.get("reference_document")
    if not document:
        message = "Reference document is required first."
        _mark_execution(state, execution_id, False, message)
        return False, message

    result = api_client.call(
        "POST /api/references/{refId}/translate",
        {
            "refId": document["id"],
            "targetLanguage": state["api_config"].get("target_language", "en"),
            "provider": state["api_config"].get("provider", "openai"),
            "runtime_token": api_client.create_runtime_token(),
        },
    )
    if not result.get("ok"):
        message = "Raw translation API failed."
        _mark_execution(state, execution_id, False, message)
        return False, message

    state["translated_text"] = document["raw_text"]
    state["selected_node_id"] = _first_node_id_by_type(state, "normalize", CORE_NODE_IDS["NORM"])
    message = "Raw Translate Node completed."
    _mark_execution(state, execution_id, True, message)
    return True, message


def run_sentence_normalization(state, api_client):
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["NORM"]
    source = state.get("translated_text") or (state.get("reference_document") or {}).get("raw_text", "")
    if not source.strip():
        message = "No source text to normalize."
        _mark_execution(state, execution_id, False, message)
        return False, message

    result = api_client.call(
        "POST /api/references/{refId}/sentences/extract",
        {
            "refId": (state.get("reference_document") or {}).get("id"),
            "runtime_token": api_client.create_runtime_token(),
        },
    )
    if not result.get("ok"):
        message = "Sentence extraction API failed."
        _mark_execution(state, execution_id, False, message)
        return False, message

    cursor = 0
    units = []
    for idx, sentence in enumerate(split_sentences(source)):
        start = source.find(sentence, cursor)
        safe_start = start if start >= 0 else cursor
        safe_end = safe_start + len(sentence)
        cursor = safe_end
        units.append(
            {
                "id": make_id("sentence"),
                "doc_id": (state.get("reference_document") or {}).get("id", "n/a"),
                "node_id": CORE_NODE_IDS["NORM"],
                "paragraph_id": f"p-{idx // 8}",
                "index": idx,
                "raw_text": sentence,
                "translated_text": sentence,
                "start_offset": safe_start,
                "end_offset": safe_end,
                "citation_span": extract_citation(sentence),
                "highlighted": False,
                "note": "",
            }
        )

    if not units:
        message = "No sentence units extracted."
        _mark_execution(state, execution_id, False, message)
        return False, message

    state["sentence_units"] = units
    state["sentence_artifacts"] = []
    state["selected_sentence_ids"] = []
    state["selected_node_id"] = _first_node_id_by_type(state, "extract", CORE_NODE_IDS["EXTRACT"])
    message = f"Sentence Normalization Node completed ({len(units)} units)."
    _mark_execution(state, execution_id, True, message)
    return True, message


def run_extract_node(state, api_client):
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["EXTRACT"]
    units = state.get("sentence_units", [])
    if not units:
        message = "Run Sentence Normalization first."
        _mark_execution(state, execution_id, False, message)
        return False, message

    result = api_client.call(
        "POST /api/projects/{projectId}/nodes/{nodeId}/sentences/highlight",
        {
            "nodeId": execution_id,
            "runtime_token": api_client.create_runtime_token(),
        },
    )
    if not result.get("ok"):
        message = "Extract/highlight sync API failed."
        _mark_execution(state, execution_id, False, message)
        return False, message

    if not state.get("sentence_artifacts"):
        bucket = state.get("category_bucket", "core-concept")
        for unit in units[: min(3, len(units))]:
            set_highlight_for_sentence(state, unit["id"], "amber")
            set_category_for_sentence(state, unit["id"], bucket)
        message = "Extract artifacts bootstrapped from first sentence blocks."
    else:
        message = "Extract node synced with current artifact edits."
    _mark_execution(state, execution_id, True, message)
    return True, message


def build_theory_background(state, api_client):
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["THEORY"]
    artifacts = state.get("sentence_artifacts", [])
    if not artifacts:
        message = "Need extract artifacts before theory build."
        _mark_execution(state, execution_id, False, message)
        return False, message

    result = api_client.call(
        "POST /api/projects/{projectId}/nodes/{nodeId}/theory/build",
        {
            "nodeId": execution_id,
            "runtime_token": api_client.create_runtime_token(),
        },
    )
    if not result.get("ok"):
        message = "Theory builder API failed."
        _mark_execution(state, execution_id, False, message)
        return False, message

    category_map = {}
    for artifact in artifacts:
        if artifact.get("type") != "category":
            continue
        tag = artifact.get("tag") or "uncategorized"
        category_map.setdefault(tag, [])
        category_map[tag].extend(artifact.get("source_sentence_ids", []))
    for key, values in category_map.items():
        category_map[key] = list(dict.fromkeys(values))

    evidence_links = list(
        dict.fromkeys(
            sid
            for artifact in artifacts
            if artifact.get("type") in {"highlight", "snippet", "abstract", "category", "merged"}
            for sid in artifact.get("source_sentence_ids", [])
        )
    )

    units = state.get("sentence_units", [])
    unit_map = {row["id"]: row for row in units}
    snapshots = []
    for sid in evidence_links[:8]:
        row = unit_map.get(sid)
        snapshots.append(f"- [{sid}] {truncate(row['translated_text'], 90) if row else sid}")

    concepts = list(category_map.keys())
    draft_lines = ["Theoretical Background Draft", ""]
    draft_lines.extend(
        [
            f"{idx + 1}. {concept} ({len(category_map.get(concept, []))} evidence sentence(s))"
            for idx, concept in enumerate(concepts)
        ]
    )
    draft_lines.extend(["", "Evidence Snapshots"])
    draft_lines.extend(snapshots)

    state["theory_background"] = {
        "id": make_id("theory"),
        "node_id": execution_id,
        "concepts": concepts,
        "category_map": category_map,
        "evidence_links": evidence_links,
        "draft_text": "\n".join(draft_lines),
        "revision_history": [{"id": make_id("rev"), "at": now_iso(), "by": "system", "note": "auto build"}],
    }
    state["selected_node_id"] = _first_node_id_by_type(state, "question", CORE_NODE_IDS["QUESTION"])
    message = "Theoretical Background Builder Node completed."
    _mark_execution(state, execution_id, True, message)
    return True, message


def build_auto_questions(state, api_client):
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["QUESTION"]
    theory = state.get("theory_background")
    if not theory:
        message = "Need theory background first."
        _mark_execution(state, execution_id, False, message)
        return False, message

    result = api_client.call(
        "POST /api/projects/{projectId}/nodes/{nodeId}/research-questions",
        {
            "nodeId": execution_id,
            "runtime_token": api_client.create_runtime_token(),
        },
    )
    if not result.get("ok"):
        message = "Research-question generation API failed."
        _mark_execution(state, execution_id, False, message)
        return False, message

    concepts = theory.get("concepts", [])[:4]
    if concepts:
        generated = [
            {
                "id": make_id("rq"),
                "text": f"{idx + 1}. How does {concept} explain the core research phenomenon?",
            }
            for idx, concept in enumerate(concepts)
        ]
    else:
        generated = [
            {
                "id": make_id("rq"),
                "text": "1. What conceptual mechanism best explains the target phenomenon?",
            }
        ]
    while len(generated) < 3:
        generated.append(
            {
                "id": make_id("rq"),
                "text": "Which contextual factors moderate the observed relationships?",
            }
        )
    generated.append(
        {
            "id": make_id("rq"),
            "text": "Which methodology is most defensible for testing the above assumptions?",
        }
    )
    final_list = generated[:5]
    state["research_question_draft"] = {
        "id": make_id("rqdraft"),
        "node_id": execution_id,
        "questions": final_list,
        "selected_question_ids": [],
        "rationale_refs": theory.get("evidence_links", [])[:5],
        "theory_support_ids": theory.get("evidence_links", [])[:5],
    }
    state["rq_tab"] = "review"
    message = "Research Question Generator Node created 3-5 candidates."
    _mark_execution(state, execution_id, True, message)
    return True, message


def add_manual_questions(state):
    text = state.get("manual_question_input", "")
    rows = [line.strip() for line in text.splitlines() if line.strip()]
    if not rows:
        return False, "Enter manual questions first."
    additions = [{"id": make_id("rq"), "text": row} for row in rows]
    draft = state.get("research_question_draft", default_rq_draft())
    draft.setdefault("questions", [])
    draft["id"] = draft.get("id") or make_id("rqdraft")
    draft["questions"].extend(additions)
    state["research_question_draft"] = draft
    state["manual_question_input"] = ""
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["QUESTION"]
    _mark_execution(state, execution_id, True, f"Added {len(additions)} manual question(s).")
    return True, f"Added {len(additions)} manual question(s)."


def approve_selected_questions(state, selected_ids):
    if not selected_ids:
        return False, "Select at least one research question."
    draft = state.get("research_question_draft", default_rq_draft())
    questions = draft.get("questions", [])
    selected_rqs = [row for row in questions if row["id"] in selected_ids]
    draft["selected_question_ids"] = list(selected_ids)
    state["research_question_draft"] = draft

    context = state.get("methodology_context", default_methodology_context())
    context["selected_rqs"] = selected_rqs
    state["methodology_context"] = context
    state["selected_node_id"] = _first_node_id_by_type(state, "methodology", CORE_NODE_IDS["METHOD"])
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["QUESTION"]
    _mark_execution(state, execution_id, True, "Research question fixed. Methodology node entered.")
    return True, "Research question fixed. Methodology node entered."


def build_methodology(state, api_client):
    node = selected_node(state)
    execution_id = node["id"] if node else CORE_NODE_IDS["METHOD"]
    from core.state import compute_pipeline_status

    status = compute_pipeline_status(state)
    lock = methodology_lock(state, status)
    if lock["locked"]:
        message = "Methodology node locked. Need approved RQ + category artifacts + evidence links >= 3."
        _mark_execution(state, execution_id, False, message)
        return False, message

    result = api_client.call(
        "POST /api/projects/{projectId}/nodes/{nodeId}/methodology/seed",
        {
            "nodeId": execution_id,
            "runtime_token": api_client.create_runtime_token(),
        },
    )
    if not result.get("ok"):
        message = "Methodology seed API failed."
        _mark_execution(state, execution_id, False, message)
        return False, message

    draft = state.get("research_question_draft", {})
    selected_ids = draft.get("selected_question_ids", [])
    selected_questions = [row for row in draft.get("questions", []) if row["id"] in selected_ids]
    theory = state.get("theory_background") or {}
    method = state.get("methodology_context", default_methodology_context())
    evidence_count = len(theory.get("evidence_links", []))

    lines = ["Methodology Draft", "", "Selected Research Questions"]
    lines.extend([f"- {row['text']}" for row in selected_questions])
    lines.extend(
        [
            "",
            f"Template: {method.get('method_template_type', '')}",
            f"Required Data Sources: {method.get('required_data_sources') or '(pending)'}",
            "",
            "Analytic Plan",
            method.get("analytic_plan") or "(pending)",
            "",
            "Validity Checks",
            method.get("validity_checks") or "(pending)",
            "",
            f"Evidence Links ({evidence_count})",
        ]
    )
    lines.extend([f"- {sid}" for sid in theory.get("evidence_links", [])[:10]])

    method["id"] = make_id("method")
    method["selected_rqs"] = selected_questions
    method["draft_text"] = "\n".join(lines)
    method["risk_log"] = [
        "Verify traceability from evidence to selected method.",
        "Check data access constraints and sample bias risks.",
        "Validate internal/external validity checks before final writeup.",
    ]
    state["methodology_context"] = method
    message = "Methodology Node completed."
    _mark_execution(state, execution_id, True, message)
    return True, message


def run_selected_node(state, api_client):
    node = selected_node(state)
    if not node:
        return False, "Select a node first."
    node_type = node.get("type")
    if node_type == "reference":
        return run_reference_input(state, api_client)
    if node_type == "translate":
        return run_raw_translate(state, api_client)
    if node_type == "normalize":
        return run_sentence_normalization(state, api_client)
    if node_type == "extract":
        return run_extract_node(state, api_client)
    if node_type == "theory":
        return build_theory_background(state, api_client)
    if node_type == "question":
        if not state.get("research_question_draft", {}).get("questions"):
            return build_auto_questions(state, api_client)
        return True, "Question list exists. Use review tab to approve."
    if node_type == "methodology":
        return build_methodology(state, api_client)
    return False, "Unsupported node type."
