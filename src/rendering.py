from __future__ import annotations

import base64
import uuid

from model import Campus, Floor, Room
from geometry import PLAN_DISPLAY_WIDTH_PX, SCALE, building_footprint, world_to_px
from theme import DARK, Palette


def text_scale_for_canvas(w_units: float) -> float:
    """Facteur de compensation pour que le texte garde une taille constante à
    l'écran, quelle que soit la taille réelle (en unités monde) de l'étage.

    Le plan est dessiné à échelle réelle fixe (SCALE px par unité), donc le
    canevas natif fait `w_units * SCALE` pixels de large. Le navigateur
    redimensionne ensuite cette image pour tenir dans une largeur d'affichage
    fixe (PLAN_DISPLAY_WIDTH_PX, via le style CSS "max-width"). Un étage deux
    fois plus grand est donc affiché deux fois plus petit à l'écran : sans
    compensation, un texte de taille fixe en unités SVG rétrécirait (ou
    grossirait) avec la taille de l'étage. En multipliant les tailles de
    police par ce facteur, le texte reste lisible et de taille visuelle
    constante quel que soit le contour de l'étage.
    """
    canvas_w_px = max(w_units * SCALE, 1.0)
    return canvas_w_px / PLAN_DISPLAY_WIDTH_PX


def blank_background(w_units: float, h_units: float, palette: Palette = DARK) -> str:
    """Image de fond (data URI SVG) de taille pixel fixe = w_units*SCALE x h_units*SCALE."""
    w_px, h_px = w_units * SCALE, h_units * SCALE
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_px}" height="{h_px}">'
        f'<rect width="100%" height="100%" fill="{palette.CANVAS_BG}" stroke="{palette.CANVAS_STROKE}" stroke-width="1"/>'
        f"</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def grid_lines_svg(origin_x: float, origin_y: float, w_units: float, h_units: float, step: float = 5.0, palette: Palette = DARK) -> str:
    parts = []
    x = -(origin_x % step)
    while x < w_units:
        px, _ = world_to_px(origin_x + x, 0, origin_x, origin_y)
        parts.append(f'<line x1="{px}" y1="0" x2="{px}" y2="{h_units * SCALE}" stroke="{palette.GRID_LINE_COLOR}" stroke-width="1"/>')
        x += step
    y = -(origin_y % step)
    while y < h_units:
        _, py = world_to_px(0, origin_y + y, origin_x, origin_y)
        parts.append(f'<line x1="0" y1="{py}" x2="{w_units * SCALE}" y2="{py}" stroke="{palette.GRID_LINE_COLOR}" stroke-width="1"/>')
        y += step
    return "".join(parts)


def room_svg(room: Room, origin_x: float, origin_y: float, text_scale: float = 1.0, palette: Palette = DARK) -> str:
    cx, cy = world_to_px(room.position[0], room.position[1], origin_x, origin_y)
    r = 1.0 * SCALE
    name_font = 24 * text_scale
    cap_font = 18 * text_scale
    gap_above = 12 * text_scale
    gap_below = 26 * text_scale
    is_unavailable = not room.extra.get("available", True)
    if is_unavailable:
        fill, fill_opacity, stroke, dash = palette.ROOM_UNAVAILABLE_FILL, "0.6", palette.ROOM_UNAVAILABLE_STROKE, ' stroke-dasharray="4,3"'
        name_fill = palette.TEXT_SECONDARY
        title_suffix = " (indisponible)"
    else:
        fill, fill_opacity, stroke, dash = palette.ROOM_FILL, "0.9", palette.ROOM_STROKE, ""
        name_fill = palette.TEXT_PRIMARY
        title_suffix = ""
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" fill-opacity="{fill_opacity}" '
        f'stroke="{stroke}" stroke-width="2"{dash}><title>{room.name} — {room.capacity} pers.{title_suffix}</title></circle>'
        f'<text x="{cx}" y="{cy - r - gap_above:.2f}" font-size="{name_font:.2f}" font-weight="700" text-anchor="middle" fill="{name_fill}">{room.name}</text>'
        f'<text x="{cx}" y="{cy + r + gap_below:.2f}" font-size="{cap_font:.2f}" font-weight="600" text-anchor="middle" fill="{palette.TEXT_SECONDARY}">{room.capacity} pers.</text>'
    )


