import streamlit as st


def render_builder_panel(state, node_templates):
    st.subheader("Workflow Builder")
    load_sample = st.button("Load Sample Workflow", use_container_width=True, key="builder_load_sample")

    builder = state.get("workflow_builder", {})
    template_types = [template["type"] for template in node_templates]
    if builder.get("template_type") not in template_types:
        builder["template_type"] = template_types[0]

    builder["template_type"] = st.selectbox(
        "Node Template",
        template_types,
        index=template_types.index(builder.get("template_type", template_types[0])),
        key="builder_template_type",
    )
    builder["placement"] = st.selectbox(
        "Placement",
        ["parallel", "vertical", "horizontal"],
        index=["parallel", "vertical", "horizontal"].index(builder.get("placement", "parallel")),
        key="builder_placement",
    )
    create_node = st.button("Create Node", use_container_width=True, key="builder_create_node")

    node_ids = [node["id"] for node in state.get("nodes", [])]
    if node_ids:
        if builder.get("from_id") not in node_ids:
            builder["from_id"] = node_ids[0]
        if builder.get("to_id") not in node_ids:
            builder["to_id"] = node_ids[min(1, len(node_ids) - 1)]

        builder["from_id"] = st.selectbox(
            "From Node",
            node_ids,
            index=node_ids.index(builder["from_id"]),
            format_func=lambda nid: _format_node_label(state, nid),
            key="builder_from_id",
        )
        builder["to_id"] = st.selectbox(
            "To Node",
            node_ids,
            index=node_ids.index(builder["to_id"]),
            format_func=lambda nid: _format_node_label(state, nid),
            key="builder_to_id",
        )

    builder["edge_mode"] = st.selectbox(
        "Edge Mode",
        ["horizontal", "vertical", "parallel"],
        index=["horizontal", "vertical", "parallel"].index(builder.get("edge_mode", "horizontal")),
        key="builder_edge_mode",
    )
    builder["edge_label"] = st.text_input(
        "Edge Label (optional)",
        value=builder.get("edge_label", ""),
        key="builder_edge_label",
    )
    connect_nodes = st.button("Connect Nodes", use_container_width=True, key="builder_connect_nodes")

    state["workflow_builder"] = builder
    st.caption(f"Total nodes: {len(state.get('nodes', []))} | Total connections: {len(state.get('edges', []))}")
    return {"load_sample": load_sample, "create_node": create_node, "connect_nodes": connect_nodes}


def render_pipeline_status(state, status):
    st.subheader("Pipeline Status")
    rows = []
    for node in state.get("nodes", []):
        rows.append(
            {
                "node": node["label"],
                "id": node["id"],
                "type": node["type"],
                "status": status["per_node"].get(node["id"], "ready"),
            }
        )
    st.dataframe(rows, use_container_width=True, height=260)

    counters = status.get("counters", {})
    st.caption(
        f"approved RQ: {counters.get('approved_count', 0)} | category artifacts: {counters.get('category_count', 0)} | evidence links: {counters.get('evidence_count', 0)}"
    )


def render_api_log(state):
    st.subheader("API Call Log")
    logs = state.get("api_log", [])
    if not logs:
        st.caption("No logs yet.")
        return
    for entry in logs[:12]:
        mode = entry.get("mode", "mock")
        error = entry.get("error")
        if error:
            st.error(f"[{mode}] {entry['endpoint']} | {error}")
        else:
            st.success(f"[{mode}] {entry['endpoint']}")
        st.caption(entry.get("at", ""))


def _format_node_label(state, node_id):
    node = next((row for row in state.get("nodes", []) if row["id"] == node_id), None)
    if not node:
        return node_id
    return f"{node['label']} ({node['id']})"
