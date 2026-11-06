"""DEV-051 T05 / FEAT-014 + BUG-047 offline fixture: four-wall flange diagnosis.

The 0.7.0 R1 S3 case is a 185 x 232 x 1 mm base wall plus four flanges
(h80 / R2.54 / Y0.5) submitted as one plan whose edges were captured in a single
inspection (reported as 104-107). The third flange, perpendicular to the first
two, returned ProFeatureWithoptionsCreate=-1 and the fourth never ran.

Nothing here reproduces Creo; this module is the offline half of the diagnosis:

* edges are chosen from geometry (an inspection-shaped box payload), never from
  the reported 104-107 ids. An unqualified side is refused because a 1 mm wall
  has two parallel boundary edges 1 mm apart (top/bottom);
* each flange is re-selected from a refreshed inspection, and a reference is
  rejected when it disappeared or moved. The reported run captured all four ids
  once, before any flange existed -- the unguarded pattern;
* the same recipe feeds the driver and the unit tests (one source, no duplicate
  fixture), and every flange carries the judgement fields a live run must fill.

Oracles are independent boxes and arc lengths, never production code.
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from creo_mechdog.capabilities import families
from creo_mechdog.schema import SheetmetalFlangeOp, validate_operations

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- confirmed thin base plate (DEV-051 T03, BUG-032) ----------------------
PLATE_LENGTH_MM = 185.0
PLATE_WIDTH_MM = 232.0
PLATE_THICKNESS_MM = 1.0
PLATE_VOLUME_MM3 = 42_920.0
PLATE_BOUNDS = (
    (0.0, 0.0, 0.0),
    (PLATE_LENGTH_MM, PLATE_WIDTH_MM, PLATE_THICKNESS_MM),
)

# --- the one flange recipe reported for all four walls (0.7.0 R1 S3) ------
FLANGE_HEIGHT_MM = 80.0
FLANGE_RADIUS_MM = 2.54
FLANGE_Y_FACTOR = 0.5
FLANGE_ANGLE_DEG = 90.0

# --- original evidence, preserved verbatim --------------------------------
ORIGINAL_JOB = "f45415a90a0544bfad24fe1225c18f50"
ORIGINAL_MODEL = "0fdb2601c11e4471a3352f6254c59ef4"
ORIGINAL_MODEL_NAME = "acc70_sm2"
ORIGINAL_ERROR = "ProFeatureWithoptionsCreate=-1"
# Evidence only. Selection never reads these; the fixture catalog uses its own
# ids and renumbers them on every refresh.
REPORT_EDGE_IDS = (104, 105, 106, 107)
ORIGINAL_OPERATION_RESULTS = (
    {
        "op": "sheetmetal_flange",
        "index": 2,
        "label": "f_px",
        "execution_status": "succeeded",
        "effect_status": "rolled_back",
    },
    {
        "op": "sheetmetal_flange",
        "index": 4,
        "label": "f_ny",
        "execution_status": "failed",
        "effect_status": "rolled_back",
    },
    {
        "op": "sheetmetal_flange",
        "index": 5,
        "label": "f_py",
        "execution_status": "not_executed",
        "effect_status": "no_effect",
    },
)

TOL_MM = 0.01
SPAN_TOL_MM = 0.5

# A rim edge runs across the sheet thickness, so its span is comparable to the
# thickness itself; a wall boundary edge spans the plate width or length. The
# 2026-10-30 live run submitted a 1 mm rim edge as a "shortened" boundary and
# Creo refused the attachment (PRO_TK_BAD_CONTEXT, -8) -- a driver selection
# defect, never a modelling failure.
THICKNESS_SCALE_FACTOR = 2.0


def is_thickness_scale_span(span_mm: float, thickness_mm: float) -> bool:
    """True when an edge span is comparable to the sheet thickness (a rim edge)."""
    return span_mm <= THICKNESS_SCALE_FACTOR * thickness_mm + TOL_MM


# side -> (coordinate axis of the side plane, axis the edge runs along)
SIDE_AXES = {"+x": (0, 1), "-x": (0, 1), "+y": (1, 0), "-y": (1, 0)}
# side -> the two plan corners it ends at, as (x sign, y sign)
SIDE_CORNERS = {
    "+x": {("+", "+"), ("+", "-")},
    "-x": {("-", "+"), ("-", "-")},
    "+y": {("+", "+"), ("-", "+")},
    "-y": {("+", "-"), ("-", "-")},
}
FLANGE_SEQUENCE = (("+x", "f_px"), ("-x", "f_nx"), ("-y", "f_ny"), ("+y", "f_py"))


class EdgeSelectionError(ValueError):
    """A reference is absent, moved, ambiguous or short of the plate boundary."""


# --- fixture: an inspection-shaped box ------------------------------------


FACE_IDS = {"-x": 301, "+x": 302, "-y": 303, "+y": 304, "bottom": 305, "top": 306}
EDGE_IDS = (211, 218, 224, 231, 236, 240, 247, 253, 259, 262, 268, 274)


def box_inspection(bounds: tuple = PLATE_BOUNDS) -> dict:
    """A plate inspection with the fields the live selector reads.

    ProEdgeVisit only fills start/end when ProLinedataGet succeeds, so a payload
    without endpoints is not a straight edge. Bodies carry the active state and
    the outline bbox the live inspection returns.
    """
    lo = tuple(float(v) for v in bounds[0])
    hi = tuple(float(v) for v in bounds[1])
    edges: list[tuple] = []
    for face, z in (("bottom", lo[2]), ("top", hi[2])):
        edges.append(((lo[0], lo[1], z), (hi[0], lo[1], z), "-y", face))
        edges.append(((lo[0], hi[1], z), (hi[0], hi[1], z), "+y", face))
        edges.append(((lo[0], lo[1], z), (lo[0], hi[1], z), "-x", face))
        edges.append(((hi[0], lo[1], z), (hi[0], hi[1], z), "+x", face))
    for x, y in ((lo[0], lo[1]), (lo[0], hi[1]), (hi[0], lo[1]), (hi[0], hi[1])):
        edges.append(((x, y, lo[2]), (x, y, hi[2]), None, None))

    payload = []
    for edge_id, (start, end, side, face) in zip(EDGE_IDS, edges):
        item = {"id": edge_id, "start": list(start), "end": list(end)}
        if side is None:
            item["adjacent_surfaces"] = [
                FACE_IDS["+x"] if start[0] == hi[0] else FACE_IDS["-x"],
                FACE_IDS["+y"] if start[1] == hi[1] else FACE_IDS["-y"],
            ]
        else:
            item["adjacent_surfaces"] = [FACE_IDS[side], FACE_IDS[face]]
        payload.append(item)

    surfaces = [
        {
            "id": FACE_IDS["-x"],
            "normal": [-1.0, 0.0, 0.0],
            "bbox": [list(lo), [lo[0], hi[1], hi[2]]],
        },
        {
            "id": FACE_IDS["+x"],
            "normal": [1.0, 0.0, 0.0],
            "bbox": [[hi[0], lo[1], lo[2]], list(hi)],
        },
        {
            "id": FACE_IDS["-y"],
            "normal": [0.0, -1.0, 0.0],
            "bbox": [list(lo), [hi[0], lo[1], hi[2]]],
        },
        {
            "id": FACE_IDS["+y"],
            "normal": [0.0, 1.0, 0.0],
            "bbox": [[lo[0], hi[1], lo[2]], list(hi)],
        },
        {
            "id": FACE_IDS["bottom"],
            "normal": [0.0, 0.0, -1.0],
            "bbox": [list(lo), [hi[0], hi[1], lo[2]]],
        },
        {
            "id": FACE_IDS["top"],
            "normal": [0.0, 0.0, 1.0],
            "bbox": [[lo[0], lo[1], hi[2]], list(hi)],
        },
    ]
    return {
        "model_id": "t05_fixture",
        "bodies": [
            {"id": 1, "state": 2, "has_geometry": True, "bbox": [list(lo), list(hi)]},
        ],
        "surfaces": surfaces,
        "edges": payload,
        "counts": {"bodies": 1, "surfaces": len(surfaces), "edges": len(payload)},
    }


# --- the measured post-flange topology (2026-10-30 live px_then_ny) ---------

# What plate_bounds must be (the plate slab: top stays z=0.5) versus what the
# buggy caller passed (the whole body bbox: the +x wall lifts the top to
# z=79.5). Classifying "top" against the body bbox is the shared root cause of
# both live selection failures.
POST_FLANGE_PLATE_BOUNDS = ((0.0, -232.0, -0.5), (185.0, 0.0, 0.5))
POST_FLANGE_BODY_BOUNDS = ((0.0, -232.0, -0.5), (185.0, 0.0, 79.5))


def post_flange_inspection() -> dict:
    """The measured px_then_ny topology after the +x wall (2026-10-30 live).

    The plate's -y top edge lost the bend width (radius + thickness = 3.54) at
    the +x corner and spans 181.46 mm; the -x top edge is untouched (232 mm).
    The wall contributes its end rim edge (id 211: 1 mm at y=-232, z=79.5) --
    the edge the buggy selection submitted and Creo refused with
    PRO_TK_BAD_CONTEXT (-8). Edge ids and adjacent surfaces echo the report.
    """
    edges = [
        {
            "id": 211,
            "start": [185.0, -232.0, 79.5],
            "end": [184.0, -232.0, 79.5],
            "adjacent_surfaces": [214, 213],
        },
        {
            "id": 103,
            "start": [0.0, -232.0, 0.5],
            "end": [181.46, -232.0, 0.5],
            "adjacent_surfaces": [303, 306],
        },
        {
            "id": 101,
            "start": [0.0, -232.0, -0.5],
            "end": [185.0, -232.0, -0.5],
            "adjacent_surfaces": [303, 305],
        },
        {
            "id": 106,
            "start": [0.0, -232.0, 0.5],
            "end": [0.0, 0.0, 0.5],
            "adjacent_surfaces": [301, 306],
        },
        {
            "id": 108,
            "start": [0.0, -232.0, -0.5],
            "end": [0.0, 0.0, -0.5],
            "adjacent_surfaces": [301, 305],
        },
        {
            "id": 219,
            "start": [185.0, 0.0, 79.5],
            "end": [185.0, -232.0, 79.5],
            "adjacent_surfaces": [302, 214],
        },
        {
            "id": 222,
            "start": [0.0, -232.0, -0.5],
            "end": [0.0, -232.0, 0.5],
            "adjacent_surfaces": [301, 303],
        },
    ]
    return {
        "model_id": "n05_post_flange",
        "bodies": [
            {
                "id": 1,
                "state": 2,
                "has_geometry": True,
                "bbox": [
                    list(POST_FLANGE_BODY_BOUNDS[0]),
                    list(POST_FLANGE_BODY_BOUNDS[1]),
                ],
            }
        ],
        "surfaces": [],
        "edges": edges,
        "counts": {"bodies": 1, "surfaces": 0, "edges": len(edges)},
    }


# --- geometric edge selection (no id from the report) ----------------------


def active_bbox(inspection: dict) -> tuple:
    for body in inspection.get("bodies", []):
        if body.get("has_geometry") and body.get("bbox"):
            low, high = body["bbox"]
            return tuple(float(v) for v in low), tuple(float(v) for v in high)
    raise EdgeSelectionError("inspection has no active body with geometry")


def thinnest_axis(bounds: tuple) -> int:
    spans = [bounds[1][i] - bounds[0][i] for i in range(3)]
    return min(range(3), key=lambda i: spans[i])


def _edge_face(edge: dict, plate_bounds: tuple, normal: int) -> str | None:
    middle = (edge["start"][normal] + edge["end"][normal]) / 2.0
    if abs(middle - plate_bounds[1][normal]) <= TOL_MM:
        return "top"
    if abs(middle - plate_bounds[0][normal]) <= TOL_MM:
        return "bottom"
    return None


def _record(edge: dict, side: str, face: str, run: int, expected: float) -> dict:
    start, end = list(edge["start"]), list(edge["end"])
    span = abs(end[run] - start[run])
    return {
        "edge": {"kind": "edge", "id": edge["id"]},
        "geometry": {
            "id": edge["id"],
            "side": side,
            "face": face,
            "start": start,
            "end": end,
            "span_mm": round(span, 6),
            "expected_span_mm": round(expected, 6),
            "shortfall_mm": round(max(0.0, expected - span), 6),
            "adjacent_surfaces": list(edge.get("adjacent_surfaces", [])),
        },
    }


def select_wall_edge(
    inspection: dict,
    plate_bounds: tuple,
    side: str,
    face: str | None = None,
    allow_shortened: bool = False,
) -> dict:
    """Select the plate boundary edge on one side from geometry alone.

    face="top"/"bottom" names which of the two parallel 1 mm-apart boundaries is
    meant. Omitting it is an error, not a silent pick: the choice changes which
    face the bend is built from, and the reported run never recorded it.

    plate_bounds must be the base plate slab (the bbox captured from the base
    snapshot before any flange), never the whole body: after a flange the body
    top is the wall top, and classifying "top" against it misroutes every later
    side. Thickness-scale rim edges are never candidates, and a shortened pick
    is bounded by what adjacent bends can consume -- anything else fails here
    as a driver selection error instead of reaching Creo as a bogus edge.
    """
    if side not in SIDE_AXES:
        raise EdgeSelectionError(f"unknown side {side!r}; use one of {sorted(SIDE_AXES)}")
    if face not in (None, "top", "bottom"):
        raise EdgeSelectionError(f"unknown face {face!r}; use top, bottom or None")
    normal = thinnest_axis(plate_bounds)
    axis, run = SIDE_AXES[side]
    coordinate = plate_bounds[1][axis] if side[0] == "+" else plate_bounds[0][axis]
    expected = plate_bounds[1][run] - plate_bounds[0][run]
    thickness = plate_bounds[1][normal] - plate_bounds[0][normal]

    on_plane = []
    skipped = []
    for edge in inspection.get("edges", []):
        start, end = edge.get("start"), edge.get("end")
        if start is None or end is None:
            skipped.append({"id": edge.get("id"), "reason": "no straight-line endpoints"})
            continue
        if abs(start[axis] - coordinate) > TOL_MM or abs(end[axis] - coordinate) > TOL_MM:
            continue
        if abs(start[normal] - end[normal]) > TOL_MM:
            skipped.append({"id": edge["id"], "reason": "corner edge along the plate normal"})
            continue
        if is_thickness_scale_span(abs(end[run] - start[run]), thickness):
            skipped.append({"id": edge["id"], "reason": "thickness-scale rim edge"})
            continue
        on_plane.append(edge)

    if not on_plane:
        raise EdgeSelectionError(
            f"side {side} has no boundary edge on coordinate {coordinate} "
            f"({len(skipped)} edge(s) skipped: {skipped})"
        )

    if face is None:
        if len(on_plane) > 1:
            faces = sorted({_edge_face(edge, plate_bounds, normal) or "other" for edge in on_plane})
            raise EdgeSelectionError(
                f"side {side} has {len(on_plane)} parallel boundary edges "
                f"{plate_bounds[1][normal] - plate_bounds[0][normal]:.3f} mm apart "
                f"({', '.join(faces)}); pass face='top' or face='bottom'"
            )
        face = _edge_face(on_plane[0], plate_bounds, normal)

    candidates = [edge for edge in on_plane if _edge_face(edge, plate_bounds, normal) == face]
    if not candidates:
        raise EdgeSelectionError(
            f"side {side} has no {face} boundary edge ({len(skipped)} edge(s) skipped: {skipped})"
        )

    full = [
        edge
        for edge in candidates
        if abs(abs(edge["end"][run] - edge["start"][run]) - expected) <= SPAN_TOL_MM
    ]
    if len(full) == 1:
        return _record(full[0], side, face, run, expected)
    if len(full) > 1:
        raise EdgeSelectionError(
            f"side {side} face {face} is ambiguous: " + ", ".join(str(edge["id"]) for edge in full)
        )

    measured = sorted((abs(edge["end"][run] - edge["start"][run]), edge) for edge in candidates)
    longest_span, longest = measured[-1]
    shortfall = expected - longest_span
    if allow_shortened:
        # Bounded shortfall: each adjacent bend consumes at most radius +
        # thickness of this boundary at one end, both ends at most twice that
        # (the round-six shape: 185 - 2 x 3.54 = 177.92). Anything shorter is
        # not the plate boundary; refuse it as a driver selection failure.
        max_shortfall = 2.0 * (FLANGE_RADIUS_MM + thickness)
        if shortfall > max_shortfall + SPAN_TOL_MM:
            raise EdgeSelectionError(
                f"side {side} face {face}: longest boundary edge id {longest['id']} spans "
                f"{longest_span:.3f} mm, short by {shortfall:.3f} mm, beyond the bounded "
                f"allowance {max_shortfall:.3f} mm (two bend ends of radius "
                f"{FLANGE_RADIUS_MM} mm + thickness {thickness:.3f} mm); driver selection "
                "failure, not a Creo failure"
            )
        return _record(longest, side, face, run, expected)
    raise EdgeSelectionError(
        f"side {side} face {face} has no full-length edge: nearest id {longest['id']} spans "
        f"{longest_span:.3f} mm instead of {expected:.3f} mm (short by {shortfall:.3f} mm); "
        "an earlier flange consumed that corner"
    )


def assert_edge_current(inspection: dict, reference: dict) -> dict:
    """Refuse a stale reference: absent id, or endpoints that moved."""
    edge_id = reference["geometry"]["id"]
    for edge in inspection.get("edges", []):
        if edge.get("id") != edge_id:
            continue
        start, end = edge.get("start"), edge.get("end")
        if start is None or end is None:
            raise EdgeSelectionError(f"edge {edge_id} is no longer a straight edge")
        for name, current in (("start", start), ("end", end)):
            saved = reference["geometry"][name]
            if any(abs(a - b) > TOL_MM for a, b in zip(current, saved)):
                raise EdgeSelectionError(
                    f"edge {edge_id} {name} moved from {saved} to {current}; refresh the id"
                )
        return {"id": edge_id, "current": True, "start": list(start), "end": list(end)}
    raise EdgeSelectionError(
        f"edge {edge_id} is not in the current inspection; refresh the id before submitting"
    )


def _perpendicular_sides(side: str) -> list[str]:
    return [other for other in SIDE_AXES if SIDE_AXES[other][0] != SIDE_AXES[side][0]]


def refresh_after_flange(
    inspection: dict,
    plate_bounds: tuple,
    reference: dict,
    side: str,
    step: int = 1,
    thickness_inside: bool = True,
) -> dict:
    """Worst-case refresh: consumed edge gone, neighbours shortened, ids renumbered.

    A flange consumes the edge it was built on. The two perpendicular plate
    boundaries lose the wall thickness at each shared corner (the bend radius
    removes more, so this is a lower bound). Creo may keep ids stable; the
    fixture assumes the worst case so the procedure never depends on it.
    """
    updated = copy.deepcopy(inspection)
    consumed = reference["geometry"]["id"]
    updated["edges"] = [edge for edge in updated["edges"] if edge["id"] != consumed]
    normal = thinnest_axis(plate_bounds)
    thickness = plate_bounds[1][normal] - plate_bounds[0][normal]
    axis = SIDE_AXES[side][0]
    sign = 1 if side[0] == "+" else -1
    coordinate = plate_bounds[1][axis] if sign > 0 else plate_bounds[0][axis]

    if thickness_inside:
        for other in _perpendicular_sides(side):
            other_axis = SIDE_AXES[other][0]
            other_coordinate = (
                plate_bounds[1][other_axis] if other[0] == "+" else plate_bounds[0][other_axis]
            )
            for edge in updated["edges"]:
                points = (edge["start"], edge["end"])
                if any(abs(point[other_axis] - other_coordinate) > TOL_MM for point in points):
                    continue
                if abs(points[0][normal] - points[1][normal]) > TOL_MM:
                    continue
                for point in points:
                    if abs(point[axis] - coordinate) <= TOL_MM:
                        point[axis] = coordinate - sign * thickness

    # The bend adds two wall end edges; the consumed boundary is gone.
    low, high = (list(plate_bounds[0]), list(plate_bounds[1]))
    wall_plane = coordinate - sign * thickness if thickness_inside else coordinate
    top = high[normal] + FLANGE_HEIGHT_MM
    low[normal] = high[normal]
    high[normal] = top
    if axis == 0:
        low[0] = high[0] = wall_plane
    else:
        low[1] = high[1] = wall_plane
    updated["edges"].append({"id": -1, "start": list(low), "end": list([high[0], low[1], high[2]])})
    updated["edges"].append({"id": -2, "start": list([low[0], high[1], low[2]]), "end": list(high)})

    for index, edge in enumerate(updated["edges"]):
        edge["id"] = 1000 + step * 100 + index * 7

    body = next(body for body in updated["bodies"] if body.get("has_geometry"))
    body["bbox"] = [list(plate_bounds[0]), [plate_bounds[1][0], plate_bounds[1][1], top]]
    updated["counts"] = {
        "bodies": len(updated["bodies"]),
        "surfaces": len(updated["surfaces"]),
        "edges": len(updated["edges"]),
    }
    return updated


# --- plan fixtures --------------------------------------------------------


def wall_sketch() -> dict:
    return {
        "op": "sketch",
        "label": "wall_sketch",
        # DEV-051 T05/T11: the sketch plane decides where the sheet thickness lives.
        # An XZ sketch keeps the 1 mm thin width in Z and the extrusion in Y, so
        # sheetmetal_wall(depth=232, thickness=1) gives the 185 x 232 x 1 plate whose
        # 185 x 232 faces are the sheetmetal wall faces.
        "plane": "XZ",
        "entities": [
            {
                "type": "line",
                "name": "wall_line",
                "start": [0.0, 0.0],
                "end": [PLATE_LENGTH_MM, 0.0],
            }
        ],
    }


def wall_base_op() -> dict:
    # DEV-051 T05/T11: "thickness" is the sheet metal thickness written as
    # PRO_E_STD_SMT_THICKNESS and "depth" is the extrusion, so a 185 x 232 x 1 plate is
    # sheetmetal_wall(depth=232, thickness=1). The pre-fix fixture passed
    # depth=1/thickness=232: volume and bbox still matched 185 x 232 x 1, but Creo typed
    # the part as a 232 mm thick sheet (green/white faces 185 x 1 at y=-116/+116, the four
    # 185 x 232 faces as side surfaces), so every flange edge was a rim edge and
    # ProSmtedgeContourGet answered PRO_TK_BAD_CONTEXT (-8).
    return {
        "op": "sheetmetal_wall",
        "label": "base_wall",
        "sketch": "wall_sketch",
        "depth": PLATE_WIDTH_MM,
        "thickness": PLATE_THICKNESS_MM,
        "direction": "positive",
    }


def flange_op(side: str, label: str, reference: dict, flip: bool = False) -> dict:
    return {
        "op": "sheetmetal_flange",
        "label": label,
        "edge": dict(reference["edge"]),
        "height": FLANGE_HEIGHT_MM,
        "angle": FLANGE_ANGLE_DEG,
        "radius": FLANGE_RADIUS_MM,
        "flip": flip,
        "y_factor": FLANGE_Y_FACTOR,
    }


def four_wall_plan(inspection: dict, plate_bounds: tuple = PLATE_BOUNDS) -> tuple:
    """The reported single plan: four edges captured once, all top boundaries."""
    operations = [wall_sketch(), wall_base_op()]
    references = []
    for side, label in FLANGE_SEQUENCE:
        reference = select_wall_edge(inspection, plate_bounds, side, face="top")
        references.append(reference)
        operations.append(flange_op(side, label, reference))
    return operations, references


def sequential_steps(inspection: dict, plate_bounds: tuple = PLATE_BOUNDS) -> list[dict]:
    """One flange per job, re-inspecting after each; later edges may be short."""
    steps = []
    current = inspection
    for index, (side, label) in enumerate(FLANGE_SEQUENCE):
        reference = select_wall_edge(
            current, plate_bounds, side, face="top", allow_shortened=index >= 2
        )
        steps.append(
            {
                "index": index + 2,
                "side": side,
                "label": label,
                "reference": reference,
                "operations": [flange_op(side, label, reference)],
            }
        )
        current = refresh_after_flange(current, plate_bounds, reference, side, step=index + 1)
    return steps


# --- independent oracles and classifications ------------------------------


def wall_volume_mm3(span_mm: float) -> float:
    """Constant-thickness wall: developed length x height x thickness."""
    return span_mm * FLANGE_HEIGHT_MM * PLATE_THICKNESS_MM


def shared_corners(previous_sides: list[str], side: str) -> int:
    return sum(len(SIDE_CORNERS[side] & SIDE_CORNERS[other]) for other in previous_sides)


def corner_overlap_volume_mm3(corners: int) -> float:
    """Lower bound per shared corner: (h - R) x t x t.

    The bend arc occupies R of the wall length, so the straight wall run that
    overlaps the perpendicular wall is at least h - R. Bend radii make the real
    overlap smaller, never larger.
    """
    return corners * max(0.0, FLANGE_HEIGHT_MM - FLANGE_RADIUS_MM) * PLATE_THICKNESS_MM**2


def predicted_bbox(side: str, material_side: str) -> tuple:
    low, high = (list(PLATE_BOUNDS[0]), list(PLATE_BOUNDS[1]))
    high[2] = high[2] + FLANGE_HEIGHT_MM
    axis = SIDE_AXES[side][0]
    if material_side == "outside":
        if side[0] == "+":
            high[axis] += PLATE_THICKNESS_MM
        else:
            low[axis] -= PLATE_THICKNESS_MM
    return tuple(low), tuple(high)


def classify_material_side(bbox: tuple, side: str) -> str:
    """Which side of the plate footprint the wall material sits on."""
    axis = SIDE_AXES[side][0]
    if side[0] == "+":
        offset = bbox[1][axis] - PLATE_BOUNDS[1][axis]
    else:
        offset = PLATE_BOUNDS[0][axis] - bbox[0][axis]
    return "outside" if offset >= PLATE_THICKNESS_MM / 2.0 else "inside"


def classify_direction(bbox: tuple) -> str:
    """Where the flange went: up, down, flat in-plane or not measurable."""
    low, high = PLATE_BOUNDS
    if bbox[1][2] >= high[2] + FLANGE_HEIGHT_MM / 2.0:
        return "up"
    if bbox[0][2] <= low[2] - FLANGE_HEIGHT_MM / 2.0:
        return "down"
    growth = max(bbox[1][0] - high[0], bbox[1][1] - high[1])
    if growth >= FLANGE_HEIGHT_MM / 2.0:
        return "in_plane"
    return "ambiguous"


# --- judgement record, hypotheses, decision table -------------------------


JUDGEMENT_FIELDS = (
    "label",
    "index",
    "side",
    "flip_input",
    "height_input",
    "radius_input",
    "angle_input",
    "y_factor_input",
    "edge_before_submit",
    "edge_span_mm",
    "edge_shortfall_mm",
    "parent_body_before",
    "parent_body_after",
    "new_body",
    "body_bbox_before",
    "body_bbox_after",
    "direction",
    "material_side",
    "added_volume_mm3",
    "feature_health",
    "native_tree",
    "execution_status",
    "effect_status",
    "toolkit_code",
    "last_feature_errors",
    "revision_before",
    "revision_after",
    "saved_file_reloaded_and_verified",
    "rolled_back_rebuild_required",
)


def judgement_template(label: str, index: int, side: str, flip: bool = False) -> dict:
    """One flange's record: request echoes filled, measurements left unset."""
    record = {name: None for name in JUDGEMENT_FIELDS}
    record.update(
        {
            "label": label,
            "index": index,
            "side": side,
            "flip_input": flip,
            "height_input": FLANGE_HEIGHT_MM,
            "radius_input": FLANGE_RADIUS_MM,
            "angle_input": FLANGE_ANGLE_DEG,
            "y_factor_input": FLANGE_Y_FACTOR,
        }
    )
    return record


