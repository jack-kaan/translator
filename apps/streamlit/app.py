import streamlit as st

from components.canvas import render_canvas
from components.panels import render_api_log, render_builder_panel, render_pipeline_status
from core.actions import (
    abstract_selected_sentences,
    add_manual_questions,
    add_snippet_from_selected,
    approve_selected_questions,
    build_methodology,
    build_theory_background,
    connect_nodes_from_builder,
    create_node_from_builder,
    highlight_selected_sentences,
    load_sample_workflow_action,
    merge_selected_sentences,
    move_selected_to_category,
    run_extract_node,
    run_raw_translate,
    run_reference_input,
    run_selected_node,
    run_sentence_normalization,
    set_category_for_sentence,
    set_highlight_for_sentence,
    split_selected_sentence,
)
from core.pipeline import API_PROVIDERS, CATEGORIES, CORE_NODE_IDS, METHOD_TEMPLATES, NODE_TEMPLATES
from core.state import (
    apply_node_status,
    build_artifact_index,
    compute_pipeline_status,
    init_session_state,
    methodology_lock,
    selected_node,
)
from services.api_client import APIClient


def notify(_ok: bool, message: str):
    st.toast(message)


def apply_and_refresh(ok: bool, message: str):
    notify(ok, message)
    if ok:
        st.rerun()


def render_reference_workspace(state, api_client):
    form = state["reference_form"]
    api = state["api_config"]

    col1, col2 = st.columns(2)
    with col1:
        form["source_type"] = st.selectbox(
            "Source Type",
            ["upload", "url"],
            index=["upload", "url"].index(form.get("source_type", "upload")),
            key="ref_source_type",
        )
        api["target_language"] = st.selectbox(
            "Work Language",
            ["en", "ko"],
            index=["en", "ko"].index(api.get("target_language", "en")),
            key="ref_target_language",
        )
        api["provider"] = st.selectbox(
            "Provider",
            API_PROVIDERS,
            index=API_PROVIDERS.index(api.get("provider", "openai"))
            if api.get("provider", "openai") in API_PROVIDERS
            else 0,
            key="ref_provider",
        )
    with col2:
        api["mode"] = st.selectbox(
            "API Mode",
            ["mock", "real"],
            index=["mock", "real"].index(api.get("mode", "mock")),
            key="ref_api_mode",
        )
        api["model"] = st.text_input(
            "Model",
            value=api.get("model", "gpt-4o-mini"),
            key="ref_model",
        )
        api["api_base_url"] = st.text_input(
            "API Base URL (real mode)",
            value=api.get("api_base_url", ""),
            key="ref_api_base_url",
            placeholder="https://your-backend.example.com",
        )

    api["api_key"] = st.text_input(
        "Personal API Key (runtime only)",
        value=api.get("api_key", ""),
        type="password",
        key="ref_api_key",
        placeholder="sk-...",
    )

    if form["source_type"] == "upload":
        uploaded = st.file_uploader(
            "Upload (PDF/DOCX/TXT)",
            type=["txt", "pdf", "docx", "doc", "md", "csv", "json"],
            key="ref_upload_file",
        )
        if uploaded is not None:
            state["reference_upload"] = {
                "name": uploaded.name,
                "type": uploaded.type,
                "bytes": uploaded.getvalue(),
            }
        upload_name = state["reference_upload"].get("name", "")
        if upload_name:
            st.caption(f"Current upload buffer: {upload_name}")
    else:
        form["source_url"] = st.text_input(
            "Source URL",
            value=form.get("source_url", ""),
            key="ref_source_url",
            placeholder="https://...",
        )

    form["manual_text"] = st.text_area(
        "Manual Text (fallback)",
        value=form.get("manual_text", ""),
        height=120,
        key="ref_manual_text",
    )

    m1, m2 = st.columns(2)
    with m1:
        form["title"] = st.text_input("Title", value=form.get("title", ""), key="ref_title")
        form["year"] = st.text_input("Year", value=form.get("year", ""), key="ref_year")
        form["journal"] = st.text_input("Journal", value=form.get("journal", ""), key="ref_journal")
    with m2:
        form["authors"] = st.text_input("Authors", value=form.get("authors", ""), key="ref_authors")
        form["doi"] = st.text_input("DOI", value=form.get("doi", ""), key="ref_doi")

    if st.button("Run Reference Input Node", use_container_width=True, key="run_ref_node"):
        ok, msg = run_reference_input(state, api_client)
        apply_and_refresh(ok, msg)

    if state.get("reference_document"):
        doc = state["reference_document"]
        st.info(
            f"{doc.get('title', 'Untitled')} | {doc.get('authors', 'Unknown')} ({doc.get('year', 'n.d.')})"
        )
        st.caption(
            f"DOI: {doc.get('doi', '-')} | Detected language: {doc.get('language_detected', 'und')}"
        )


