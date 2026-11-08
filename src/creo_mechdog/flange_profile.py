"""Offline flange section admission; coordinates are mm and angles degrees.

Analytic intersections are used (never chord sampling). Coincident circles are
conservatively refused, including disjoint arcs, until overlap topology is proven.
All input scalars are bounded to +/-1e6 to keep intersection arithmetic finite.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal, Union

from pydantic import BeforeValidator, Field, model_validator

from creo_mechdog.schema_base import Label, StrictModel

TOL = 1e-8


def _number(v):
    if type(v) not in (float, int) or abs(v) > 1e6 or not math.isfinite(v):
        raise ValueError("finite numbers within +/-1e6 required; bool is forbidden")
    return v


Number = Annotated[float, BeforeValidator(_number)]
Point = Annotated[list[Number], Field(min_length=2, max_length=2)]


def _direction(v):
    if type(v) is not int or v not in (-1, 1):
        raise ValueError("dir must be strict integer +1 or -1")
    return v


class FlangeLine(StrictModel):
    type: Literal["line"]
    name: Label
    start: Point
    end: Point


class FlangeArc(StrictModel):
    type: Literal["arc"]
    name: Label
    center: Point
    radius: Annotated[Number, Field(gt=1e-8, le=100000)]
    start_angle: Number
    end_angle: Number
    dir: Annotated[int, BeforeValidator(_direction)] = 1

    @model_validator(mode="after")
    def sweep_valid(self):
        if self.sweep < 1e-8:
            raise ValueError("arc sweep must be between zero and 360 degrees")
        return self

    @property
    def sweep(self):
        return ((self.end_angle - self.start_angle) * self.dir) % 360

    def at(self, angle):
        a = math.radians(angle)
        return [
            self.center[0] + self.radius * math.cos(a),
            self.center[1] + self.radius * math.sin(a),
        ]

    @property
    def start(self):
        return self.at(self.start_angle)

    @property
    def end(self):
        return self.at(self.end_angle)


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1]]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _on(e, p):
    if isinstance(e, FlangeLine):
        d, q = _sub(e.end, e.start), _sub(p, e.start)
        return abs(_cross(d, q)) <= TOL * math.hypot(*d) and -TOL <= _dot(q, d) <= _dot(d, d) + TOL
    if abs(math.dist(p, e.center) - e.radius) > TOL:
        return False
    angle = math.degrees(math.atan2(p[1] - e.center[1], p[0] - e.center[0]))
    sweep = ((angle - e.start_angle) * e.dir) % 360
    return sweep <= e.sweep + TOL or 360 - sweep <= TOL


def _intersections(a, b):
    if isinstance(a, FlangeArc) and isinstance(b, FlangeLine):
        return _intersections(b, a)
    if isinstance(a, FlangeLine) and isinstance(b, FlangeLine):
        d, f, q = _sub(a.end, a.start), _sub(b.end, b.start), _sub(b.start, a.start)
        den = _cross(d, f)
        if den == 0:
            points = [p for p in (a.start, a.end, b.start, b.end) if _on(a, p) and _on(b, p)]
            return points
        t = _cross(q, f) / den
        candidates = [[a.start[0] + t * d[0], a.start[1] + t * d[1]]]
    elif isinstance(a, FlangeLine):
        d, q = _sub(a.end, a.start), _sub(a.start, b.center)
        aa, bb = _dot(d, d), 2 * _dot(q, d)
        disc = bb * bb - 4 * aa * (_dot(q, q) - b.radius * b.radius)
        if disc < -TOL:
            return []
        roots = [(-bb + s * math.sqrt(max(0, disc))) / (2 * aa) for s in (-1, 1)]
        candidates = [[a.start[0] + t * d[0], a.start[1] + t * d[1]] for t in roots]
    else:
        d = math.dist(a.center, b.center)
        if d <= TOL:
            if abs(a.radius - b.radius) <= TOL:
                raise ValueError("coincident-circle arcs are not supported offline")
            return []
        if d > a.radius + b.radius + TOL or d < abs(a.radius - b.radius) - TOL:
            return []
        x = (a.radius * a.radius - b.radius * b.radius + d * d) / (2 * d)
        h = math.sqrt(max(0, a.radius * a.radius - x * x))
        ux, uy = ((b.center[i] - a.center[i]) / d for i in (0, 1))
        candidates = [
            [a.center[0] + x * ux - s * h * uy, a.center[1] + x * uy + s * h * ux] for s in (-1, 1)
        ]
    return [p for p in candidates if _on(a, p) and _on(b, p)]


class FlangeProfile(StrictModel):
    entities: Annotated[
        list[Annotated[Union[FlangeLine, FlangeArc], Field(discriminator="type")]],
        Field(min_length=2, max_length=32),
    ]

    @model_validator(mode="after")
    def topology(self):
        if math.dist(self.entities[0].start, [0, 0]) > TOL:
            raise ValueError("profile must start at [0,0]")
        if len({e.name for e in self.entities}) != len(self.entities):
            raise ValueError("entity names must be unique")
        for i, e in enumerate(self.entities):
            if math.dist(e.start, e.end) <= TOL:
                raise ValueError("zero-length entity or closed arc")
            if i and math.dist(self.entities[i - 1].end, e.start) > TOL:
                raise ValueError("profile must be an ordered continuous open chain")
            for j, previous in enumerate(self.entities[:i]):
                for point in _intersections(previous, e):
                    if j != i - 1 or math.dist(point, e.start) > TOL:
                        raise ValueError("profile self-intersects, overlaps or closes")
        return self

    @property
    def extent(self):
        # Conservative request bound, never an observed physical wall height.
        return max(
            max(math.hypot(*e.start), math.hypot(*e.end))
            if isinstance(e, FlangeLine)
            else math.hypot(*e.center) + e.radius
            for e in self.entities
        )

    def to_profile(self):
        return dict(profile=[e.model_dump() for e in self.entities], dimensions=[], constraints=[])
