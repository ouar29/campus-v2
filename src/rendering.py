from __future__ import annotations

import base64
import uuid

from model import Campus, Floor, Room
from geometry import SCALE, building_footprint, world_to_px

CANVAS_BG = "#211d55"
CANVAS_STROKE = "#4338ca"
FLOOR_FILL = "#3730a3"
FLOOR_STROKE = "#a5b4fc"
GRID_LINE_COLOR = "#4338ca"
TEXT_PRIMARY = "#eef2ff"
TEXT_SECONDARY = "#c7d2fe"
PALETTE = [
    "#60a5fa",
    "#f59e0b",
    "#34d399",
    "#f472b6",
    "#a78bfa",
    "#f87171",
    "#2dd4bf",
]


def blank_background(w_units: float, h_units: float) -> str:
    """Image de fond (data URI SVG) de taille pixel fixe = w_units*SCALE x h_units*SCALE."""
    w_px, h_px = w_units * SCALE, h_units * SCALE
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_px}" height="{h_px}">'
        f'<rect width="100%" height="100%" fill="{CANVAS_BG}" stroke="{CANVAS_STROKE}" stroke-width="1"/>'
        f"</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def grid_lines_svg(origin_x: float, origin_y: float, w_units: float, h_units: float, step: float = 5.0) -> str:
    parts = []
    x = -(origin_x % step)
    while x < w_units:
        px, _ = world_to_px(origin_x + x, 0, origin_x, origin_y)
        parts.append(f'<line x1="{px}" y1="0" x2="{px}" y2="{h_units * SCALE}" stroke="{GRID_LINE_COLOR}" stroke-width="1"/>')
        x += step
    y = -(origin_y % step)
    while y < h_units:
        _, py = world_to_px(0, origin_y + y, origin_x, origin_y)
        parts.append(f'<line x1="0" y1="{py}" x2="{w_units * SCALE}" y2="{py}" stroke="{GRID_LINE_COLOR}" stroke-width="1"/>')
        y += step
    return "".join(parts)


def room_svg(room: Room, origin_x: float, origin_y: float) -> str:
    cx, cy = world_to_px(room.position[0], room.position[1], origin_x, origin_y)
    r = 1.0 * SCALE
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#93c5fd" fill-opacity="0.9" '
        f'stroke="#1d4ed8" stroke-width="2"><title>{room.name} — {room.capacity} pers.</title></circle>'
        f'<text x="{cx}" y="{cy - r - 10}" font-size="20" font-weight="600" text-anchor="middle" fill="{TEXT_PRIMARY}">{room.name}</text>'
        f'<text x="{cx}" y="{cy + r + 22}" font-size="16" text-anchor="middle" fill="{TEXT_SECONDARY}">{room.capacity} pers.</text>'
    )


def floor_plan_content(floor: Floor, origin_x: float, origin_y: float) -> str:
    parts = []
    poly_px = " ".join(f"{px},{py}" for px, py in (world_to_px(x, y, origin_x, origin_y) for x, y in floor.polygon))
    parts.append(f'<polygon points="{poly_px}" fill="{FLOOR_FILL}" stroke="{FLOOR_STROKE}" stroke-width="2"/>')
    for room in floor.rooms:
        parts.append(room_svg(room, origin_x, origin_y))
    return "".join(parts)


def drawing_preview_content(points: list[list[float]], origin_x: float, origin_y: float) -> str:
    w_units, h_units = 50.0, 30.0
    parts = [grid_lines_svg(origin_x, origin_y, w_units, h_units)]
    if points:
        px_points = [world_to_px(x, y, origin_x, origin_y) for x, y in points]
        line_points = " ".join(f"{px},{py}" for px, py in px_points)
        parts.append(f'<polyline points="{line_points}" fill="none" stroke="#1d4ed8" stroke-width="2" stroke-dasharray="6,4"/>')
        for i, (px, py) in enumerate(px_points):
            radius = 6 if i == 0 else 5
            fill = "#dc2626" if i == 0 else "#1d4ed8"
            parts.append(f'<circle cx="{px}" cy="{py}" r="{radius}" fill="{fill}"/>')
    return "".join(parts)


def floor_edit_content(floor: Floor, origin_x: float, origin_y: float) -> str:
    """Plan de l'étage avec poignées de sommets pour l'édition du contour."""
    parts = [floor_plan_content(floor, origin_x, origin_y)]
    for i, (x, y) in enumerate(floor.polygon):
        px, py = world_to_px(x, y, origin_x, origin_y)
        parts.append(f'<circle cx="{px}" cy="{py}" r="7" fill="#f59e0b" stroke="#78350f" stroke-width="2"/>')
    return "".join(parts)