def render_translate_workspace(state, api_client):
    if st.button("Run Raw Translate Node", use_container_width=True, key="run_raw_node"):
        ok, msg = run_raw_translate(state, api_client)
        apply_and_refresh(ok, msg)

    source = state.get("translated_text") or (state.get("reference_document") or {}).get("raw_text", "")
    st.text_area("Translated / Source Text", value=source, height=220, key="raw_preview_text")
    st.caption("Preservation rule: citations/equations/author tokens are kept unchanged in this branch.")


def render_normalize_workspace(state, api_client):
    if st.button("Run Sentence Normalization Node", use_container_width=True, key="run_norm_node"):
        ok, msg = run_sentence_normalization(state, api_client)
        apply_and_refresh(ok, msg)

    units = state.get("sentence_units", [])
    st.caption(f"Sentence units: {len(units)}")
    preview = [{"index": row["index"] + 1, "text": row["translated_text"][:140]} for row in units[:40]]
    st.dataframe(preview, use_container_width=True, height=240)


def render_extract_workspace(state, api_client):
    units = state.get("sentence_units", [])
    artifacts = state.get("sentence_artifacts", [])
    artifact_map = build_artifact_index(artifacts)

    state["sentence_view_mode"] = st.selectbox(
        "Sentence View",
        ["raw", "translated", "highlight"],
        index=["raw", "translated", "highlight"].index(state.get("sentence_view_mode", "translated")),
        key="extract_view_mode",
    )
    state["highlight_color"] = st.selectbox(
        "Highlight Color",
        ["amber", "cyan", "emerald", "violet"],
        index=["amber", "cyan", "emerald", "violet"].index(state.get("highlight_color", "amber")),
        key="extract_highlight_color",
    )
    state["category_bucket"] = st.selectbox(
        "Category Bucket",
        CATEGORIES,
        index=CATEGORIES.index(state.get("category_bucket", CATEGORIES[0]))
        if state.get("category_bucket", CATEGORIES[0]) in CATEGORIES
        else 0,
        key="extract_category_bucket",
    )

    visible_units = (
        [unit for unit in units if artifact_map.get(unit["id"], {}).get("highlight")]
        if state["sentence_view_mode"] == "highlight"
        else units
    )

    options = [row["id"] for row in visible_units]
    default_selected = [sid for sid in state.get("selected_sentence_ids", []) if sid in options]
    selected_ids = st.multiselect(
        "Selected Sentence Blocks",
        options,
        default=default_selected,
        format_func=lambda sid: _format_sentence_label(sid, units),
        key="extract_selected_sentence_ids",
    )
    state["selected_sentence_ids"] = selected_ids

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Box Highlight", use_container_width=True, key="extract_highlight"):
            ok, msg = highlight_selected_sentences(state)
            apply_and_refresh(ok, msg)
    with c2:
        if st.button("Move Category", use_container_width=True, key="extract_category"):
            ok, msg = move_selected_to_category(state)
            apply_and_refresh(ok, msg)
    with c3:
        if st.button("Split First", use_container_width=True, key="extract_split"):
            ok, msg = split_selected_sentence(state)
            apply_and_refresh(ok, msg)

    c4, c5, c6 = st.columns(3)
    with c4:
        if st.button("Merge Selected", use_container_width=True, key="extract_merge"):
            ok, msg = merge_selected_sentences(state)
            apply_and_refresh(ok, msg)
    with c5:
        if st.button("Abstract", use_container_width=True, key="extract_abstract"):
            ok, msg = abstract_selected_sentences(state)
            apply_and_refresh(ok, msg)
    with c6:
        if st.button("Snippet", use_container_width=True, key="extract_snippet"):
            ok, msg = add_snippet_from_selected(state)
            apply_and_refresh(ok, msg)

    c7, c8, c9 = st.columns(3)
    with c7:
        if st.button("Line Highlight 1st", use_container_width=True, key="extract_line_highlight"):
            if selected_ids:
                ok, msg = set_highlight_for_sentence(state, selected_ids[0], state["highlight_color"])
            else:
                ok, msg = False, "Select a sentence first."
            apply_and_refresh(ok, msg)
    with c8:
        if st.button("Set Category 1st", use_container_width=True, key="extract_line_category"):
            if selected_ids:
                ok, msg = set_category_for_sentence(state, selected_ids[0], state["category_bucket"])
            else:
                ok, msg = False, "Select a sentence first."
            apply_and_refresh(ok, msg)
    with c9:
        if st.button("Sync Extract Node", use_container_width=True, key="extract_sync"):
            ok, msg = run_extract_node(state, api_client)
            apply_and_refresh(ok, msg)

    if st.button("Build Theory", use_container_width=True, key="extract_build_theory"):
        ok, msg = build_theory_background(state, api_client)
        apply_and_refresh(ok, msg)

    st.caption(f"Sentence blocks: {len(visible_units)} | Selected: {len(selected_ids)} | Artifacts: {len(artifacts)}")
    preview_rows = []
    for unit in visible_units[:80]:
        unit_artifacts = artifact_map.get(unit["id"], {})
        category = (unit_artifacts.get("category") or [{}])[-1].get("tag", "uncategorized")
        color = (unit_artifacts.get("highlight") or [{}])[-1].get("tag", "")
        text = unit["raw_text"] if state["sentence_view_mode"] == "raw" else unit["translated_text"]
        preview_rows.append({"index": unit["index"] + 1, "category": category, "highlight": color, "text": text[:180]})
    st.dataframe(preview_rows, use_container_width=True, height=280)


