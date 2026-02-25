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
from core.pipeline import API_PROVIDERS, CATEGORIES, METHOD_TEMPLATES, NODE_TEMPLATES
from core.state import (
    apply_node_status,
    build_artifact_index,
    compute_pipeline_status,
    init_session_state,
    methodology_lock,
    selected_node,
)
from services.api_client import APIClient


def notify(ok: bool, message: str):
    st.toast(message, icon="✅" if ok else "⚠️")


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
    preview = [
        {"index": row["index"] + 1, "text": row["translated_text"][:140]}
        for row in units[:40]
    ]
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

    if state["sentence_view_mode"] == "highlight":
        visible_units = [
            unit
            for unit in units
            if artifact_map.get(unit["id"], {}).get("highlight")
        ]
    else:
        visible_units = units

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

    st.caption(
        f"Sentence blocks: {len(visible_units)} | Selected: {len(selected_ids)} | Artifacts: {len(artifacts)}"
    )
    preview_rows = []
    for unit in visible_units[:80]:
        unit_artifacts = artifact_map.get(unit["id"], {})
        category = (unit_artifacts.get("category") or [{}])[-1].get("tag", "uncategorized")
        color = (unit_artifacts.get("highlight") or [{}])[-1].get("tag", "")
        text = unit["raw_text"] if state["sentence_view_mode"] == "raw" else unit["translated_text"]
        preview_rows.append(
            {
                "index": unit["index"] + 1,
                "category": category,
                "highlight": color,
                "text": text[:180],
            }
        )
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
    category_map = theory.get("category_map", {})
    st.json(category_map)
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
    st.warning(
        "Lock condition: approved question + category artifacts + evidence links >= 3"
    )
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

    if st.button(
        "Run Methodology Node",
        use_container_width=True,
        key="run_method_node",
        disabled=lock_info["locked"],
    ):
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


def main():
    st.set_page_config(page_title="Paper Assistant Streamlit Branch", layout="wide")
    init_session_state(st.session_state)

    st.title("Paper Assistant - Streamlit Branch")
    st.caption("Original React project is preserved. This app runs in apps/streamlit only.")

    api_client = APIClient(st.session_state)

    top_col1, top_col2, top_col3 = st.columns([5, 2, 2])
    with top_col2:
        if st.button("Run Selected Node", use_container_width=True, key="run_selected_top"):
            ok, msg = run_selected_node(st.session_state, api_client)
            apply_and_refresh(ok, msg)
    with top_col3:
        if st.button("Load Sample Workflow", use_container_width=True, key="load_sample_top"):
            ok, msg = load_sample_workflow_action(st.session_state)
            apply_and_refresh(ok, msg)

    left, center, right = st.columns([1.35, 2.6, 2.05], gap="medium")

    with left:
        events = render_builder_panel(st.session_state, NODE_TEMPLATES)
        if events["load_sample"]:
            ok, msg = load_sample_workflow_action(st.session_state)
            apply_and_refresh(ok, msg)
        if events["create_node"]:
            ok, msg = create_node_from_builder(st.session_state)
            apply_and_refresh(ok, msg)
        if events["connect_nodes"]:
            ok, msg = connect_nodes_from_builder(st.session_state)
            apply_and_refresh(ok, msg)

        status = compute_pipeline_status(st.session_state)
        apply_node_status(st.session_state, status)
        lock_info = methodology_lock(st.session_state, status)

        render_pipeline_status(st.session_state, status)
        render_api_log(st.session_state)

    with center:
        status = compute_pipeline_status(st.session_state)
        apply_node_status(st.session_state, status)
        selected_id = render_canvas(
            st.session_state["nodes"],
            st.session_state["edges"],
            st.session_state.get("selected_node_id"),
        )
        if selected_id != st.session_state.get("selected_node_id"):
            st.session_state["selected_node_id"] = selected_id
            st.rerun()

    with right:
        status = compute_pipeline_status(st.session_state)
        apply_node_status(st.session_state, status)
        lock_info = methodology_lock(st.session_state, status)

        node = selected_node(st.session_state)
        if not node:
            st.info("Select a node from canvas.")
            return

        st.subheader("Node Workspace")
        st.write(f"**{node['label']}**")
        st.caption(f"{node['desc']} | id: {node['id']} | status: {node.get('status', 'ready')}")

        if node["type"] == "reference":
            render_reference_workspace(st.session_state, api_client)
        elif node["type"] == "translate":
            render_translate_workspace(st.session_state, api_client)
        elif node["type"] == "normalize":
            render_normalize_workspace(st.session_state, api_client)
        elif node["type"] == "extract":
            render_extract_workspace(st.session_state, api_client)
        elif node["type"] == "theory":
            render_theory_workspace(st.session_state, api_client)
        elif node["type"] == "question":
            render_question_workspace(st.session_state, api_client)
        elif node["type"] == "methodology":
            render_methodology_workspace(st.session_state, api_client, lock_info)


if __name__ == "__main__":
    main()