HYPOTHESES = (
    {
        "id": "H1_edge_reference_drift",
        "statement": (
            "the four edge ids were captured before any flange existed; earlier flanges "
            "consume their edge and shorten the two perpendicular boundaries, so the third "
            "reference no longer describes the intended full-length edge"
        ),
        "probe": (
            "re-inspect before each flange, compare id/endpoints/span, and submit one flange "
            "per job; also run the untouched single plan for the same fingerprint"
        ),
        "expected_if_true": (
            "before flange 3 the id is gone or its span is shorter by >= t at each shared "
            "corner; the refreshed submission either fails differently or succeeds with a "
            "shorter wall"
        ),
        "refutation": "the third edge is unchanged (same id, endpoints, span) before flange 3",
        "judgement_fields": (
            "edge_before_submit",
            "edge_span_mm",
            "edge_shortfall_mm",
            "execution_status",
            "toolkit_code",
        ),
        "status": "unresolved_offline",
    },
    {
        "id": "H2_corner_material_overlap",
        "statement": (
            "with the wall material on the inside of the plate footprint the third flange "
            "overlaps both existing perpendicular walls; sheetmetal walls cannot merge, so "
            "the corner is solid interference rather than a bend"
        ),
        "probe": (
            "read the material side from the bbox after flanges 1-2, then try the third flange "
            "on the shortened edge and on an edge trimmed 20 mm short of both corners"
        ),
        "expected_if_true": (
            "inside material: third flange fails, trimmed or outward variants succeed; "
            "outside material: the third flange succeeds with no overlap"
        ),
        "refutation": (
            "the third flange fails identically on a shortened/trimmed edge with zero "
            "predicted overlap"
        ),
        "judgement_fields": (
            "material_side",
            "body_bbox_after",
            "added_volume_mm3",
            "execution_status",
            "toolkit_code",
        ),
        "status": "unresolved_offline",
    },
    {
        "id": "H3_trajectory_normal_flip",
        "statement": (
            "RESOLVED 2026-10-29: `flip` used to write PRO_E_SMT_FLANGE_TRAJ_CRV_NORM and the "
            "one-variable live pair (flip=false -> 1, flip=true -> -1) produced identical "
            "bbox, identical volume and the same side, so that element is not the switch. "
            "PRO_E_SMT_FLANGE_SEC_FLIP is: top edge FALSE -> down / TRUE -> up, bottom edge "
            "FALSE -> up / TRUE -> down, i.e. the side is relative to the attachment face"
        ),
        "probe": "same edge, same h/R/Y, only flip toggled; measure bbox side and direction",
        "expected_if_true": (
            "the two runs sit on opposite sides of the plate, one flange height apart"
        ),
        "refutation": (
            "flip=true and flip=false give the same bbox side on the same edge - observed "
            "before the fix, which is why the switch moved to the section side element"
        ),
        "judgement_fields": ("flip_input", "material_side", "body_bbox_after", "direction"),
        "status": "resolved_by_live_matrix_2026-10-29",
    },
    {
        "id": "H4_parent_body_implicit",
        "statement": (
            "the flange tree sets no PRO_E_BODY element, so the wall attaches to the model's "
            "active body implicitly; the reported bodies=2 makes the body list unusable as "
            "evidence on its own"
        ),
        "probe": "record bodies (id/state/has_geometry) before and after each flange",
        "expected_if_true": (
            "a body is created or the active body id changes across the flange, or the "
            "feature reports a body-related element error"
        ),
        "refutation": "one unchanged active body and no body element error in last_feature_errors",
        "judgement_fields": (
            "parent_body_before",
            "parent_body_after",
            "new_body",
            "feature_health",
            "native_tree",
        ),
        "status": "unresolved_offline",
    },
    {
        "id": "H5_thick_plate_first_flange",
        "statement": (
            "the thick-base first flange is a separate branch: T03 has not yet confirmed the "
            "real bbox placement or axis signs of depth=232/thickness=1"
        ),
        "probe": "after the T03 live contract, build the thick base and run one flange",
        "expected_if_true": "not applicable: this branch carries no prediction yet",
        "refutation": "not applicable",
        "judgement_fields": (
            "edge_before_submit",
            "body_bbox_before",
            "direction",
            "material_side",
            "added_volume_mm3",
        ),
        "status": "pending_t03_live_contract",
    },
)