def render_theory_workspace(state, api_client):
    if st.button("Run Theory Builder Node", use_container_width=True, key="run_theory_node"):
        ok, msg = build_theory_background(state, api_client)
        apply_and_refresh(ok, msg)

    theory = state.get("theory_background")
    if not theory:
        st.warning("Run Extract node and create artifacts first.")
        return

    st.caption("Category tree + evidence snapshot output")
    st.json(theory.get("category_map", {}))
    theory["draft_text"] = st.text_area(
        "Theory Draft",
        value=theory.get("draft_text", ""),
        height=260,
        key="theory_draft_text",
    )


def render_question_workspace(state, api_client):
    draft = state["research_question_draft"]
    state["rq_tab"] = st.radio(
        "Question Mode",
        ["auto", "manual", "review"],
        index=["auto", "manual", "review"].index(state.get("rq_tab", "auto")),
        horizontal=True,
        key="rq_tab_mode",
    )

    if state["rq_tab"] == "auto":
        if st.button("Auto Generate 3-5 Questions", use_container_width=True, key="run_rq_auto"):
            from core.actions import build_auto_questions

            ok, msg = build_auto_questions(state, api_client)
            apply_and_refresh(ok, msg)
        evidence = len((state.get("theory_background") or {}).get("evidence_links", []))
        st.caption(f"Evidence links: {evidence}")
        return

    if state["rq_tab"] == "manual":
        state["manual_question_input"] = st.text_area(
            "Manual Questions (one per line)",
            value=state.get("manual_question_input", ""),
            height=140,
            key="rq_manual_text",
        )
        if st.button("Add Manual Questions", use_container_width=True, key="add_manual_questions"):
            ok, msg = add_manual_questions(state)
            apply_and_refresh(ok, msg)
        return

    questions = draft.get("questions", [])
    options = [q["id"] for q in questions]
    selected = st.multiselect(
        "Approve Questions",
        options,
        default=draft.get("selected_question_ids", []),
        format_func=lambda qid: _format_question_label(qid, questions),
        key="rq_selected_ids",
    )
    if st.button("Approve Selected", use_container_width=True, key="approve_questions"):
        ok, msg = approve_selected_questions(state, selected)
        apply_and_refresh(ok, msg)
    st.caption(f"Candidates: {len(questions)}")


