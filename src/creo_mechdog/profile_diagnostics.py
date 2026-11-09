"""Analytic multi-contour diagnostics for solid sketch profiles (DEV-047 T06).

The module analyses the coordinates supplied to a sketch operation only. It
does not model the Creo section solver: every category is derived from the
input curves and the native solver stays authoritative for anything else.
Only conditions that follow from the supplied geometry reject admission, and
unsupported curve types disable rejection instead of guessing.

Two published tolerances come from the native sketch path: coordinate
dimensioning solves with a 1e-9 mm epsilon, other modes use 1e-4 mm. A contour
that closes only through the looser tolerance is therefore reported as
``near_tolerance`` and rejected for explicit coordinate dimensioning.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

CLOSURE_TOLERANCE_MM = 1e-4
EXACT_TOLERANCE_MM = 1e-9
# DEV-081/F02: a join gap this small relative to the requested closure scale
# is an input floating-point residual, not a kernel-visible open profile.
RESIDUAL_RATIO = 1e-3
ZERO_AREA_MM2 = 1e-9
_INTERSECTION_EPS = 1e-9
_TANGENT_EPS = 1e-8
_TWO_PI = 2.0 * math.pi
_MAX_ITEMS = 20

Point = tuple[float, float]


@dataclass(frozen=True)
class Curve:
    """One analytic piece of the supplied profile."""

    name: str
    kind: str  # "line", "arc", "circle", "unsupported"
    start: Point | None = None
    end: Point | None = None
    center: Point | None = None
    radius: float = 0.0
    start_angle: float = 0.0
    sweep: float = 0.0


@dataclass
class _Contour:
    curves: list[int]
    closed: bool
    area: float = 0.0
    max_gap: float = 0.0
    polygon: list[Point] = field(default_factory=list)
    depth: int = 0
    interior_known: bool = True


def _point(value) -> Point:
    return (float(value[0]), float(value[1]))


def _on_circle(center: Point, radius: float, angle: float) -> Point:
    return (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))


def _arc_direction(entity: dict) -> int:
    # FEAT-034/T02: the analyzer consumes the same strict dir contract as the
    # schema. Payloads without the field keep the legacy counterclockwise +1.
    value = entity.get("dir", 1)
    if type(value) is not int or value not in (-1, 1):
        raise ValueError(
            "Arc dir must be the strict integer +1 (counterclockwise) or -1 (clockwise)"
        )
    return value


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _expand(entities: list[dict]) -> tuple[list[Curve], list[str]]:
    curves: list[Curve] = []
    unsupported: list[str] = []
    for entity in entities:
        kind = entity["type"]
        if entity.get("construction") or kind == "centerline":
            continue
        name = str(entity["name"])
        if kind == "circle":
            curves.append(
                Curve(
                    name,
                    "circle",
                    center=_point(entity["center"]),
                    radius=float(entity["radius"]),
                    sweep=_TWO_PI,
                )
            )
        elif kind == "arc":
            center = _point(entity["center"])
            radius = float(entity["radius"])
            start_deg = float(entity["start_angle"])
            end_deg = float(entity["end_angle"])
            direction = _arc_direction(entity)
            if not math.isfinite(start_deg) or not math.isfinite(end_deg):
                raise ValueError("Arc angles must be finite degrees")
            start = math.radians(start_deg)
            # Signed sweep: positive runs counterclockwise from the logical
            # start, negative clockwise (FEAT-034/T02). A zero sweep or a
            # complete circle belongs to the circle entity.
            magnitude = (
                (end_deg - start_deg) % 360 if direction > 0 else (start_deg - end_deg) % 360
            )
            if magnitude <= 1e-9:
                raise ValueError(
                    "Arc sweep must be strictly between 0 and 360 degrees; "
                    "use circle for a complete circle"
                )
            sweep = direction * math.radians(magnitude)
            curves.append(
                Curve(
                    name,
                    "arc",
                    start=_on_circle(center, radius, start),
                    end=_on_circle(center, radius, start + sweep),
                    center=center,
                    radius=radius,
                    start_angle=start,
                    sweep=sweep,
                )
            )
        elif kind == "line":
            curves.append(
                Curve(name, "line", start=_point(entity["start"]), end=_point(entity["end"]))
            )
        elif kind == "rectangle":
            low, high = _point(entity["min"]), _point(entity["max"])
            corners = [low, (high[0], low[1]), high, (low[0], high[1])]
            for index in range(4):
                curves.append(
                    Curve(
                        f"{name}_{index}",
                        "line",
                        start=corners[index],
                        end=corners[(index + 1) % 4],
                    )
                )
        elif kind == "polyline":
            points = [_point(value) for value in entity["points"]]
            segments = len(points) - 1 + (1 if entity.get("closed") else 0)
            for index in range(segments):
                curves.append(
                    Curve(
                        f"{name}_{index}",
                        "line",
                        start=points[index],
                        end=points[(index + 1) % len(points)],
                    )
                )
        else:
            # Ellipse/spline topology is checked by the native solver; a static
            # verdict here would be a guess.
            unsupported.append(name)
    return curves, unsupported


class _Nodes:
    """Cluster curve endpoints that meet within the closure tolerance."""

    def __init__(self, tolerance: float) -> None:
        self.tolerance = tolerance
        self.points: list[Point] = []
        self.cluster: list[int] = []
        self.representative: list[Point] = []
        self.members: list[list[int]] = []

    def add(self, point: Point) -> int:
        index = len(self.points)
        self.points.append(point)
        for candidate, existing in enumerate(self.representative):
            if _distance(point, existing) <= self.tolerance:
                self.cluster.append(candidate)
                self.members[candidate].append(index)
                return candidate
        self.cluster.append(len(self.representative))
        self.representative.append(point)
        self.members.append([index])
        return len(self.representative) - 1

    def gap(self, node: int) -> float:
        members = self.members[node]
        if len(members) < 2:
            return 0.0
        return max(
            _distance(self.points[a], self.points[b])
            for position, a in enumerate(members)
            for b in members[position + 1 :]
        )


def _components(
    edges: list[tuple[int, int, int]], adjacency: dict[int, list[tuple[int, int]]]
) -> list[list[int]]:
    ends = {edge: (first, second) for edge, first, second in edges}
    remaining = set(ends)
    result = []
    while remaining:
        seed = next(iter(remaining))
        stack = [seed]
        component = []
        while stack:
            edge = stack.pop()
            if edge not in remaining:
                continue
            remaining.remove(edge)
            component.append(edge)
            for vertex in ends[edge]:
                for neighbour, _ in adjacency[vertex]:
                    if neighbour in remaining:
                        stack.append(neighbour)
        result.append(component)
    return result


def _ordered(adjacency: dict[int, list], start: int) -> list[tuple[int, int]]:
    """Walk a closed component: (curve index, entry node) in traversal order."""
    order: list[tuple[int, int]] = []
    used: set[int] = set()
    node = start
    while True:
        options = [(edge, other) for edge, other in adjacency[node] if edge not in used]
        if not options:
            return []
        edge, other = options[0]
        used.add(edge)
        order.append((edge, node))
        node = other
        if node == start:
            return order


def _area(curve: Curve, forward: bool) -> float:
    if curve.kind == "line":
        a, b = (curve.start, curve.end) if forward else (curve.end, curve.start)
        return 0.5 * (a[0] * b[1] - b[0] * a[1])
    center, radius = curve.center, curve.radius
    start, end = curve.start_angle, curve.start_angle + curve.sweep
    value = 0.5 * (
        radius * center[0] * (math.sin(end) - math.sin(start))
        - radius * center[1] * (math.cos(end) - math.cos(start))
        + radius * radius * curve.sweep
    )
    return value if forward else -value


def _sample(curve: Curve, forward: bool) -> list[Point]:
    if curve.kind == "line":
        return [curve.start, curve.end] if forward else [curve.end, curve.start]
    steps = max(8, math.ceil(abs(curve.sweep) / (math.pi / 18)))
    angles = [curve.start_angle + curve.sweep * index / steps for index in range(steps + 1)]
    if not forward:
        angles.reverse()
    return [_on_circle(curve.center, curve.radius, angle) for angle in angles]


def _dedupe(points: list[Point]) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if not result or _distance(result[-1], point) > EXACT_TOLERANCE_MM:
            result.append(point)
    if len(result) > 1 and _distance(result[0], result[-1]) <= EXACT_TOLERANCE_MM:
        result.pop()
    return result


def _polygon_area(points: list[Point]) -> float:
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )


def _inside(point: Point, polygon: list[Point]) -> bool:
    """Even-odd ray casting against the sampled contour boundary."""
    x, y = point
    inside = False
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        if (first[1] > y) == (second[1] > y):
            continue
        crossing = first[0] + (y - first[1]) * (second[0] - first[0]) / (second[1] - first[1])
        if x < crossing:
            inside = not inside
    return inside


def _interior(polygon: list[Point]) -> tuple[Point, bool]:
    if len(polygon) >= 3 and abs(_polygon_area(polygon)) > ZERO_AREA_MM2:
        centroid = (
            sum(point[0] for point in polygon) / len(polygon),
            sum(point[1] for point in polygon) / len(polygon),
        )
        if _inside(centroid, polygon):
            return centroid, True
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        midpoint = ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
        for scale in (1e-6, 1e-5, 1e-4):
            toward = (
                midpoint[0] + (polygon[0][0] - midpoint[0]) * scale,
                midpoint[1] + (polygon[0][1] - midpoint[1]) * scale,
            )
            if _inside(toward, polygon):
                return toward, True
    return polygon[0], False


def _segment_segment(a1: Point, a2: Point, b1: Point, b2: Point) -> list[tuple[str, Point]]:
    rx, ry = a2[0] - a1[0], a2[1] - a1[1]
    sx, sy = b2[0] - b1[0], b2[1] - b1[1]
    denominator = rx * sy - ry * sx
    scale = math.hypot(rx, ry) * math.hypot(sx, sy)
    if abs(denominator) <= _INTERSECTION_EPS * max(scale, 1.0):
        if abs(_cross(a1, a2, b1)) > _TANGENT_EPS or abs(_cross(a1, a2, b2)) > _TANGENT_EPS:
            return []
        length = rx * rx + ry * ry
        projections = [(b[0] - a1[0]) * rx + (b[1] - a1[1]) * ry for b in (b1, b2)]
        low, high = min(projections), max(projections)
        if high < -_TANGENT_EPS or low > length + _TANGENT_EPS:
            return []
        start = max(low, 0.0) / length
        return [("overlap", (a1[0] + rx * start, a1[1] + ry * start))]
    t = ((b1[0] - a1[0]) * sy - (b1[1] - a1[1]) * sx) / denominator
    u = ((b1[0] - a1[0]) * ry - (b1[1] - a1[1]) * rx) / denominator
    if not -_INTERSECTION_EPS <= t <= 1 + _INTERSECTION_EPS:
        return []
    if not -_INTERSECTION_EPS <= u <= 1 + _INTERSECTION_EPS:
        return []
    point = (a1[0] + t * rx, a1[1] + t * ry)
    interior = (
        _INTERSECTION_EPS < t < 1 - _INTERSECTION_EPS
        and _INTERSECTION_EPS < u < 1 - _INTERSECTION_EPS
    )
    return [("cross" if interior else "touch", point)]


def _segment_circle(a1: Point, a2: Point, center: Point, radius: float) -> list[tuple[str, Point]]:
    dx, dy = a2[0] - a1[0], a2[1] - a1[1]
    fx, fy = a1[0] - center[0], a1[1] - center[1]
    a = dx * dx + dy * dy
    if a <= EXACT_TOLERANCE_MM:
        return []
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    discriminant = b * b - 4 * a * c
    if discriminant < -_TANGENT_EPS:
        return []
    if discriminant <= _TANGENT_EPS:
        t = -b / (2 * a)
        if -_INTERSECTION_EPS <= t <= 1 + _INTERSECTION_EPS:
            return [("touch", (a1[0] + t * dx, a1[1] + t * dy))]
        return []
    root = math.sqrt(max(discriminant, 0.0))
    result = []
    for t in ((-b - root) / (2 * a), (-b + root) / (2 * a)):
        if -_INTERSECTION_EPS <= t <= 1 + _INTERSECTION_EPS:
            result.append(("cross", (a1[0] + t * dx, a1[1] + t * dy)))
    return result


def _circle_circle(c1: Point, r1: float, c2: Point, r2: float) -> list[tuple[str, Point]]:
    distance = _distance(c1, c2)
    if distance <= _TANGENT_EPS and abs(r1 - r2) <= _TANGENT_EPS:
        return [("overlap", c1)]
    if distance > r1 + r2 + _TANGENT_EPS:
        return []
    if distance < abs(r1 - r2) - _TANGENT_EPS:
        return []
    if abs(distance - (r1 + r2)) <= _TANGENT_EPS or abs(distance - abs(r1 - r2)) <= _TANGENT_EPS:
        if distance <= _TANGENT_EPS:
            return [("touch", c1)]
        point = (c1[0] + (c2[0] - c1[0]) * r1 / distance, c1[1] + (c2[1] - c1[1]) * r1 / distance)
        return [("touch", point)]
    projection = (r1 * r1 - r2 * r2 + distance * distance) / (2 * distance)
    height = math.sqrt(max(r1 * r1 - projection * projection, 0.0))
    base = (
        c1[0] + (c2[0] - c1[0]) * projection / distance,
        c1[1] + (c2[1] - c1[1]) * projection / distance,
    )
    offset = (-(c2[1] - c1[1]) * height / distance, (c2[0] - c1[0]) * height / distance)
    return [
        ("cross", (base[0] + offset[0], base[1] + offset[1])),
        ("cross", (base[0] - offset[0], base[1] - offset[1])),
    ]


def _in_arc(curve: Curve, point: Point) -> bool:
    angle = math.atan2(point[1] - curve.center[1], point[0] - curve.center[0])
    offset = (angle - curve.start_angle) % _TWO_PI
    if curve.sweep >= 0:
        return offset <= curve.sweep + 1e-9 or offset >= _TWO_PI - 1e-9
    # Clockwise arc: the covered band ends at the logical start angle.
    return offset >= _TWO_PI + curve.sweep - 1e-9 or offset <= 1e-9


def _intersections(first: Curve, second: Curve) -> list[tuple[str, Point]]:
    if first.kind == "circle" and second.kind == "circle":
        return _circle_circle(first.center, first.radius, second.center, second.radius)
    if first.kind == "line" and second.kind == "line":
        return _segment_segment(first.start, first.end, second.start, second.end)
    if first.kind == "line" and second.kind in ("circle", "arc"):
        points = _segment_circle(first.start, first.end, second.center, second.radius)
        return (
            points
            if second.kind == "circle"
            else [item for item in points if _in_arc(second, item[1])]
        )
    if first.kind in ("circle", "arc") and second.kind == "line":
        return _intersections(second, first)
    if first.kind in ("circle", "arc") and second.kind in ("circle", "arc"):
        points = _circle_circle(first.center, first.radius, second.center, second.radius)
        if first.kind == "arc":
            points = [item for item in points if _in_arc(first, item[1])]
        if second.kind == "arc":
            points = [item for item in points if _in_arc(second, item[1])]
        return points
    return []


def _item(kind: str, names: list[str], **extra) -> dict:
    return {"category": kind, "entities": names, **extra}


def _arc_echo(curve: Curve) -> dict:
    # FEAT-034/T02: logical start/end, tangents, direction and sweep of one arc
    # in the sketch-local frame. This block describes the supplied input only
    # (source="input"); measured kernel geometry never enters this report and
    # input values are never presented as a native result.
    direction = 1 if curve.sweep >= 0 else -1

    def tangent(angle: float) -> list[float]:
        if direction > 0:
            return [-math.sin(angle), math.cos(angle)]
        return [math.sin(angle), -math.cos(angle)]

    return {
        "name": curve.name,
        "source": "input",
        "query_code": None,
        "frame": "sketch_local",
        "start_uv": [curve.start[0], curve.start[1]],
        "end_uv": [curve.end[0], curve.end[1]],
        # BUG-049/N03: center and radius enable the two-stage comparison
        # against the measured arc report; both describe the input only.
        "center_uv": [curve.center[0], curve.center[1]],
        "radius_mm": curve.radius,
        "start_tangent_uv": tangent(curve.start_angle),
        "end_tangent_uv": tangent(curve.start_angle + curve.sweep),
        "dir": direction,
        "sweep_deg": math.degrees(abs(curve.sweep)),
    }


def analyze_profile(entities: list[dict], tolerance: float = CLOSURE_TOLERANCE_MM) -> dict:
    """Return the analytic contour report for one sketch entity list."""
    curves, unsupported = _expand(entities)
    nodes = _Nodes(tolerance)
    edges: list[tuple[int, int, int]] = []
    for index, curve in enumerate(curves):
        if curve.kind in ("line", "arc"):
            edges.append((index, nodes.add(curve.start), nodes.add(curve.end)))
    edge_nodes = {edge: (first, second) for edge, first, second in edges}
    adjacency: dict[int, list[tuple[int, int]]] = {}
    degrees: dict[int, int] = {}
    for edge, first, second in edges:
        adjacency.setdefault(first, []).append((edge, second))
        adjacency.setdefault(second, []).append((edge, first))
        degrees[first] = degrees.get(first, 0) + 1
        degrees[second] = degrees.get(second, 0) + 1

    categories: dict[str, list[dict]] = {
        "open": [],
        "branched": [],
        "self_intersecting": [],
        "intersecting": [],
        "tangent": [],
        "zero_area": [],
        "near_tolerance": [],
        "unsupported": [_item("unsupported", [name]) for name in unsupported],
    }
    contours: list[_Contour] = []
    for component in _components(edges, adjacency):
        vertices = set()
        for edge in component:
            vertices.update(edge_nodes[edge])
        closed = all(degrees[vertex] == 2 for vertex in vertices)
        contour = _Contour(curves=list(component), closed=closed)
        contour.max_gap = max(nodes.gap(vertex) for vertex in vertices)
        if closed:
            order = _ordered(adjacency, edge_nodes[component[0]][0])
            area = 0.0
            points: list[Point] = []
            for edge, entry in order:
                curve = curves[edge]
                forward = edge_nodes[edge][0] == entry
                area += _area(curve, forward)
                points.extend(_sample(curve, forward))
            contour.area = area
            contour.polygon = _dedupe(points)
            if abs(area) <= ZERO_AREA_MM2:
                categories["zero_area"].append(
                    _item("zero_area", [curves[edge].name for edge in component], area_mm2=area)
                )
        else:
            names = [curves[edge].name for edge in component]
            open_ends = [vertex for vertex in vertices if degrees[vertex] == 1]
            branches = [vertex for vertex in vertices if degrees[vertex] > 2]
            if open_ends:
                categories["open"].append(
                    _item(
                        "open",
                        names,
                        points=[nodes.representative[vertex] for vertex in open_ends],
                    )
                )
            if branches:
                categories["branched"].append(
                    _item(
                        "branched",
                        names,
                        points=[nodes.representative[vertex] for vertex in branches],
                        degrees=sorted(degrees[vertex] for vertex in branches),
                    )
                )
        contours.append(contour)

    circle_curves = [index for index, curve in enumerate(curves) if curve.kind == "circle"]
    for index in circle_curves:
        contour = _Contour(curves=[index], closed=True, area=math.pi * curves[index].radius ** 2)
        contour.polygon = _dedupe(_sample(curves[index], True))
        contours.append(contour)

    for node, _members in enumerate(nodes.members):
        gap = nodes.gap(node)
        if EXACT_TOLERANCE_MM < gap <= tolerance:
            names = sorted({curves[edge].name for edge, _ in adjacency.get(node, [])})
            categories["near_tolerance"].append(
                _item(
                    "near_tolerance",
                    names,
                    gap_mm=gap,
                    point=nodes.representative[node],
                    tolerance_mm=tolerance,
                )
            )

    for index, contour in enumerate(contours):
        if not contour.closed:
            continue
        curve_list = [curves[item] for item in contour.curves]
        for first in range(len(curve_list)):
            for second in range(first + 1, len(curve_list)):
                if len(curve_list) > 1 and (
                    second == first + 1 or (first == 0 and second == len(curve_list) - 1)
                ):
                    continue
                for kind, point in _intersections(curve_list[first], curve_list[second]):
                    if kind == "touch":
                        categories["tangent"].append(
                            _item(
                                "tangent",
                                [curve_list[first].name, curve_list[second].name],
                                point=point,
                                scope="self",
                            )
                        )
                    else:
                        categories["self_intersecting"].append(
                            _item(
                                "self_intersecting",
                                [curve_list[first].name, curve_list[second].name],
                                point=point,
                                contact=kind,
                            )
                        )
    for first in range(len(contours)):
        if not contours[first].closed:
            continue
        for second in range(first + 1, len(contours)):
            if not contours[second].closed:
                continue
            for a in contours[first].curves:
                for b in contours[second].curves:
                    for kind, point in _intersections(curves[a], curves[b]):
                        name = "tangent" if kind == "touch" else "intersecting"
                        categories[name].append(
                            _item(
                                name,
                                [curves[a].name, curves[b].name],
                                point=point,
                                contact=kind,
                                contours=[first, second],
                            )
                        )

    closed = [contour for contour in contours if contour.closed]
    for index, contour in enumerate(closed):
        if len(contour.polygon) < 3:
            continue
        point, known = _interior(contour.polygon)
        contour.interior_known = known
        if not known:
            continue
        for other_index, other in enumerate(closed):
            if index == other_index or len(other.polygon) < 3:
                continue
            # A smaller closed region whose interior point lies in the other
            # region is nested inside it; equal-area coincident boundaries are
            # reported by the intersection check instead of nesting twice.
            if abs(contour.area) >= abs(other.area) - ZERO_AREA_MM2:
                continue
            if _inside(point, other.polygon):
                contour.depth += 1

    return {
        "method": "analytic-input",
        "analysis": "partial" if unsupported else "complete",
        "closure_tolerance_mm": tolerance,
        "exact_tolerance_mm": EXACT_TOLERANCE_MM,
        "arc_geometry": [_arc_echo(curve) for curve in curves if curve.kind == "arc"],
        "entity_count": len(curves),
        "contour_count": len(contours),
        "closed_contour_count": len(closed),
        "open_contour_count": len(contours) - len(closed),
        "material_area_mm2": sum(
            abs(contour.area) * (1 if contour.depth % 2 == 0 else -1) for contour in closed
        ),
        "categories": {
            name: {
                "count": len(items),
                "items": items[:_MAX_ITEMS],
                "truncated": len(items) > _MAX_ITEMS,
            }
            for name, items in categories.items()
        },
        "contours": [
            {
                "index": index,
                "closed": contour.closed,
                "entity_count": len(contour.curves),
                "entities": [curves[item].name for item in contour.curves],
                "area_mm2": contour.area if contour.closed else None,
                "orientation": "ccw" if contour.area > 0 else ("cw" if contour.area < 0 else None),
                "nesting_depth": contour.depth,
                "max_join_gap_mm": contour.max_gap,
                "interior_point_known": contour.interior_known,
            }
            for index, contour in enumerate(contours)
        ],
    }


_CATEGORY_TEXT = {
    "open": "an open contour (endpoints are not closed within {closure:g} mm)",
    "branched": "a branched contour (more than two curves meet at one point)",
    "self_intersecting": "a self-intersecting contour",
    "intersecting": "contours whose boundaries cross",
    "tangent": "contours that touch without crossing",
    "zero_area": "a zero-area contour",
    "near_tolerance": "endpoints joined only by the closure tolerance",
    "no_closed_contour": "no closed contour",
}


def validate_solid_profile(
    entities: list[dict],
    dimensioning: str = "auto",
    operation: str = "extrude",
    tolerance: float = CLOSURE_TOLERANCE_MM,
) -> dict:
    """Reject a solid profile only when the supplied geometry proves it invalid.

    Unsupported entities (ellipse/spline) skip the verdict: their topology is
    checked by the native solver, not guessed here. ``tolerance`` is the
    caller's analytic closure scale; the native epsilon and solve precision are
    never changed by it.
    """
    if (
        isinstance(tolerance, bool)
        or not isinstance(tolerance, (int, float))
        or not math.isfinite(tolerance)
        or tolerance <= 0
    ):
        raise ValueError("closure_tolerance_mm must be a finite positive number of millimeters")
    tolerance = float(tolerance)
    report = analyze_profile(entities, tolerance)
    if report["analysis"] != "complete":
        return report
    fatal = ["open", "branched", "self_intersecting", "intersecting", "tangent", "zero_area"]
    near = report["categories"]["near_tolerance"]
    residual_only = (
        bool(near["items"])
        and not near["truncated"]
        and all(item["gap_mm"] <= tolerance * RESIDUAL_RATIO for item in near["items"])
    )
    if dimensioning == "coordinates" and not (
        residual_only and report["closed_contour_count"] >= 1 and report["open_contour_count"] == 0
    ):
        # Coordinate dimensioning solves with a 1e-9 mm epsilon. Only a profile
        # that resolves to closed contours with no open ones, whose every join
        # gap is a residual next to the requested closure scale, is admitted
        # (DEV-081/F02); larger gaps keep the original kernel-openness guard.
        fatal.append("near_tolerance")
    problems = [name for name in fatal if report["categories"][name]["count"]]
    if not report["closed_contour_count"] and "no_closed_contour" not in problems:
        problems.insert(0, "no_closed_contour")
    if not problems:
        return report
    details = []
    for name in problems:
        entry = report["categories"].get(name, {"items": []})
        first = entry["items"][0] if entry["items"] else {}
        names = "/".join(first.get("entities", []))
        point = first.get("point")
        if point is None and first.get("points"):
            point = first["points"][0]
        where = f" near ({point[0]:.9g}, {point[1]:.9g}) mm" if point else ""
        detail = _CATEGORY_TEXT[name].format(closure=report["closure_tolerance_mm"])
        details.append(f"[{name}] {detail} ({names}){where}" if names else f"[{name}] {detail}")
    raise ValueError(
        f"Solid {operation} profile rejected: detected "
        f"{report['closed_contour_count']} closed contour(s), "
        f"{report['open_contour_count']} open contour(s) and "
        f"{report['entity_count']} curve entities; "
        + "; ".join(details)
        + ". Supply disjoint or nested closed loops; the native solver remains authoritative "
        "for anything this check cannot confirm. Remediation: set closure_tolerance_mm, "
        "merge the arcs into one polyline, or use snap_endpoints / endpoint_policy=weld; "
        "weld is applied at submission time, not during plan validation."
    )