DECISION_TABLE = (
    {
        "observation": "third edge absent or shortened before flange 3",
        "conclusion": "H1 supported: the pre-plan capture was stale; per-flange refresh is required",
    },
    {
        "observation": "third flange fails on a full edge but succeeds 20 mm short of both corners",
        "conclusion": "H2 supported: corner interference, not a reference defect; needs T11 relief",
    },
    {
        "observation": "third flange fails identically on a trimmed edge",
        "conclusion": "H2 refuted; keep H1/H3/H4 open and re-read the element errors",
    },
    {
        "observation": "flip toggling moves the wall to the other side of the plate",
        "conclusion": "H3 supported for that edge; material side must be derived per edge",
    },
    {
        "observation": "a body appears or the active body changes across a flange",
        "conclusion": "H4 supported: body handling must be fixed before wall placement",
    },
    {
        "observation": "all four walls succeed and each bbox grows on the documented side",
        "conclusion": "four-wall capability still needs unbend/bend-back, edit, reload and rollback",
    },
)

THICK_PLATE_BRANCH = {
    "base": "sheetmetal_wall(depth=232, thickness=1) -> 185 x 1 x 232 (T03 contract)",
    "status": "pending_t03_live_contract",
    "first_flange": {
        "height": FLANGE_HEIGHT_MM,
        "radius": FLANGE_RADIUS_MM,
        "y_factor": FLANGE_Y_FACTOR,
        "expected_added_volume_mm3": 14_800.0,
        "volume_basis": "185 mm top edge x 80 mm x 1 mm, conditional on that edge",
    },
    "unknown": (
        "bbox placement and axis signs",
        "which of the two 1 mm boundaries the flange uses",
        "material side and bend direction",
    ),
    "note": (
        "the volume is a geometry oracle; direction/material side stay unknown until the "
        "T03 live contract fixes the real bbox"
    ),
}