def render_methodology_workspace(state, api_client, lock_info):
    method = state["methodology_context"]
    st.warning("Lock condition: approved question + category artifacts + evidence links >= 3")
    if lock_info["locked"]:
        for reason in lock_info["reasons"]:
            st.caption(f"- {reason}")
    else:
        st.success("Methodology node unlocked.")

    c1, c2 = st.columns(2)
    with c1:
        method["method_template_type"] = st.selectbox(
            "Method Template",
            METHOD_TEMPLATES,
            index=METHOD_TEMPLATES.index(method.get("method_template_type", METHOD_TEMPLATES[0]))
            if method.get("method_template_type", METHOD_TEMPLATES[0]) in METHOD_TEMPLATES
            else 0,
            key="method_template_type",
        )
    with c2:
        method["required_data_sources"] = st.text_input(
            "Required Data Sources",
            value=method.get("required_data_sources", ""),
            key="method_required_data_sources",
            placeholder="interview/survey/archive...",
        )

    method["analytic_plan"] = st.text_area(
        "Analytic Plan",
        value=method.get("analytic_plan", ""),
        height=120,
        key="method_analytic_plan",
    )
    method["validity_checks"] = st.text_area(
        "Validity Checks",
        value=method.get("validity_checks", ""),
        height=120,
        key="method_validity_checks",
    )

    if st.button("Run Methodology Node", use_container_width=True, key="run_method_node", disabled=lock_info["locked"]):
        ok, msg = build_methodology(state, api_client)
        apply_and_refresh(ok, msg)

    method["draft_text"] = st.text_area(
        "Methodology Draft",
        value=method.get("draft_text", ""),
        height=260,
        key="method_draft_text",
    )


def _format_sentence_label(sentence_id, units):
    row = next((item for item in units if item["id"] == sentence_id), None)
    if not row:
        return sentence_id
    return f"#{row['index'] + 1} {row['translated_text'][:72]}"


def _format_question_label(question_id, questions):
    row = next((item for item in questions if item["id"] == question_id), None)
    if not row:
        return question_id
    return row["text"][:110]


def _inject_shell_css():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { min-width: 72px !important; max-width: 72px !important; }
        [data-testid="stSidebar"] .block-container { padding-top: 0.8rem; padding-left: 0.35rem; padding-right: 0.35rem; }
        [data-testid="stSidebar"] button { font-size: 0.85rem !important; padding: 0.40rem 0 !important; line-height: 1 !important; }
        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: 100% !important;
            padding-top: 0.7rem;
            padding-left: 1rem;
            padding-right: 1rem;
            padding-bottom: 0.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sync_query_params(state):
    st.query_params["selected_node_id"] = state.get("selected_node_id", "")
    st.query_params["view_mode"] = state.get("view_mode", "canvas")
    st.query_params["menu_banner_open"] = "1" if state.get("menu_banner_open", False) else "0"


