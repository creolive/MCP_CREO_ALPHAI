"""Surface-chain operation schemas (FEAT-039 S02/S03/S04/S07).

The trim, merge and projection operators live here instead of inside the
general schema module, so the package owns the surface chain by name. The
shared primitives come from creo_mechdog.schema_base; the general module
re-exports these classes, so both import paths stay valid.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from creo_mechdog.schema_base import Label, Positive, StrictModel


def quilt_reference_problem(
    reference: Any, *, allow_datum_plane: bool, allow_curve: bool = False
) -> str | None:
    """FEAT-039/S02: describe why a surface_trim reference is unusable.

    Quilt references are always accepted; a datum plane and a curve are
    trimming tools only, so they are opt-in. A curve is passed as the geometry
    item (`{kind: curve, id: N}`) because that is what the use-curve tree
    consumes; a curve feature label would name the parent sketch instead.
    """
    if not isinstance(reference, dict):
        return "must be a single {kind:...} reference object"
    kind = reference.get("kind")
    if kind is None:
        return "must carry a kind"
    if kind == "quilt":
        value = reference.get("id")
        if type(value) is not int or value < 0:
            return "quilt reference requires a nonnegative integer id"
        return None
    if kind == "quilt_feature":
        if not isinstance(reference.get("label"), str) or not reference["label"]:
            return "quilt_feature reference requires a label"
        return None
    if allow_datum_plane and kind == "datum_plane":
        if not isinstance(reference.get("label"), str) or not reference["label"]:
            return "datum_plane reference requires a label"
        return None
    if allow_curve and kind == "curve":
        value = reference.get("id")
        if type(value) is not int or value < 0:
            return "curve reference requires a nonnegative integer id"
        return None
    return f"unsupported kind '{kind}'"


class SurfaceTrimOp(StrictModel):
    """High-level surface trim (FEAT-039/S02).

    The target is one quilt; the tool is one quilt, one datum plane or one
    curve. Bodies and multiple tools are refused before a job is queued. For a
    curve tool ProTrim.h defines the two sides along the curve direction, which
    the 2026-11-04 probe measured: reversing the curve swaps the retained
    region, so ``kept_side_basis`` reports ``side_reference=curve_direction``.
    ``keep_side``
    is ``one``/``two`` only — its physical direction is read back through
    ``kept_side_basis`` instead of being named after a GUI view.
    """

    op: Literal["surface_trim"]
    label: Label
    target: dict[str, Any]
    tool: dict[str, Any]
    keep_side: Literal["one", "two"]
    # FEAT-039/S07: the documented thin-trim route offsets the trimming
    # surface by a distance before it cuts (ProTrim.h §4.1). The distance and
    # its direction are given explicitly, never derived from a GUI view.
    offset_mm: Positive | None = None
    offset_side: Literal["one", "two"] | None = None

    @model_validator(mode="after")
    def valid_references(self):
        problem = quilt_reference_problem(self.target, allow_datum_plane=False)
        if problem:
            raise ValueError(f"surface_trim target {problem}")
        problem = quilt_reference_problem(self.tool, allow_datum_plane=True, allow_curve=True)
        if problem:
            raise ValueError(f"surface_trim tool {problem}")
        # The same reference object cannot be both sides of the trim. Two
        # different spellings of one quilt are caught at run time by the native
        # resolver, which already refuses ambiguous quilt references.
        if self.target == self.tool:
            raise ValueError(
                "surface_trim target and tool must be distinct quilts; one quilt cannot trim itself"
            )
        if (self.offset_mm is None) != (self.offset_side is None):
            raise ValueError("surface_trim offset_mm and offset_side must be given together")
        if self.offset_mm is not None and self.tool.get("kind") == "curve":
            raise ValueError(
                "surface_trim offset applies to the use-quilt trimming variant; a curve "
                "tool has no surface to offset"
            )
        return self


class SurfaceLoftOp(StrictModel):
    """Minimal two-section boundary blend (FEAT-009/H02).

    Exactly two sections, each one MCP-owned sketch that owns one
    non-composite curve, and straight interpolation only. Multi-section,
    smooth, closed and continuity requests are refused before a job exists; the
    operator never falls back to a solid Blend.
    """

    op: Literal["surface_loft"]
    label: Label
    sections: Annotated[list[str | int], Field(min_length=2, max_length=2)]
    interpolation: Literal["straight"] = "straight"

    @field_validator("sections", mode="before")
    @classmethod
    def normalize_section_ids(cls, values: Any) -> Any:
        # Same public-client tolerance as LoftOp: digit-only strings are
        # integer feature IDs, because a label must start with a letter.
        if isinstance(values, list):
            values = [
                int(value) if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) else value
                for value in values
            ]
            if any(type(value) is int and not 0 <= value <= 2147483647 for value in values):
                raise ValueError("Surface loft section IDs must be nonnegative 32-bit integers")
            if any(isinstance(value, bool) for value in values):
                raise ValueError("Surface loft section IDs cannot be booleans")
        return values

    @model_validator(mode="after")
    def two_distinct_sections(self):
        if len(self.sections) != len(set(self.sections)):
            raise ValueError("Surface loft sections must be two distinct sketches")
        return self


class QuiltMergeOp(StrictModel):
    """Surface merge of two quilts (FEAT-039/S03).

    The first release is the documented ProMerge.h join of exactly two quilts.
    No tolerance and no intersect variant are accepted: an unproved tolerance
    would just be ignored by the SDK tree, and intersect is not this op's
    semantics.
    """

    op: Literal["quilt_merge"]
    label: Label
    target: dict[str, Any]
    tool: dict[str, Any]

    @model_validator(mode="after")
    def two_distinct_quilts(self):
        for field, reference in (("target", self.target), ("tool", self.tool)):
            problem = quilt_reference_problem(reference, allow_datum_plane=False)
            if problem:
                raise ValueError(f"quilt_merge {field} {problem}")
        if self.target == self.tool:
            raise ValueError(
                "quilt_merge target and tool must be distinct quilts; a quilt cannot be "
                "merged with itself"
            )
        return self


def _curve_reference_problem(reference: Any) -> str | None:
    """FEAT-039/S04: describe why a projection source is unusable.

    The source is one ``PRO_CURVE`` geometry id from
    ``creo_inspect_model``; a feature label is not accepted because a sketch
    feature may own several curves and the projection would have to pick one.
    """
    if not isinstance(reference, dict):
        return "must be a single {kind:...} reference object"
    kind = reference.get("kind")
    if kind is None:
        return "must carry a kind"
    if kind != "curve":
        return f"must be {{kind:'curve',id:<int>}}, not kind '{kind}'"
    value = reference.get("id")
    if type(value) is not int or not 0 <= value <= 2147483647:
        return "curve reference requires a nonnegative 32-bit integer id"
    return None


def _direction_reference_problem(reference: Any) -> str | None:
    """FEAT-039/S04: describe why a projection direction is unusable.

    Only references that yield a real vector are accepted: a datum plane or
    datum axis feature label, or a straight curve id. ``datum_plane`` labels are
    refused because the resolver drops the label and falls back to the default
    axis filter (live 2026-11-04, S02); a raw vector is refused because the
    reported side would then have no measurable basis.
    """
    if not isinstance(reference, dict):
        return "must be a single {kind:...} reference object"
    kind = reference.get("kind")
    if kind is None:
        return "must carry a kind"
    if kind in ("datum_feature", "datum_axis_feature"):
        label = reference.get("label")
        if not isinstance(label, str) or not label:
            return f"{kind} reference requires a label"
        return None
    if kind == "curve":
        value = reference.get("id")
        if type(value) is not int or not 0 <= value <= 2147483647:
            return "curve direction reference requires a nonnegative 32-bit integer id"
        return None
    if kind == "datum_plane":
        return (
            "must not be {kind:'datum_plane',label:...}: that resolver drops the label and "
            "picks the default plane; use {kind:'datum_feature',label:...} for a plane feature"
        )
    return f"unsupported kind '{kind}': use datum_feature, datum_axis_feature or a curve id"


class SurfaceGroupMeasureOp(StrictModel):
    """Read-only group-level boundary measurement (FEAT-039/H04).

    The group is one or more quilts; every member face is part of it. Per-quilt
    ``closed`` (ProQuiltVolumeEval) cannot say whether two members are joined,
    slightly apart or overlapping, so the native side measures boundary edges,
    seam gaps and overlapping face area separately. ``tolerance_mm`` is the
    join/flush tolerance (0.01 mm by default); ``gap_search_mm`` is the widest
    boundary-to-boundary distance still reported as a seam gap (1 mm by
    default). Gaps wider than that are exposed boundary, not a measured gap.
    """

    op: Literal["surface_group_measure"]
    references: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=8)]
    tolerance_mm: Positive = 0.01
    gap_search_mm: Positive = 1.0

    @model_validator(mode="after")
    def valid_references(self):
        for index, reference in enumerate(self.references):
            problem = quilt_reference_problem(reference, allow_datum_plane=False)
            if problem:
                raise ValueError(f"surface_group_measure references[{index}] {problem}")
        if len({repr(sorted(reference.items())) for reference in self.references}) != len(
            self.references
        ):
            raise ValueError("surface_group_measure references must be distinct quilts")
        if self.gap_search_mm < self.tolerance_mm:
            raise ValueError(
                "surface_group_measure gap_search_mm must be at least tolerance_mm; a gap "
                "search narrower than the join tolerance could never report a gap"
            )
        return self


class ProjectCurveOp(StrictModel):
    """Project one curve onto one quilt along an explicit direction (FEAT-039/S04).

    Exactly one quilt target, exactly one curve source and one direction
    reference. ``side`` only flips the direction read from ``direction_ref``;
    which side is "positive" is measured on hardware, never named after a GUI
    view. A multi-branch projection is refused at run time by the native side
    instead of being reported as one curve.
    """

    op: Literal["project_curve"]
    label: Label
    target: dict[str, Any]
    source: dict[str, Any]
    direction_ref: dict[str, Any]
    side: Literal["positive", "negative"] = "positive"

    @model_validator(mode="after")
    def valid_references(self):
        problem = quilt_reference_problem(self.target, allow_datum_plane=False)
        if problem:
            raise ValueError(f"project_curve target {problem}")
        problem = _curve_reference_problem(self.source)
        if problem:
            raise ValueError(f"project_curve source {problem}")
        problem = _direction_reference_problem(self.direction_ref)
        if problem:
            raise ValueError(f"project_curve direction_ref {problem}")
        return self


class SurfaceRoundOp(StrictModel):
    """Constant round on the edge shared by two member faces of one quilt.

    DEV-074/H08 measured this route on hardware: ``PRO_FEAT_ROUND`` with
    ``PRO_ROUND_REF_SURF_SURF`` keeps the result on the same quilt. The
    reference set uses the same shape the generic round already takes
    (``[{"surfaces": [{kind:"surface",id:N}, {kind:"surface",id:M}]}]``), so
    one operation has exactly one set and exactly two faces. An edge chain, a
    second set, variable radii, full/chordal/through-curve radii and custom
    transitions have no field here and are refused before a job exists.

    The pair must be two distinct member faces of the target quilt. Face
    membership is checked natively against the quilt's own face visit, which
    also refuses a solid face or another quilt's face. Adjacency (sharing one
    edge) is deliberately left to the kernel: the 2026-11-08 hardware probe
    showed a non-adjacent pair failing regeneration with a full rollback, so a
    guessed topology test here would only second-guess the kernel.
    """

    op: Literal["surface_round"]
    label: Label
    target: dict[str, Any]
    references: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=1)]
    radius: Positive

    @field_validator("radius", mode="before")
    @classmethod
    def radius_is_a_number(cls, value: Any) -> Any:
        # Pydantic would accept True as 1.0 and "3" as 3.0; a radius is a real
        # number, not a boolean or a string.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("surface_round radius must be a finite value greater than zero")
        return value

    @model_validator(mode="after")
    def one_constant_surface_pair(self):
        problem = quilt_reference_problem(self.target, allow_datum_plane=False)
        if problem:
            raise ValueError(f"surface_round target {problem}")
        if len(self.references) != 1:
            raise ValueError(
                "surface_round accepts exactly one {'surfaces':[...]} reference set; "
                "multiple sets are not supported"
            )
        reference = self.references[0]
        if not isinstance(reference, dict):
            raise ValueError("surface_round references[0] must be a {'surfaces':[...]} object")
        if set(reference) != {"surfaces"}:
            raise ValueError(
                "surface_round references[0] accepts only the 'surfaces' key; edge chains, "
                "variable radii and transitions are not supported"
            )
        faces = reference.get("surfaces")
        if not isinstance(faces, list) or len(faces) != 2:
            raise ValueError(
                "surface_round requires exactly two member faces as "
                "{'surfaces':[{kind:'surface',id:N}, {kind:'surface',id:M}]}"
            )
        ids = set()
        for index, face in enumerate(faces):
            if not isinstance(face, dict) or face.get("kind") != "surface":
                raise ValueError(
                    f"surface_round faces[{index}] must be {{kind:'surface',id:N}}; an edge, "
                    "a plane or a body is not a member face"
                )
            if set(face) != {"kind", "id"}:
                raise ValueError(
                    f"surface_round faces[{index}] accepts only kind and id; a face id is "
                    "the geometry id from creo_inspect_model, not a feature label"
                )
            value = face.get("id")
            if type(value) is not int or not 0 <= value <= 2147483647:
                raise ValueError(
                    f"surface_round faces[{index}].id must be a nonnegative 32-bit integer"
                )
            ids.add(value)
        if len(ids) != 2:
            raise ValueError("surface_round faces must be two distinct surfaces")
        return self