LIVE_REFUSAL = (
    "T05 live diagnosis is a separate integration step on the single shared dev service "
    "(MCP_CREO_MechDog_dev, E:/Projects/MCP_CREO_MechDog). This driver runs offline checks "
    "only: it never instantiates an MCP client, never connects to Creo and never retries a "
    "job. Use --live --confirm-session-usable only inside that assigned integration step."
)


def archived_reports_containing(token: str) -> list[str]:
    root = REPO_ROOT / "docs" / "validation"
    return [
        str(path.relative_to(REPO_ROOT))
        for path in sorted(root.rglob("*.md"))
        if token.encode("ascii") in path.read_bytes()
    ]


class EdgeSelectionTest(unittest.TestCase):
    def test_plate_oracle_matches_confirmed_thin_plate(self) -> None:
        self.assertAlmostEqual(
            PLATE_LENGTH_MM * PLATE_WIDTH_MM * PLATE_THICKNESS_MM, PLATE_VOLUME_MM3
        )
        low, high = active_bbox(box_inspection())
        self.assertEqual(high[0] - low[0], PLATE_LENGTH_MM)
        self.assertEqual(high[1] - low[1], PLATE_WIDTH_MM)
        self.assertEqual(high[2] - low[2], PLATE_THICKNESS_MM)
        self.assertEqual(thinnest_axis(PLATE_BOUNDS), 2)

    def test_unqualified_side_is_refused_as_ambiguous(self) -> None:
        for side in SIDE_AXES:
            with self.assertRaises(EdgeSelectionError) as ctx:
                select_wall_edge(box_inspection(), PLATE_BOUNDS, side)
            self.assertIn("1.000 mm apart", str(ctx.exception), side)
            self.assertIn("face='top'", str(ctx.exception), side)

    def test_face_selects_the_plate_boundary_plane(self) -> None:
        inspection = box_inspection()
        for side in SIDE_AXES:
            top = select_wall_edge(inspection, PLATE_BOUNDS, side, face="top")
            bottom = select_wall_edge(inspection, PLATE_BOUNDS, side, face="bottom")
            self.assertAlmostEqual(top["geometry"]["start"][2], PLATE_THICKNESS_MM)
            self.assertAlmostEqual(bottom["geometry"]["start"][2], 0.0)
            self.assertNotEqual(top["edge"]["id"], bottom["edge"]["id"])
            self.assertEqual(top["geometry"]["face"], "top")

    def test_selected_edge_spans_the_plate_and_is_not_a_corner_edge(self) -> None:
        inspection = box_inspection()
        for side, (axis, run) in SIDE_AXES.items():
            reference = select_wall_edge(inspection, PLATE_BOUNDS, side, face="top")
            geometry = reference["geometry"]
            self.assertAlmostEqual(geometry["start"][axis], geometry["end"][axis])
            self.assertAlmostEqual(geometry["span_mm"], PLATE_BOUNDS[1][run])
            self.assertAlmostEqual(geometry["start"][2], geometry["end"][2])
            self.assertEqual(geometry["shortfall_mm"], 0.0)

    def test_report_edge_ids_are_never_used(self) -> None:
        inspection = box_inspection()
        catalog = {edge["id"] for edge in inspection["edges"]}
        self.assertFalse(catalog & set(REPORT_EDGE_IDS))
        for side in SIDE_AXES:
            reference = select_wall_edge(inspection, PLATE_BOUNDS, side, face="top")
            self.assertNotIn(reference["edge"]["id"], REPORT_EDGE_IDS)

    def test_selection_follows_geometry_under_permuted_ids(self) -> None:
        inspection = box_inspection()
        baseline = {
            side: select_wall_edge(inspection, PLATE_BOUNDS, side, face="top")["geometry"]
            for side in SIDE_AXES
        }
        shuffled = copy.deepcopy(inspection)
        remap = {}
        for index, edge in enumerate(shuffled["edges"]):
            remap[edge["id"]] = 700 + index * 13
            edge["id"] = remap[edge["id"]]
        for side, geometry in baseline.items():
            moved = select_wall_edge(shuffled, PLATE_BOUNDS, side, face="top")["geometry"]
            self.assertEqual(moved["start"], geometry["start"])
            self.assertEqual(moved["end"], geometry["end"])
            self.assertEqual(moved["id"], remap[geometry["id"]])

    def test_edges_without_straight_line_endpoints_are_skipped(self) -> None:
        inspection = box_inspection()
        inspection["edges"].append({"id": 999, "type": 3, "adjacent_surfaces": [302, 306]})
        reference = select_wall_edge(inspection, PLATE_BOUNDS, "+x", face="top")
        self.assertEqual(reference["geometry"]["span_mm"], PLATE_WIDTH_MM)
        self.assertNotEqual(reference["edge"]["id"], 999)

    def test_unknown_side_and_face_are_rejected(self) -> None:
        with self.assertRaises(EdgeSelectionError):
            select_wall_edge(box_inspection(), PLATE_BOUNDS, "+z", face="top")
        with self.assertRaises(EdgeSelectionError):
            select_wall_edge(box_inspection(), PLATE_BOUNDS, "+x", face="middle")