def _hydrate_state_from_query(state):
    query = st.query_params
    selected_from_query = query.get("selected_node_id")
    view_mode_from_query = query.get("view_mode")
    menu_banner_from_query = query.get("menu_banner_open")
    if isinstance(selected_from_query, list):
        selected_from_query = selected_from_query[-1] if selected_from_query else None
    if isinstance(view_mode_from_query, list):
        view_mode_from_query = view_mode_from_query[-1] if view_mode_from_query else None
    if isinstance(menu_banner_from_query, list):
        menu_banner_from_query = menu_banner_from_query[-1] if menu_banner_from_query else None

    node_ids = [row["id"] for row in state.get("nodes", [])]
    if selected_from_query and selected_from_query in node_ids:
        state["selected_node_id"] = selected_from_query
    if view_mode_from_query in {"canvas", "tool-focus"}:
        state["view_mode"] = view_mode_from_query
    if menu_banner_from_query in {"0", "1"}:
        state["menu_banner_open"] = menu_banner_from_query == "1"


def _render_node_workspace(state, api_client, lock_info):
    node = selected_node(state)
    if not node:
        st.info("Select a node from canvas.")
        return
    st.subheader("Node Workspace")
    st.write(f"**{node['label']}**")
    st.caption(f"{node['desc']} | id: {node['id']} | status: {node.get('status', 'ready')}")

    if node["type"] == "reference":
        render_reference_workspace(state, api_client)
    elif node["type"] == "translate":
        render_translate_workspace(state, api_client)
    elif node["type"] == "normalize":
        render_normalize_workspace(state, api_client)
    elif node["type"] == "extract":
        render_extract_workspace(state, api_client)
    elif node["type"] == "theory":
        render_theory_workspace(state, api_client)
    elif node["type"] == "question":
        render_question_workspace(state, api_client)
    elif node["type"] == "methodology":
        render_methodology_workspace(state, api_client, lock_info)


def _render_left_menu(state):
    with st.sidebar:
        if st.button("H", use_container_width=True, help="Canvas View", key="left_menu_canvas"):
            state["view_mode"] = "canvas"
            _sync_query_params(state)
            st.rerun()
        if st.button("B", use_container_width=True, help="Work Banner", key="left_menu_banner"):
            state["menu_banner_open"] = not state.get("menu_banner_open", False)
            _sync_query_params(state)
            st.rerun()
        if st.button("W", use_container_width=True, help="Workspace", key="left_menu_workspace"):
            state["view_mode"] = "tool-focus" if state.get("view_mode") == "canvas" else "canvas"
            _sync_query_params(state)
            st.rerun()
        if st.button("R", use_container_width=True, help="Run Node", key="left_menu_run"):
            return {"run_selected": True, "load_sample": False}
        if st.button("S", use_container_width=True, help="Sample Workflow", key="left_menu_sample"):
            return {"run_selected": False, "load_sample": True}

        ordered_core = [
            CORE_NODE_IDS["REF"],
            CORE_NODE_IDS["RAW"],
            CORE_NODE_IDS["NORM"],
            CORE_NODE_IDS["EXTRACT"],
            CORE_NODE_IDS["THEORY"],
            CORE_NODE_IDS["QUESTION"],
            CORE_NODE_IDS["METHOD"],
        ]
        nodes = state.get("nodes", [])
        node_map = {row["id"]: row for row in nodes}
        ordered_nodes = [node_map[nid] for nid in ordered_core if nid in node_map]
        ordered_nodes.extend([row for row in nodes if row["id"] not in ordered_core])

        icon_by_type = {
            "reference": "RF",
            "translate": "TR",
            "normalize": "NM",
            "extract": "EX",
            "theory": "TH",
            "question": "RQ",
            "methodology": "MT",
        }
        for row in ordered_nodes:
            icon = icon_by_type.get(row.get("type"), "ND")
            if st.button(icon, use_container_width=True, help=f"{row['label']} ({row.get('status', 'ready')})", key=f"left_node_{row['id']}"):
                if state.get("selected_node_id") == row["id"] and state.get("view_mode") == "tool-focus":
                    state["view_mode"] = "canvas"
                else:
                    state["selected_node_id"] = row["id"]
                    state["view_mode"] = "tool-focus"
                _sync_query_params(state)
                st.rerun()
    return {"run_selected": False, "load_sample": False}