def floor_plan_content(floor: Floor, origin_x: float, origin_y: float, text_scale: float = 1.0, palette: Palette = DARK) -> str:
    parts = []
    poly_px = " ".join(f"{px},{py}" for px, py in (world_to_px(x, y, origin_x, origin_y) for x, y in floor.polygon))
    parts.append(f'<polygon points="{poly_px}" fill="{palette.FLOOR_FILL}" stroke="{palette.FLOOR_STROKE}" stroke-width="2"/>')
    for room in floor.rooms:
        parts.append(room_svg(room, origin_x, origin_y, text_scale, palette))
    return "".join(parts)


def drawing_preview_content(points: list[list[float]], origin_x: float, origin_y: float, palette: Palette = DARK) -> str:
    w_units, h_units = 50.0, 30.0
    parts = [grid_lines_svg(origin_x, origin_y, w_units, h_units, palette=palette)]
    if points:
        px_points = [world_to_px(x, y, origin_x, origin_y) for x, y in points]
        line_points = " ".join(f"{px},{py}" for px, py in px_points)
        parts.append(f'<polyline points="{line_points}" fill="none" stroke="{palette.DRAW_LINE_COLOR}" stroke-width="2" stroke-dasharray="6,4"/>')
        for i, (px, py) in enumerate(px_points):
            radius = 6 if i == 0 else 5
            fill = palette.DRAW_FIRST_VERTEX_COLOR if i == 0 else palette.DRAW_LINE_COLOR
            parts.append(f'<circle cx="{px}" cy="{py}" r="{radius}" fill="{fill}"/>')
    return "".join(parts)


def floor_edit_content(floor: Floor, origin_x: float, origin_y: float, text_scale: float = 1.0, palette: Palette = DARK) -> str:
    """Plan de l'étage avec poignées de sommets pour l'édition du contour."""
    parts = [floor_plan_content(floor, origin_x, origin_y, text_scale, palette)]
    for x, y in floor.polygon:
        px, py = world_to_px(x, y, origin_x, origin_y)
        parts.append(f'<circle cx="{px}" cy="{py}" r="7" fill="{palette.VERTEX_FILL}" stroke="{palette.VERTEX_STROKE}" stroke-width="2"/>')
    return "".join(parts)


def _escape_js_string(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def campus_map_shapes_svg(campus: Campus, origin_x: float, origin_y: float, palette: Palette = DARK) -> str:
    parts = []
    for building in campus.buildings:
        footprint = building_footprint(building)
        color = palette.PLAN_PALETTE[hash(building.id) % len(palette.PLAN_PALETTE)]
        pts_px = [world_to_px(x, y, origin_x, origin_y) for x, y in footprint]
        points_str = " ".join(f"{px},{py}" for px, py in pts_px)
        parts.append(
            f'<polygon points="{points_str}" fill="{color}" fill-opacity="0.85" stroke="{palette.OUTLINE_DARK}" stroke-width="2">'
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


def campus_map_parts(campus: Campus, palette: Palette = DARK) -> tuple[str, str]:
    """Retourne (html, js) pour le plan du campus."""
    from geometry import campus_transform, building_footprint, world_to_px

    origin_x, origin_y, w_units, h_units = campus_transform(campus)
    w_px, h_px = w_units * SCALE, h_units * SCALE
    step = campus_grid_step(w_units, h_units)
    uid = uuid.uuid4().hex

    svg = (
        f'<svg id="campusmap-svg-{uid}" width="{w_px}" height="{h_px}" viewBox="0 0 {w_px} {h_px}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block; max-width:100%; max-height:100%; '
        f'width:auto; height:auto; background:{palette.CANVAS_BG}; border:1px solid {palette.CANVAS_STROKE}; border-radius:8px;">'
        + grid_lines_svg(origin_x, origin_y, w_units, h_units, step=step, palette=palette)
        + campus_map_shapes_svg(campus, origin_x, origin_y, palette)
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
      <div style="position:absolute; left:8px; bottom:8px; font-size:13px; color:{palette.TEXT_SECONDARY};">
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
                div.style.color = "{palette.TEXT_PRIMARY}";
                div.style.textShadow = "0 0 4px {palette.TEXT_SHADOW_COLOR}, 0 0 6px {palette.TEXT_SHADOW_COLOR}, 0 0 8px {palette.TEXT_SHADOW_COLOR}";
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