class PostFlangeSelectionTest(unittest.TestCase):
    """The 2026-10-30 live first run: both selection failure modes, locked offline."""

    def test_minus_y_selects_the_shortened_plate_edge_not_the_rim_edge(self):
        reference = select_wall_edge(
            post_flange_inspection(),
            POST_FLANGE_PLATE_BOUNDS,
            "-y",
            face="top",
            allow_shortened=True,
        )
        geometry = reference["geometry"]
        self.assertNotEqual(reference["edge"]["id"], 211)
        self.assertAlmostEqual(geometry["span_mm"], 181.46, places=6)
        self.assertAlmostEqual(geometry["start"][2], 0.5, places=6)
        self.assertEqual(geometry["face"], "top")

    def test_body_bbox_cannot_trick_the_selector_into_the_rim_edge(self):
        # The live defect: classifying "top" against the post-flange body bbox
        # (wall top at z=79.5) left the rim edge as the only candidate. It must
        # fail the driver, never pick the rim.
        with self.assertRaises(EdgeSelectionError) as ctx:
            select_wall_edge(
                post_flange_inspection(),
                POST_FLANGE_BODY_BOUNDS,
                "-y",
                face="top",
                allow_shortened=True,
            )
        self.assertIn("no top boundary edge", str(ctx.exception))

    def test_thickness_scale_edges_are_never_candidates(self):
        inspection = post_flange_inspection()
        inspection["edges"] = [edge for edge in inspection["edges"] if edge["id"] != 103]
        with self.assertRaises(EdgeSelectionError) as ctx:
            select_wall_edge(
                inspection, POST_FLANGE_PLATE_BOUNDS, "-y", face="top", allow_shortened=True
            )
        self.assertIn("rim", str(ctx.exception))

    def test_minus_x_selection_is_deterministic_after_the_flange(self):
        inspection = post_flange_inspection()
        first = select_wall_edge(
            inspection, POST_FLANGE_PLATE_BOUNDS, "-x", face="top", allow_shortened=True
        )
        second = select_wall_edge(
            inspection, POST_FLANGE_PLATE_BOUNDS, "-x", face="top", allow_shortened=True
        )
        self.assertEqual(first["edge"]["id"], second["edge"]["id"])
        self.assertAlmostEqual(first["geometry"]["span_mm"], 232.0, places=6)
        self.assertAlmostEqual(first["geometry"]["start"][2], 0.5, places=6)
        self.assertNotEqual(first["edge"]["id"], 211)

    def test_minus_x_with_body_bbox_fails_as_a_driver_error(self):
        # The exact live stop ("side -x has no top boundary edge"): with the
        # plate bounds it selects deterministically; with the body bbox it is
        # a bounded driver failure, never a silent pick.
        with self.assertRaises(EdgeSelectionError):
            select_wall_edge(post_flange_inspection(), POST_FLANGE_BODY_BOUNDS, "-x", face="top")


