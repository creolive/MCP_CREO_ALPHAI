"""Analytic multi-contour fixtures for DEV-047 T06.

Every coordinate and radius is given explicitly; the only variable between
cases is the number and type of closed contours. The external gear10.json and
sketch_entities.json attachments are missing, so these are independent
fixtures, not byte-for-byte replays of the reported case.
"""

from __future__ import annotations

import math

DEPTH_MM = 8.0
RADIUS_MM = 3.0


def circle(name: str, center: tuple[float, float], radius: float = RADIUS_MM) -> dict:
    return {"type": "circle", "name": name, "center": list(center), "radius": radius}


def arc_ring(prefix: str, center: tuple[float, float], radius: float = RADIUS_MM) -> list[dict]:
    """A closed loop of four quarter arcs; the fourth ends at 360 degrees."""
    return [
        {
            "type": "arc",
            "name": f"{prefix}_{quarter}",
            "center": list(center),
            "radius": radius,
            "start_angle": quarter * 90,
            "end_angle": quarter * 90 + 90,
        }
        for quarter in range(4)
    ]


def row(count: int, factory, spacing: float = 12.0) -> list[dict]:
    start = -(count - 1) * spacing / 2
    result: list[dict] = []
    for index in range(count):
        result.extend(factory(index, (start + index * spacing, 0.0)))
    return result


def circles(count: int) -> list[dict]:
    return row(count, lambda index, center: [circle(f"c{index}", center)])


def rings(count: int) -> list[dict]:
    return row(count, lambda index, center: arc_ring(f"r{index}", center))


def separated(count: int, kind: str) -> dict:
    entities = circles(count) if kind == "circle" else rings(count)
    return {
        "name": f"{count}_{kind}s",
        "entities": entities,
        "depth": DEPTH_MM,
        "expected_area_mm2": count * math.pi * RADIUS_MM**2,
        "expected_contour_count": count,
        "expected_entity_count": count if kind == "circle" else count * 4,
    }


def mixed(circle_count: int = 2, ring_count: int = 5) -> dict:
    """The reported '2 circles + 5 four-arc loops' shape in one sketch."""
    entities: list[dict] = []
    for index in range(circle_count):
        entities.append(circle(f"m{index}", (-30.0 + index * 12.0, 20.0)))
    for index in range(ring_count):
        entities.extend(arc_ring(f"mix{index}", (-24.0 + index * 12.0, -20.0)))
    return {
        "name": "two_circles_five_arc_rings",
        "entities": entities,
        "depth": DEPTH_MM,
        "expected_area_mm2": (circle_count + ring_count) * math.pi * RADIUS_MM**2,
        "expected_contour_count": circle_count + ring_count,
        "expected_entity_count": circle_count + ring_count * 4,
    }


def nested(outer: float = 10.0, inner: float = 4.0) -> dict:
    return {
        "name": "nested_circles",
        "entities": [circle("outer", (0.0, 0.0), outer), circle("hole", (0.0, 0.0), inner)],
        "depth": DEPTH_MM,
        "expected_area_mm2": math.pi * (outer**2 - inner**2),
        "expected_contour_count": 2,
        "expected_entity_count": 2,
    }


def legal_cases() -> list[dict]:
    return [
        separated(2, "circle"),
        separated(5, "circle"),
        separated(10, "circle"),
        separated(5, "arc_ring"),
        separated(10, "arc_ring"),
        mixed(),
        nested(),
    ]


def intersecting() -> list[dict]:
    return [circle("left", (0.0, 0.0), 5.0), circle("right", (8.0, 0.0), 5.0)]


def tangent() -> list[dict]:
    return [circle("first", (0.0, 0.0), 5.0), circle("second", (10.0, 0.0), 5.0)]


def zero_area() -> list[dict]:
    return [
        {"type": "line", "name": "forward", "start": [0.0, 0.0], "end": [10.0, 0.0]},
        {"type": "line", "name": "backward", "start": [10.0, 0.0], "end": [0.0, 0.0]},
    ]


def self_intersecting() -> list[dict]:
    points = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0), (0.0, 0.0)]
    return [
        {"type": "line", "name": f"edge{index}", "start": list(a), "end": list(b)}
        for index, (a, b) in enumerate(zip(points, points[1:]))
    ]


def near_tolerance(gap: float = 1e-6) -> list[dict]:
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, gap)]
    return [
        {"type": "line", "name": f"side{index}", "start": list(a), "end": list(b)}
        for index, (a, b) in enumerate(zip(points, points[1:]))
    ]


def open_chain() -> list[dict]:
    return [{"type": "line", "name": "rail", "start": [0.0, 0.0], "end": [40.0, 0.0]}]


INVALID = {
    "intersecting": intersecting,
    "tangent": tangent,
    "zero_area": zero_area,
    "self_intersecting": self_intersecting,
    "near_tolerance": near_tolerance,
}
