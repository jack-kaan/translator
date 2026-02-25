import html

import streamlit as st
import streamlit.components.v1 as components


NODE_WIDTH = 250
NODE_HEIGHT = 110


def _status_colors(status):
    if status == "completed":
        return "#10b981", "#ecfdf5", "#065f46"
    if status == "ready":
        return "#3b82f6", "#eff6ff", "#1e3a8a"
    if status == "blocked":
        return "#94a3b8", "#f8fafc", "#475569"
    return "#94a3b8", "#f8fafc", "#475569"


def _truncate(value, length=40):
    if len(value) <= length:
        return value
    return f"{value[: length - 3]}..."


def _escape(value):
    return html.escape(str(value))


def _edge_path(from_node, to_node, mode, sibling_offset):
    if mode == "vertical":
        x1 = from_node["x"] + NODE_WIDTH / 2 + sibling_offset
        y1 = from_node["y"] + NODE_HEIGHT
        x2 = to_node["x"] + NODE_WIDTH / 2 + sibling_offset
        y2 = to_node["y"]
        dy = y2 - y1
        c1y = y1 + dy / 2
        c2y = y2 - dy / 2
        path = f"M {x1} {y1} C {x1} {c1y}, {x2} {c2y}, {x2} {y2}"
        lx = (x1 + x2) / 2
        ly = (y1 + y2) / 2 - 10
        return path, lx, ly

    x1 = from_node["x"] + NODE_WIDTH
    y1 = from_node["y"] + NODE_HEIGHT / 2 + sibling_offset
    x2 = to_node["x"]
    y2 = to_node["y"] + NODE_HEIGHT / 2 + sibling_offset
    dx = x2 - x1
    c1 = x1 + dx / 2
    c2 = x2 - dx / 2
    path = f"M {x1} {y1} C {c1} {y1}, {c2} {y2}, {x2} {y2}"
    lx = (x1 + x2) / 2
    ly = y1 - 8
    return path, lx, ly


def render_canvas(nodes, edges, selected_node_id):
    if not nodes:
        st.info("No nodes available.")
        return None

    max_x = max(node["x"] for node in nodes) + NODE_WIDTH + 140
    max_y = max(node["y"] for node in nodes) + NODE_HEIGHT + 140
    width = max(1600, int(max_x))
    height = max(520, int(max_y))

    node_map = {node["id"]: node for node in nodes}
    svg_parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#f8fafc"/>',
    ]

    for edge in edges:
        from_node = node_map.get(edge["from_id"])
        to_node = node_map.get(edge["to_id"])
        if not from_node or not to_node:
            continue
        siblings = [e for e in edges if e["from_id"] == edge["from_id"] and e["to_id"] == edge["to_id"]]
        sibling_idx = next((idx for idx, row in enumerate(siblings) if row["id"] == edge["id"]), 0)
        sibling_offset = (sibling_idx - (len(siblings) - 1) / 2) * (26 if edge.get("mode") == "parallel" else 18)
        active = selected_node_id in {edge["from_id"], edge["to_id"]}

        path, lx, ly = _edge_path(from_node, to_node, edge.get("mode", "horizontal"), sibling_offset)
        stroke = "#3b82f6" if active else "#cbd5e1"
        text_fill = "#1d4ed8" if active else "#64748b"
        svg_parts.append(
            f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="2.6" />'
        )
        svg_parts.append(
            f'<text x="{lx}" y="{ly}" fill="{text_fill}" font-size="11" text-anchor="middle" font-weight="600">{_escape(edge.get("label", ""))}</text>'
        )

    for node in nodes:
        selected = node["id"] == selected_node_id
        border, bg, text_color = _status_colors(node.get("status", "ready"))
        stroke = "#4f46e5" if selected else border
        stroke_width = 3 if selected else 2
        x = node["x"]
        y = node["y"]
        svg_parts.append(
            f'<rect x="{x}" y="{y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="12" fill="{bg}" stroke="{stroke}" stroke-width="{stroke_width}" />'
        )
        svg_parts.append(
            f'<text x="{x + 12}" y="{y + 28}" fill="#0f172a" font-size="13" font-weight="700">{_escape(_truncate(node.get("label", ""), 34))}</text>'
        )
        svg_parts.append(
            f'<text x="{x + 12}" y="{y + 50}" fill="#475569" font-size="11">{_escape(_truncate(node.get("desc", ""), 44))}</text>'
        )
        svg_parts.append(
            f'<text x="{x + 12}" y="{y + 78}" fill="{text_color}" font-size="10" font-weight="600">status: {_escape(node.get("status", "ready"))}</text>'
        )
        svg_parts.append(
            f'<text x="{x + 12}" y="{y + 96}" fill="#64748b" font-size="9">{_escape(node.get("id", ""))}</text>'
        )

    svg_parts.append("</svg>")
    html_block = "".join(svg_parts)
    components.html(html_block, height=min(max(height + 20, 380), 900), scrolling=True)

    options = [node["id"] for node in nodes]
    if selected_node_id not in options:
        selected_node_id = options[0]
    selected_id = st.selectbox(
        "Selected Node",
        options,
        index=options.index(selected_node_id),
        format_func=lambda nid: next((f"{row['label']} ({row['id']})" for row in nodes if row["id"] == nid), nid),
    )
    return selected_id