class SequentialRefreshTest(unittest.TestCase):
    def test_flanged_edge_disappears_after_the_flange(self) -> None:
        inspection = box_inspection()
        reference = select_wall_edge(inspection, PLATE_BOUNDS, "+x", face="top")
        refreshed = refresh_after_flange(inspection, PLATE_BOUNDS, reference, "+x")
        self.assertNotIn(reference["edge"]["id"], {edge["id"] for edge in refreshed["edges"]})
        with self.assertRaises(EdgeSelectionError) as ctx:
            assert_edge_current(refreshed, reference)
        self.assertIn("not in the current inspection", str(ctx.exception))

    def test_reference_with_moved_endpoints_is_rejected(self) -> None:
        inspection = box_inspection()
        reference = select_wall_edge(inspection, PLATE_BOUNDS, "+y", face="top")
        assert_edge_current(inspection, reference)
        moved = copy.deepcopy(inspection)
        for edge in moved["edges"]:
            if edge["id"] == reference["edge"]["id"]:
                edge["end"][0] = PLATE_LENGTH_MM - 0.5
                break
        with self.assertRaises(EdgeSelectionError) as ctx:
            assert_edge_current(moved, reference)
        self.assertIn("refresh the id", str(ctx.exception))

    def test_perpendicular_edges_shorten_at_both_shared_corners(self) -> None:
        inspection = box_inspection()
        steps = sequential_steps(inspection)
        spans = [step["reference"]["geometry"]["span_mm"] for step in steps]
        self.assertEqual(spans, [PLATE_WIDTH_MM, PLATE_WIDTH_MM, 183.0, 183.0])
        self.assertEqual(
            [step["reference"]["geometry"]["shortfall_mm"] for step in steps], [0.0, 0.0, 2.0, 2.0]
        )

    def test_full_span_selection_refuses_the_shortened_edge(self) -> None:
        inspection = box_inspection()
        first = select_wall_edge(inspection, PLATE_BOUNDS, "+x", face="top")
        second = select_wall_edge(inspection, PLATE_BOUNDS, "-x", face="top")
        refreshed = refresh_after_flange(inspection, PLATE_BOUNDS, first, "+x", step=1)
        refreshed = refresh_after_flange(refreshed, PLATE_BOUNDS, second, "-x", step=2)
        with self.assertRaises(EdgeSelectionError) as ctx:
            select_wall_edge(refreshed, PLATE_BOUNDS, "-y", face="top")
        message = str(ctx.exception)
        self.assertIn("no full-length edge", message)
        self.assertIn("short by 2.000 mm", message)

    def test_refresh_keeps_untouched_geometry_and_renumbers_it(self) -> None:
        inspection = box_inspection()
        reference = select_wall_edge(inspection, PLATE_BOUNDS, "-x", face="top")
        refreshed = refresh_after_flange(
            inspection,
            PLATE_BOUNDS,
            select_wall_edge(inspection, PLATE_BOUNDS, "+x", face="top"),
            "+x",
        )
        again = select_wall_edge(refreshed, PLATE_BOUNDS, "-x", face="top")
        self.assertNotEqual(again["edge"]["id"], reference["edge"]["id"])
        self.assertEqual(again["geometry"]["start"], reference["geometry"]["start"])
        self.assertEqual(again["geometry"]["end"], reference["geometry"]["end"])


