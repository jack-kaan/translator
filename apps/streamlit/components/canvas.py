from collections import defaultdict

import streamlit as st

try:
    from streamlit_flow import streamlit_flow
    from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode
    from streamlit_flow.state import StreamlitFlowState

    FLOW_AVAILABLE = True
except Exception:
    FLOW_AVAILABLE = False


STATUS_COLORS = {
    "completed": "#22c55e",
    "ready": "#3b82f6",
    "blocked": "#ef4444",
    "idle": "#64748b",
}


def render_canvas(nodes, edges, selected_node_id):
    _inject_canvas_css()
    if not FLOW_AVAILABLE:
        return _render_fallback(nodes, selected_node_id)

    flow_nodes = [_to_flow_node(node, selected_node_id) for node in nodes]
    flow_edges = _to_flow_edges(edges, selected_node_id)
    flow_state = StreamlitFlowState(
        nodes=flow_nodes,
        edges=flow_edges,
        selected_id=selected_node_id,
    )

    next_state = _run_flow(flow_state)
    _sync_positions(nodes, next_state)
    selected = _extract_selected(next_state)
    if selected:
        return selected
    return selected_node_id


def _run_flow(flow_state):
    base = {
        "fit_view": True,
        "show_minimap": False,
        "show_controls": True,
        "allow_new_edges": False,
        "animate_new_edges": False,
        "height": 780,
    }
    candidates = [
        base,
        {k: v for k, v in base.items() if k not in {"allow_new_edges", "animate_new_edges"}},
        {"fit_view": True, "height": 780},
        {},
    ]

    last_error = None
    for options in candidates:
        try:
            return streamlit_flow("paper-assistant-canvas", flow_state, **options)
        except TypeError as exc:
            last_error = exc
            continue
    if last_error:
        st.warning(f"streamlit_flow signature mismatch: {last_error}")
    return flow_state


def _to_flow_node(node, selected_node_id):
    status = node.get("status", "idle")
    selected = node["id"] == selected_node_id
    color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
    style = {
        "background": "#0f172a",
        "color": "#e2e8f0",
        "borderRadius": "12px",
        "border": f"2px solid {'#60a5fa' if selected else color}",
        "boxShadow": "0 8px 20px rgba(2, 6, 23, 0.45)",
        "fontSize": "12px",
        "padding": "8px",
    }
    content = f"{node.get('label', node['id'])}\n{status.upper()}"

    kwargs = {
        "id": node["id"],
        "pos": (int(node.get("x", 0)), int(node.get("y", 0))),
        "data": {"content": content},
        "node_type": "default",
        "draggable": True,
        "selectable": True,
        "connectable": False,
        "deletable": False,
        "width": 260,
        "height": 92,
        "style": style,
    }
    try:
        return StreamlitFlowNode(**kwargs)
    except TypeError:
        return StreamlitFlowNode(
            id=node["id"],
            pos=(int(node.get("x", 0)), int(node.get("y", 0))),
            data={"content": content},
        )


def _to_flow_edges(edges, selected_node_id):
    rendered = []
    sibling_index = defaultdict(int)
    for edge in edges:
        key = (edge.get("from_id"), edge.get("to_id"))
        sibling_index[key] += 1
        index = sibling_index[key] - 1
        rendered.append(_to_flow_edge(edge, index, selected_node_id))
    return rendered


def _to_flow_edge(edge, index, selected_node_id):
    mode = edge.get("mode", "horizontal")
    edge_type = "default"
    animated = False
    style = {
        "stroke": "#64748b",
        "strokeWidth": 2,
    }

    if mode == "vertical":
        edge_type = "step"
        style["stroke"] = "#14b8a6"
    elif mode == "parallel":
        edge_type = "straight"
        animated = True
        style["stroke"] = "#f59e0b"
        style["strokeDasharray"] = "4 4"

    if index > 0:
        style["strokeWidth"] = 1.5
        style["strokeOpacity"] = 0.85
        animated = True

    if edge.get("from_id") == selected_node_id or edge.get("to_id") == selected_node_id:
        style["strokeWidth"] = max(style["strokeWidth"], 3)

    label = edge.get("label", "")
    kwargs = {
        "id": edge["id"],
        "source": edge["from_id"],
        "target": edge["to_id"],
        "label": label,
        "edge_type": edge_type,
        "animated": animated,
        "marker_end": {"type": "arrow"},
        "style": style,
    }
    try:
        return StreamlitFlowEdge(**kwargs)
    except TypeError:
        return StreamlitFlowEdge(
            id=edge["id"],
            source=edge["from_id"],
            target=edge["to_id"],
            label=label,
            edge_type=edge_type,
            animated=animated,
        )


def _sync_positions(nodes, next_state):
    flow_nodes = _extract_nodes(next_state)
    if not flow_nodes:
        return
    pos_map = {}
    for flow_node in flow_nodes:
        node_id = _node_id(flow_node)
        xy = _extract_xy(flow_node)
        if node_id and xy:
            pos_map[node_id] = xy
    for node in nodes:
        if node["id"] in pos_map:
            x, y = pos_map[node["id"]]
            node["x"] = int(x)
            node["y"] = int(y)


def _extract_nodes(flow_state):
    if flow_state is None:
        return []
    if isinstance(flow_state, dict):
        return flow_state.get("nodes", [])
    return getattr(flow_state, "nodes", [])


def _extract_selected(flow_state):
    if flow_state is None:
        return None
    if isinstance(flow_state, dict):
        return flow_state.get("selected_id")
    return getattr(flow_state, "selected_id", None)


def _node_id(flow_node):
    if isinstance(flow_node, dict):
        return flow_node.get("id")
    return getattr(flow_node, "id", None)


def _extract_xy(flow_node):
    if isinstance(flow_node, dict):
        pos = flow_node.get("pos", flow_node.get("position"))
    else:
        pos = getattr(flow_node, "pos", None)
        if pos is None:
            pos = getattr(flow_node, "position", None)

    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return pos[0], pos[1]
    if isinstance(pos, dict):
        if "x" in pos and "y" in pos:
            return pos["x"], pos["y"]
    if pos is not None:
        x = getattr(pos, "x", None)
        y = getattr(pos, "y", None)
        if x is not None and y is not None:
            return x, y
    return None


def _render_fallback(nodes, selected_node_id):
    st.warning("Install `streamlit-flow-component` to use full canvas interactions.")
    ids = [node["id"] for node in nodes]
    if not ids:
        return None
    if selected_node_id not in ids:
        selected_node_id = ids[0]
    return st.selectbox("Node", ids, index=ids.index(selected_node_id), key="fallback_canvas_select")


def _inject_canvas_css():
    st.markdown(
        """
        <style>
        .st-key-fallback_canvas_select {
            margin-bottom: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