def _render_command_banner(state, api_client):
    st.info("Work Banner")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("Run Selected Node", use_container_width=True, key="banner_run_selected"):
            ok, msg = run_selected_node(state, api_client)
            apply_and_refresh(ok, msg)
    with c2:
        if st.button("Load Sample Workflow", use_container_width=True, key="banner_load_sample"):
            ok, msg = load_sample_workflow_action(state)
            apply_and_refresh(ok, msg)
    with c3:
        if st.button("Close Banner", use_container_width=True, key="banner_close"):
            state["menu_banner_open"] = False
            _sync_query_params(state)
            st.rerun()

    left, right = st.columns([1.2, 1.1], gap="medium")
    with left:
        events = render_builder_panel(state, NODE_TEMPLATES)
        if events["load_sample"]:
            ok, msg = load_sample_workflow_action(state)
            apply_and_refresh(ok, msg)
        if events["create_node"]:
            ok, msg = create_node_from_builder(state)
            apply_and_refresh(ok, msg)
        if events["connect_nodes"]:
            ok, msg = connect_nodes_from_builder(state)
            apply_and_refresh(ok, msg)
    with right:
        status = compute_pipeline_status(state)
        apply_node_status(state, status)
        render_pipeline_status(state, status)
        render_api_log(state)


def main():
    st.set_page_config(page_title="Paper Assistant Streamlit Branch", layout="wide")
    init_session_state(st.session_state)
    _hydrate_state_from_query(st.session_state)
    _inject_shell_css()

    st.title("Paper Assistant - Streamlit Branch")
    st.caption("Canvas uses full width. Click node on canvas to switch to node workspace.")

    api_client = APIClient(st.session_state)

    menu_events = _render_left_menu(st.session_state)
    if menu_events["run_selected"]:
        ok, msg = run_selected_node(st.session_state, api_client)
        apply_and_refresh(ok, msg)
    if menu_events["load_sample"]:
        ok, msg = load_sample_workflow_action(st.session_state)
        apply_and_refresh(ok, msg)

    status = compute_pipeline_status(st.session_state)
    apply_node_status(st.session_state, status)
    lock_info = methodology_lock(st.session_state, status)

    if st.session_state.get("view_mode", "canvas") == "tool-focus":
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("Back To Canvas", use_container_width=True, key="focus_back_canvas"):
                st.session_state["view_mode"] = "canvas"
                _sync_query_params(st.session_state)
                st.rerun()
        with c2:
            if st.button("Run Selected Node", use_container_width=True, key="focus_run_selected"):
                ok, msg = run_selected_node(st.session_state, api_client)
                apply_and_refresh(ok, msg)
        with c3:
            if st.button("Work Banner", use_container_width=True, key="focus_toggle_banner"):
                st.session_state["menu_banner_open"] = not st.session_state.get("menu_banner_open", False)
                _sync_query_params(st.session_state)
                st.rerun()

        if st.session_state.get("menu_banner_open", False):
            _render_command_banner(st.session_state, api_client)
        _render_node_workspace(st.session_state, api_client, lock_info)
        _sync_query_params(st.session_state)
        return

    top1, top2 = st.columns([1, 5])
    with top1:
        if st.button("Work Banner", use_container_width=True, key="canvas_toggle_banner"):
            st.session_state["menu_banner_open"] = not st.session_state.get("menu_banner_open", False)
            _sync_query_params(st.session_state)
            st.rerun()
    with top2:
        st.caption("Banner is not fixed. It appears only after pressing Work Banner.")

    if st.session_state.get("menu_banner_open", False):
        _render_command_banner(st.session_state, api_client)

    status = compute_pipeline_status(st.session_state)
    apply_node_status(st.session_state, status)
    selected_id = render_canvas(
        st.session_state["nodes"],
        st.session_state["edges"],
        st.session_state.get("selected_node_id"),
    )
    if selected_id and selected_id != st.session_state.get("selected_node_id"):
        st.session_state["selected_node_id"] = selected_id
        st.session_state["view_mode"] = "tool-focus"
        _sync_query_params(st.session_state)
        st.rerun()

    _sync_query_params(st.session_state)


if __name__ == "__main__":
    main()