class PlanContractTest(unittest.TestCase):
    def test_four_wall_plan_validates_and_matches_reported_indices(self) -> None:
        operations, references = four_wall_plan(box_inspection())
        validated = validate_operations(operations)
        self.assertEqual(len(validated), 6)
        self.assertEqual([op["op"] for op in validated[2:]], ["sheetmetal_flange"] * 4)
        self.assertEqual([op["label"] for op in validated[2:]], ["f_px", "f_nx", "f_ny", "f_py"])
        self.assertEqual(len(references), 4)
        reported = {row["label"]: row["index"] for row in ORIGINAL_OPERATION_RESULTS}
        self.assertEqual(reported, {"f_px": 2, "f_ny": 4, "f_py": 5})

    def test_flange_parameters_are_preserved_verbatim(self) -> None:
        operations, _ = four_wall_plan(box_inspection())
        for operation in validate_operations(operations)[2:]:
            self.assertEqual(operation["height"], FLANGE_HEIGHT_MM)
            self.assertEqual(operation["angle"], FLANGE_ANGLE_DEG)
            self.assertEqual(operation["radius"], FLANGE_RADIUS_MM)
            self.assertEqual(operation["y_factor"], FLANGE_Y_FACTOR)
            self.assertFalse(operation["flip"])
            self.assertEqual(operation["edge"]["kind"], "edge")

    def test_flip_is_the_only_field_that_changes(self) -> None:
        inspection = box_inspection()
        reference = select_wall_edge(inspection, PLATE_BOUNDS, "-y", face="top")
        base = flange_op("-y", "f_ny", reference)
        flipped = flange_op("-y", "f_ny", reference, flip=True)
        differences = {key for key in base if base[key] != flipped[key]}
        self.assertEqual(differences, {"flip"})
        self.assertEqual(validate_operations([base])[0]["flip"], False)
        self.assertEqual(validate_operations([flipped])[0]["flip"], True)

    def test_labels_fit_the_native_limit(self) -> None:
        operations, _ = four_wall_plan(box_inspection())
        for operation in operations:
            label = operation["label"]
            self.assertRegex(label, r"^[a-z][a-z0-9_]{0,27}$")

    def test_single_plan_captures_once_while_sequential_refreshes(self) -> None:
        inspection = box_inspection()
        _, references = four_wall_plan(inspection)
        steps = sequential_steps(inspection)
        single = [reference["geometry"] for reference in references]
        sequential = [step["reference"]["geometry"] for step in steps]
        self.assertEqual(len({geometry["id"] for geometry in single}), 4)
        self.assertEqual([geometry["span_mm"] for geometry in single], [232.0, 232.0, 185.0, 185.0])
        self.assertEqual(
            [geometry["span_mm"] for geometry in sequential], [232.0, 232.0, 183.0, 183.0]
        )
        self.assertEqual(single[0]["start"], sequential[0]["start"])
        self.assertNotEqual(single[2]["start"], sequential[2]["start"])
        self.assertEqual(len({geometry["id"] for geometry in sequential}), 4)

    def test_each_sequential_step_validates(self) -> None:
        for step in sequential_steps(box_inspection()):
            validated = validate_operations(step["operations"])
            self.assertEqual(validated[0]["op"], "sheetmetal_flange")
            self.assertEqual(validated[0]["label"], step["label"])


class OracleTest(unittest.TestCase):
    def test_wall_volumes(self) -> None:
        self.assertAlmostEqual(wall_volume_mm3(PLATE_WIDTH_MM), 18_560.0)
        self.assertAlmostEqual(wall_volume_mm3(PLATE_LENGTH_MM), 14_800.0)
        self.assertAlmostEqual(wall_volume_mm3(183.0), 14_640.0)

    def test_corner_overlap_lower_bound(self) -> None:
        one = corner_overlap_volume_mm3(1)
        self.assertAlmostEqual(one, (FLANGE_HEIGHT_MM - FLANGE_RADIUS_MM))
        self.assertGreater(one, 0.0)
        self.assertLess(one, FLANGE_HEIGHT_MM * PLATE_THICKNESS_MM**2)

    def test_third_flange_shares_two_corners(self) -> None:
        self.assertEqual(shared_corners(["+x"], "-x"), 0)
        self.assertEqual(shared_corners(["+x", "-x"], "-y"), 2)
        self.assertEqual(shared_corners(["+x", "-x", "-y"], "+y"), 2)
        self.assertAlmostEqual(corner_overlap_volume_mm3(2), 154.92)
        previous: list[str] = []
        counts = []
        for side, _ in FLANGE_SEQUENCE:
            counts.append(shared_corners(previous, side))
            previous.append(side)
        self.assertEqual(counts, [0, 0, 2, 2])

    def test_material_side_hypotheses_are_distinguishable(self) -> None:
        for side in SIDE_AXES:
            inside = predicted_bbox(side, "inside")
            outside = predicted_bbox(side, "outside")
            axis = SIDE_AXES[side][0]
            index = 1 if side[0] == "+" else 0
            gap = abs(inside[index][axis] - outside[index][axis])
            self.assertAlmostEqual(gap, PLATE_THICKNESS_MM)
            self.assertGreater(gap, 10 * TOL_MM)
            self.assertEqual(classify_material_side(inside, side), "inside")
            self.assertEqual(classify_material_side(outside, side), "outside")

    def test_direction_classification(self) -> None:
        up = predicted_bbox("+x", "inside")
        self.assertEqual(classify_direction(up), "up")
        down = ([0.0, 0.0, -FLANGE_HEIGHT_MM], [185.0, 232.0, 1.0])
        self.assertEqual(classify_direction(down), "down")
        flat = ([0.0, 0.0, 0.0], [185.0 + FLANGE_HEIGHT_MM, 232.0, 1.0])
        self.assertEqual(classify_direction(flat), "in_plane")
        self.assertEqual(classify_direction(PLATE_BOUNDS), "ambiguous")


class BaseWallContractTest(unittest.TestCase):
    """DEV-051 T05/T11: the fixture must build a 1 mm sheet, not a 232 mm one."""

    def test_base_wall_puts_sheet_thickness_on_the_thickness_axis(self) -> None:
        sketch = wall_sketch()
        base = wall_base_op()
        self.assertEqual(sketch["plane"], "XZ")
        self.assertEqual(base["depth"], PLATE_WIDTH_MM)
        self.assertEqual(base["thickness"], PLATE_THICKNESS_MM)
        volume = PLATE_LENGTH_MM * base["thickness"] * base["depth"]
        self.assertAlmostEqual(volume, PLATE_VOLUME_MM3)

    def test_swapped_base_parameters_keep_the_volume_but_not_the_sheet(self) -> None:
        # depth=1/thickness=232 (the pre-fix fixture) has exactly the same volume and
        # bbox, so only Creo's sheetmetal typing separates the two cases: the sheet is
        # 232 mm thick, the 185 x 232 faces become side surfaces and every flange edge
        # is a rim edge (ProSmtedgeContourGet = -8, PRO_TK_BAD_CONTEXT).
        swapped = dict(wall_base_op(), depth=PLATE_THICKNESS_MM, thickness=PLATE_WIDTH_MM)
        self.assertEqual(
            PLATE_LENGTH_MM * swapped["thickness"] * swapped["depth"], PLATE_VOLUME_MM3
        )
        self.assertNotEqual(swapped["thickness"], PLATE_THICKNESS_MM)

    def test_in_plane_wall_also_satisfies_the_volume_oracle(self) -> None:
        # 232 x 80 x 1 mm3 is added by a bent flange and by a flat in-plane extension
        # alike, so the live gate must require direction == "up" as well.
        self.assertEqual(wall_volume_mm3(PLATE_WIDTH_MM), 18_560.0)
        flat = ([0.0, -232.0, -0.5], [PLATE_LENGTH_MM + FLANGE_HEIGHT_MM, 0.0, 0.5])
        self.assertEqual(classify_direction(flat), "in_plane")