def _escape_js_string(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def campus_map_shapes_svg(campus: Campus, origin_x: float, origin_y: float) -> str:
    parts = []
    for building in campus.buildings:
        footprint = building_footprint(building)
        color = PALETTE[hash(building.id) % len(PALETTE)]
        pts_px = [world_to_px(x, y, origin_x, origin_y) for x, y in footprint]
        points_str = " ".join(f"{px},{py}" for px, py in pts_px)
        parts.append(
            f'<polygon points="{points_str}" fill="{color}" fill-opacity="0.85" stroke="#1f2937" stroke-width="2">'
            f'<title>{building.name} ({len(building.floors)} étage(s))</title></polygon>'
        )
    return "".join(parts)


def campus_grid_step(w_units: float, h_units: float) -> float:
    extent = max(w_units, h_units, 1.0)
    raw_step = extent / 10.0
    nice_steps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000]
    for step in nice_steps:
        if step >= raw_step:
            return step
    return nice_steps[-1]


def campus_map_parts(campus: Campus) -> tuple[str, str]:
    """Retourne (html, js) pour le plan du campus."""
    from geometry import campus_transform, building_footprint, world_to_px

    origin_x, origin_y, w_units, h_units = campus_transform(campus)
    w_px, h_px = w_units * SCALE, h_units * SCALE
    step = campus_grid_step(w_units, h_units)
    uid = uuid.uuid4().hex

    svg = (
        f'<svg id="campusmap-svg-{uid}" width="{w_px}" height="{h_px}" viewBox="0 0 {w_px} {h_px}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block; max-width:100%; max-height:100%; '
        f'width:auto; height:auto; background:{CANVAS_BG}; border:1px solid {CANVAS_STROKE}; border-radius:8px;">'
        + grid_lines_svg(origin_x, origin_y, w_units, h_units, step=step)
        + campus_map_shapes_svg(campus, origin_x, origin_y)
        + "</svg>"
    )

    labels_json = "[" + ",".join(
        (
            lambda pts_px: f'{{"name":"{_escape_js_string(building.name)}",'
            f'"cx":{sum(p[0] for p in pts_px) / len(pts_px)},'
            f'"cy":{sum(p[1] for p in pts_px) / len(pts_px)}}}'
        )([world_to_px(x, y, origin_x, origin_y) for x, y in building_footprint(building)])
        for building in campus.buildings
    ) + "]"

    html = f"""
    <div id="campusmap-wrap-{uid}" style="position:relative; width:100%; height:100%; display:flex;
         align-items:center; justify-content:center; overflow:hidden;">
      {svg}
      <div id="campusmap-labels-{uid}" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none;"></div>
      <div style="position:absolute; left:8px; bottom:8px; font-size:13px; color:{TEXT_SECONDARY};">
        grille : {step:g} unités — échelle réelle, aucune déformation
      </div>
    </div>
    """

    js = f"""
    (function() {{
        const wrap = document.getElementById("campusmap-wrap-{uid}");
        const svgEl = document.getElementById("campusmap-svg-{uid}");
        const layer = document.getElementById("campusmap-labels-{uid}");
        if (!wrap || !svgEl || !layer) {{ return; }}
        const labels = {labels_json};
        const viewW = {w_px};
        const viewH = {h_px};

        function reposition() {{
            if (!wrap.isConnected) return;
            const svgRect = svgEl.getBoundingClientRect();
            const wrapRect = wrap.getBoundingClientRect();
            if (svgRect.width === 0 || svgRect.height === 0) return;
            const scaleX = svgRect.width / viewW;
            const scaleY = svgRect.height / viewH;
            const offsetLeft = svgRect.left - wrapRect.left;
            const offsetTop = svgRect.top - wrapRect.top;
            layer.innerHTML = "";
            labels.forEach(function(lbl) {{
                const div = document.createElement("div");
                div.textContent = lbl.name;
                div.style.position = "absolute";
                div.style.left = (offsetLeft + lbl.cx * scaleX) + "px";
                div.style.top = (offsetTop + lbl.cy * scaleY) + "px";
                div.style.transform = "translate(-50%, -50%)";
                div.style.fontSize = "24px";
                div.style.fontWeight = "700";
                div.style.color = "{TEXT_PRIMARY}";
                div.style.textShadow = "0 0 4px #0f0e2a, 0 0 6px #0f0e2a, 0 0 8px #0f0e2a";
                div.style.whiteSpace = "nowrap";
                layer.appendChild(div);
            }});
        }}

        const resizeObserver = new ResizeObserver(reposition);
        resizeObserver.observe(wrap);

        let framesLeft = 40;
        function pollReposition() {{
            reposition();
            framesLeft -= 1;
            if (framesLeft > 0) {{
                requestAnimationFrame(pollReposition);
            }}
        }}
        requestAnimationFrame(pollReposition);
    }})();
    """
    return html, js