class HypothesisTest(unittest.TestCase):
    def test_hypotheses_are_complete_and_unique(self) -> None:
        ids = [hypothesis["id"] for hypothesis in HYPOTHESES]
        self.assertEqual(len(ids), len(set(ids)))
        for hypothesis in HYPOTHESES:
            for key in ("statement", "probe", "expected_if_true", "refutation", "status"):
                self.assertTrue(hypothesis[key], (hypothesis["id"], key))
            self.assertTrue(hypothesis["judgement_fields"], hypothesis["id"])

    def test_hypothesis_fields_exist_in_the_judgement_record(self) -> None:
        known = set(JUDGEMENT_FIELDS)
        for hypothesis in HYPOTHESES:
            unknown = set(hypothesis["judgement_fields"]) - known
            self.assertFalse(unknown, (hypothesis["id"], unknown))

    def test_judgement_template_covers_every_field(self) -> None:
        record = judgement_template("f_px", 2, "+x")
        self.assertEqual(set(record), set(JUDGEMENT_FIELDS))
        self.assertEqual(record["height_input"], FLANGE_HEIGHT_MM)
        self.assertEqual(record["radius_input"], FLANGE_RADIUS_MM)
        self.assertEqual(record["y_factor_input"], FLANGE_Y_FACTOR)
        self.assertEqual(record["angle_input"], FLANGE_ANGLE_DEG)
        for name in ("added_volume_mm3", "material_side", "direction", "toolkit_code"):
            self.assertIsNone(record[name])
        for name in ("saved_file_reloaded_and_verified", "rolled_back_rebuild_required"):
            self.assertIsNone(record[name])

    def test_decision_table_is_actionable(self) -> None:
        for row in DECISION_TABLE:
            self.assertTrue(row["observation"])
            self.assertTrue(row["conclusion"])
        self.assertEqual(len(DECISION_TABLE), len({row["observation"] for row in DECISION_TABLE}))

    def test_thick_plate_branch_is_pending(self) -> None:
        self.assertEqual(THICK_PLATE_BRANCH["status"], "pending_t03_live_contract")
        self.assertAlmostEqual(
            THICK_PLATE_BRANCH["first_flange"]["expected_added_volume_mm3"], 14_800.0
        )
        self.assertTrue(THICK_PLATE_BRANCH["unknown"])
        for hypothesis in HYPOTHESES:
            if hypothesis["id"] == "H5_thick_plate_first_flange":
                self.assertEqual(hypothesis["status"], "pending_t03_live_contract")

    def test_live_refusal_points_at_the_single_dev_service(self) -> None:
        self.assertIn("MCP_CREO_MechDog_dev", LIVE_REFUSAL)
        self.assertIn("--confirm-session-usable", LIVE_REFUSAL)
        self.assertIn("offline", LIVE_REFUSAL)


class OriginalEvidenceTest(unittest.TestCase):
    def test_operation_results_match_the_reported_plan(self) -> None:
        results = {row["label"]: row for row in ORIGINAL_OPERATION_RESULTS}
        self.assertEqual(results["f_px"]["execution_status"], "succeeded")
        self.assertEqual(results["f_ny"]["execution_status"], "failed")
        self.assertEqual(results["f_py"]["execution_status"], "not_executed")
        self.assertEqual(results["f_px"]["effect_status"], "rolled_back")
        self.assertEqual(results["f_ny"]["effect_status"], "rolled_back")
        self.assertEqual(results["f_py"]["effect_status"], "no_effect")
        self.assertEqual(sorted(row["index"] for row in ORIGINAL_OPERATION_RESULTS), [2, 4, 5])

    def test_evidence_tokens_appear_in_the_archived_report(self) -> None:
        for token in (
            ORIGINAL_JOB,
            ORIGINAL_MODEL,
            ORIGINAL_MODEL_NAME,
            ORIGINAL_ERROR,
        ):
            self.assertTrue(archived_reports_containing(token), token)

    def test_failed_plan_requires_a_full_rebuild(self) -> None:
        # S10 lists f_px/f_nx as succeeded but rolled_back: resuming at flange 3
        # would build on geometry that no longer exists.
        for row in ORIGINAL_OPERATION_RESULTS:
            if row["execution_status"] == "succeeded":
                self.assertEqual(row["effect_status"], "rolled_back")
        record = judgement_template("f_ny", 4, "-y")
        self.assertIn("rolled_back_rebuild_required", record)


class FlangeWordingTest(unittest.TestCase):
    """R09 (0.13.0 feedback §3.1/§3.3/§3.5): wording only, no geometry or Creo."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (REPO_ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8")
        cls.flange = cls.source[cls.source.index("static void generic_sheetmetal_flange(") :]
        cls.guide = cls.source[
            cls.source.index("static std::string flange_first_wall_guide()") : cls.source.index(
                "static std::string flange_edge_reference_contract()"
            )
        ]

    def test_reference_error_names_the_plan_path_and_example(self) -> None:
        self.assertIn("operations[i].edge", self.source)
        self.assertIn("{kind:'edge',id:", self.source)
        self.assertIn("edge_ref.dump()", self.flange)

    def test_native_planar_guide_never_offers_the_conversion_recipe(self) -> None:
        planar = self.guide[
            self.guide.index("if (planar && !conversion)") : self.guide.index(
                "if (conversion && !planar)"
            )
        ]
        self.assertIn("creo_sheetmetal_planar_wall", planar)
        self.assertIn("no wall_contract", planar)
        self.assertNotIn("examples/sheetmetal_base_yz.json", planar)
        self.assertNotIn("YZ plane", planar)
        self.assertNotIn("see wall_contract", planar)

    def test_conversion_guide_keeps_the_wall_contract_recipe(self) -> None:
        conversion = self.guide[
            self.guide.index("if (conversion && !planar)") : self.guide.index(
                'return "This model does not report'
            )
        ]
        self.assertIn("wall_contract.wall_face_ids", conversion)
        self.assertIn("examples/sheetmetal_base_yz.json", conversion)

    def test_unknown_source_gets_no_old_recipe(self) -> None:
        unknown = self.guide[self.guide.index('return "This model does not report') :]
        self.assertIn("no first-wall recipe", unknown)
        self.assertNotIn("examples/sheetmetal_base_yz.json", unknown)
        self.assertNotIn("see wall_contract", unknown)

    def test_adjacent_guard_says_relief_is_unproven(self) -> None:
        section = self.flange[
            self.flange.index(
                "J adjacency = flange_adjacent_bend_end_evidence"
            ) : self.flange.index("ProSection2DAlloc")
        ]
        self.assertIn("not proven to resolve this corner", section)
        self.assertIn("resolve this corner", section)
        self.assertIn("bend-end relief", section)
        self.assertNotIn("implements no corner relief", section)

    def test_adjacent_guard_is_not_bypassed_by_a_supplied_relief(self) -> None:
        guard = "\n        J adjacency = flange_adjacent_bend_end_evidence(op);\n"
        self.assertIn(guard, self.flange)
        section = self.flange[self.flange.index(guard) : self.flange.index("ProSection2DAlloc")]
        self.assertNotIn("relief_request", section)

    def test_capabilities_scope_does_not_claim_four_walls_or_corner_relief(self) -> None:
        limits = families()["sheetmetal"]["limits"]
        self.assertIn("four walls are not delivered", limits)
        self.assertIn("bend-end relief", limits)
        self.assertIn("not corner relief", limits)
        self.assertIn("not a geometry or miter proof", limits)
        self.assertIn("not proven to resolve corner overlap", limits)
        self.assertIn("still applies when relief is supplied", limits)

    def test_edge_field_description_names_path_and_example(self) -> None:
        description = SheetmetalFlangeOp.model_fields["edge"].description
        self.assertIn("operations[i].edge", description)
        self.assertIn("{kind:'edge',id:N}", description)


if __name__ == "__main__":
    unittest.main()
