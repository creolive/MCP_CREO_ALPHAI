"""Schemas for general feature operations. Each operation is validated before queuing."""

from __future__ import annotations

import math
import re
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from creo_mechdog.profile_diagnostics import validate_solid_profile
from creo_mechdog.references import (
    PatternAxis,
    RevolveAxis,
    validate_planar_reference,
    validate_sketch_plane_frame,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


Point2 = Annotated[list[float], Field(min_length=2, max_length=2)]
Point3 = Annotated[list[float], Field(min_length=3, max_length=3)]
_LABEL_PATTERN = r"^[a-z][a-z0-9_]{0,27}$"


def _explain_label_pattern(value: Any, handler: ValidatorFunctionWrapHandler) -> str:
    try:
        return handler(value)
    except ValidationError as exc:
        if any(error["type"] == "string_pattern_mismatch" for error in exc.errors()):
            raise PydanticCustomError(
                "string_pattern_mismatch",
                "Label must start with a lowercase letter, contain only [a-z0-9_], "
                "and be at most 28 characters; for example i001_part1",
                {"pattern": _LABEL_PATTERN},
            ) from None
        raise


Label = Annotated[str, Field(pattern=_LABEL_PATTERN), WrapValidator(_explain_label_pattern)]
Positive = Annotated[float, Field(gt=0, le=100000)]


def _rotation_matrix(value: Any) -> Any:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("rotation_matrix must be a nested 3x3 array")
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("rotation_matrix must be a nested 3x3 array")
        if any(type(v) not in (int, float) or not -math.inf < v < math.inf for v in row):
            raise ValueError("rotation_matrix requires finite real numbers")
    for i in range(3):
        for j in range(3):
            dot = sum(value[i][k] * value[j][k] for k in range(3))
            if abs(dot - (i == j)) > 1e-6 or not math.isfinite(dot):
                raise ValueError("rotation_matrix must be orthogonal within 1e-6")
    a, b, c = value
    determinant = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if abs(determinant - 1) > 1e-6:
        raise ValueError("rotation_matrix determinant must be +1 within 1e-6")
    return value


RotationMatrix = Annotated[
    list[Point3], Field(min_length=3, max_length=3), BeforeValidator(_rotation_matrix)
]


class AssemblyPose(StrictModel):
    translation: Point3 = [0, 0, 0]
    rotation: Point3 | None = None
    rotation_matrix: RotationMatrix | None = None

    @model_validator(mode="after")
    def orientation_valid(self):
        if self.rotation_matrix is not None:
            if self.rotation is not None:
                raise ValueError("rotation and rotation_matrix are mutually exclusive")
        elif self.rotation is None:
            self.rotation = [0, 0, 0]
        return self


def _normalize_sketch_ref(value: Any) -> Any:
    # Some public clients stringify the integer branch of str|int anyOf
    # (BUG-073); digit-only strings cannot be feature labels (labels start
    # with a letter), so normalize them to feature IDs like LoftOp does.
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    if type(value) is int and not 0 <= value <= 2147483647:
        raise ValueError("Sketch feature IDs must be nonnegative 32-bit integers")
    return value


SketchRef = Annotated[str | int, BeforeValidator(_normalize_sketch_ref)]


class Line(StrictModel):
    type: Literal["line", "centerline"]
    name: Label
    start: Point2
    end: Point2
    construction: bool = False

    @model_validator(mode="after")
    def nonzero(self):
        if math.dist(self.start, self.end) < 1e-8:
            raise ValueError("Line endpoints coincide")
        return self


class Circle(StrictModel):
    type: Literal["circle"]
    name: Label
    center: Point2
    radius: Positive
    construction: bool = False


class Arc(Circle):
    type: Literal["arc"]
    start_angle: float
    end_angle: float

    @model_validator(mode="after")
    def span(self):
        if abs((self.end_angle - self.start_angle) % 360) < 1e-10:
            raise ValueError("Arc requires distinct endpoints; use circle for a complete circle")
        return self


class Polyline(StrictModel):
    type: Literal["polyline", "spline"]
    name: Label
    points: Annotated[list[Point2], Field(min_length=2, max_length=200)]
    closed: bool = False
    construction: bool = False

    @model_validator(mode="after")
    def distinct_points(self):
        if any(math.dist(a, b) < 1e-8 for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Consecutive polyline/spline points must be distinct")
        if self.closed and len(self.points) < 3:
            raise ValueError("Closed profiles need at least three points")
        if (
            self.type == "polyline"
            and self.closed
            and math.dist(self.points[0], self.points[-1]) < 1e-8
        ):
            raise ValueError("With closed=true omit the duplicated final point")
        return self


class Rectangle(StrictModel):
    type: Literal["rectangle"]
    name: Label
    min: Point2
    max: Point2
    construction: bool = False

    @model_validator(mode="after")
    def corners(self):
        if self.max[0] <= self.min[0] or self.max[1] <= self.min[1]:
            raise ValueError("Rectangle max must exceed min")
        return self


class Ellipse(StrictModel):
    type: Literal["ellipse"]
    name: Label
    center: Point2
    x_radius: Positive
    y_radius: Positive
    construction: bool = False


Entity = Annotated[
    Union[Line, Circle, Arc, Polyline, Rectangle, Ellipse], Field(discriminator="type")
]


class EntityRef(StrictModel):
    entity: str
    point: Literal["whole", "start", "end", "center"] = "whole"


class SketchDimension(StrictModel):
    name: Label
    type: Literal[
        "length",
        "radius",
        "diameter",
        "distance",
        "horizontal",
        "vertical",
        "line_distance",
        "angle",
        "arc_angle",
        "ellipse_x_radius",
        "ellipse_y_radius",
    ]
    refs: Annotated[list[EntityRef], Field(min_length=1, max_length=3)]
    value: Positive
    position: Point2 = [0, 0]


class SketchConstraint(StrictModel):
    type: Literal[
        "coincident",
        "horizontal",
        "vertical",
        "point_on",
        "tangent",
        "perpendicular",
        "equal_radius",
        "parallel",
        "equal_length",
        "collinear",
    ]
    refs: Annotated[list[EntityRef], Field(min_length=1, max_length=2)]


class SketchOp(StrictModel):
    op: Literal["sketch"]
    label: Label
    plane: Literal["XY", "XZ", "YZ"] | dict[str, Any] = "XY"
    offset: float = 0
    entities: Annotated[list[Entity], Field(min_length=1, max_length=500)]
    dimensions: list[SketchDimension] = []
    constraints: list[SketchConstraint] = []
    dimensioning: Literal["auto", "autodim", "coordinates"] = "auto"

    @model_validator(mode="after")
    def entities_unique(self):
        if self.dimensioning == "coordinates":
            if self.dimensions or self.constraints:
                raise ValueError(
                    "Coordinate dimensioning cannot be combined with supplied dimensions/constraints"
                )
            if any(
                e.type not in {"line", "centerline", "rectangle", "polyline", "circle", "arc"}
                for e in self.entities
            ):
                raise ValueError(
                    "Coordinate dimensioning supports line/centerline/rectangle/polyline/circle/arc entities"
                )
        names = [e.name for e in self.entities]
        if len(names) != len(set(names)):
            raise ValueError("Sketch entity names must be unique")
        if sum(e.type == "centerline" for e in self.entities) > 1:
            raise ValueError("One revolve centerline is supported per sketch")
        expanded = []
        for entity in self.entities:
            if entity.type == "rectangle":
                expanded += [entity.name + "_" + str(i) for i in range(4)]
            elif entity.type == "polyline":
                expanded += [
                    entity.name + "_" + str(i)
                    for i in range(len(entity.points) - 1 + int(entity.closed))
                ]
            else:
                expanded.append(entity.name)
        if len(expanded) != len(set(expanded)):
            raise ValueError("Expanded sketch entity names collide")
        for item in [*self.dimensions, *self.constraints]:
            for ref in item.refs:
                if ref.entity not in expanded:
                    raise ValueError(f"Unknown sketch entity reference: {ref.entity}")
        if len({d.name for d in self.dimensions}) != len(self.dimensions):
            raise ValueError("Dimension names must be unique")
        return self


class AirfoilProfile(StrictModel):
    chord: Positive
    thickness_ratio: Annotated[float, Field(ge=0.01, le=0.4)] = 0.12
    twist_deg: Annotated[float, Field(ge=-180, le=180)] = 0
    origin: Point2 = [0, 0]
    pivot_fraction: Annotated[float, Field(ge=0, le=1)] = 0.25
    points_per_side: Annotated[int, Field(ge=9, le=100)] = 41


class AirfoilValues(StrictModel):
    chord: Positive | None = None
    thickness_ratio: Annotated[float, Field(ge=0.01, le=0.4)] | None = None
    twist_deg: Annotated[float, Field(ge=-180, le=180)] | None = None
    origin: Point2 | None = None
    pivot_fraction: Annotated[float, Field(ge=0, le=1)] | None = None


class AirfoilStation(AirfoilProfile):
    offset: float


class AirfoilSketchOp(StrictModel):
    op: Literal["airfoil_sketch"]
    label: Label
    plane: Literal["XY", "XZ", "YZ"] | dict[str, Any] = "XY"
    offset: float = 0
    profile: AirfoilProfile


class AirfoilUpdateOp(StrictModel):
    op: Literal["update_airfoil"]
    sketch: Label
    values: AirfoilValues

    @model_validator(mode="after")
    def nonempty(self):
        if not self.values.model_dump(exclude_none=True):
            raise ValueError("At least one airfoil parameter must be supplied")
        return self


class SketchGeometryOp(StrictModel):
    op: Literal["update_sketch_geometry"]
    sketch: Label
    entities: Annotated[list[Entity], Field(min_length=1, max_length=500)]
    dimensioning: Literal["auto", "autodim", "coordinates"] = "auto"

    @model_validator(mode="after")
    def supported_entities(self):
        if any(
            e.type
            not in {
                "line",
                "centerline",
                "polyline",
                "rectangle",
                "circle",
                "arc",
                "ellipse",
                "spline",
            }
            for e in self.entities
        ):
            raise ValueError(
                "In-place editing supports line, centerline, polyline, rectangle, circle, arc, ellipse and spline"
            )
        SketchOp(
            op="sketch", label="replacement", entities=self.entities, dimensioning=self.dimensioning
        )
        return self


class FeatureGroupOp(StrictModel):
    op: Literal["feature_group"]
    label: Label
    features: Annotated[list[str | int], Field(min_length=1, max_length=200)]
    include_between: bool = False
    include_support_planes: bool = True


class ReorderOp(StrictModel):
    op: Literal["reorder_features"]
    features: Annotated[list[str | int], Field(min_length=1, max_length=200)]
    before: str | int | None = None
    after: str | int | None = None

    @model_validator(mode="after")
    def one_position(self):
        if (self.before is None) == (self.after is None):
            raise ValueError("Supply exactly one of before or after")
        return self


class AxisPatternOp(StrictModel):
    op: Literal["axis_pattern"]
    label: Label
    leader: str | int
    axis: PatternAxis
    count: Annotated[int, Field(ge=2, le=360)] = 2
    increment_deg: Annotated[float, Field(gt=-360, le=360)] = 180

    @model_validator(mode="after")
    def nonzero_angle(self):
        if abs(self.increment_deg) < 1e-8:
            raise ValueError("Pattern angular increment must be nonzero")
        return self


class GeometryTransformOp(StrictModel):
    op: Literal["geometry_transform"]
    label: Label
    references: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=100)]
    translation: Point3 = [0, 0, 0]
    rotation: Point3 = [0, 0, 0]
    coordinate_system: dict[str, Any] = {"kind": "default_csys"}
    keep_original: bool = False

    @model_validator(mode="after")
    def valid_transform(self):
        if all(abs(v) < 1e-9 for v in self.translation + self.rotation):
            raise ValueError("At least one translation/rotation must be nonzero")
        kinds = {r.get("kind") for r in self.references}
        if "body" in kinds and kinds != {"body"}:
            raise ValueError("Body and quilt/datum transformations cannot be mixed")
        if not kinds <= {
            "body",
            "quilt",
            "quilt_feature",
            "curve",
            "axis",
            "point",
            "csys",
            "datum_feature",
            "datum_axis_feature",
            "datum_csys_feature",
            "datum_point_feature",
        }:
            raise ValueError("Transform accepts whole bodies or supported quilts/datums/curves")
        if self.coordinate_system.get("kind") not in {"default_csys", "csys", "datum_csys_feature"}:
            raise ValueError("Transformation frame must be a coordinate system")
        if any(abs(v) > 100000 for v in self.translation) or any(
            abs(v) > 360 for v in self.rotation
        ):
            raise ValueError("Translation/rotation is outside the supported range")
        return self


class TransformUpdateOp(StrictModel):
    op: Literal["set_geometry_transform"]
    feature: Label
    translation: Point3
    rotation: Point3

    @model_validator(mode="after")
    def bounded_values(self):
        if any(abs(v) > 100000 for v in self.translation) or any(
            abs(v) > 360 for v in self.rotation
        ):
            raise ValueError("Translation/rotation is outside the supported range")
        return self


class ExtrudeOp(StrictModel):
    op: Literal["extrude"]
    label: Label
    sketch: SketchRef
    depth: Positive = 1
    mode: Literal["add", "cut", "surface"] = "add"
    direction: Literal["positive", "negative", "symmetric"] = "positive"
    depth_type: Literal["blind", "through_all"] = "blind"
    new_body: bool = False
    thin: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def through_cut(self):
        if self.depth_type == "through_all" and self.mode != "cut":
            raise ValueError("through_all is supported for cuts")
        return self


class RevolveOp(StrictModel):
    op: Literal["revolve"]
    label: Label
    sketch: SketchRef
    angle: Annotated[float, Field(gt=0, le=360)] = 360
    mode: Literal["add", "cut", "surface"] = "add"
    direction: Literal["positive", "negative", "symmetric"] = "positive"
    axis: RevolveAxis | None = None
    new_body: bool = False
    thin: float | None = Field(default=None, gt=0)


class HoleOp(StrictModel):
    op: Literal["hole"]
    label: Label
    placement: dict[str, Any]
    reference1: dict[str, Any]
    reference2: dict[str, Any]
    offset1: float = 0
    offset2: float = 0
    diameter: Positive
    depth: Positive | None = None
    flip: bool = False


class RoundOp(StrictModel):
    op: Literal["round", "chamfer"]
    label: Label
    size: Annotated[
        Positive | None,
        Field(
            default=None,
            description="Constant fillet radius or chamfer leg distance in mm; "
            "round also accepts the radius alias and chamfer the distance alias",
        ),
    ]
    radius: Annotated[
        Positive | None,
        Field(
            default=None,
            exclude=True,
            description="Alias for size when op=round (mm); rejected when size is also given",
        ),
    ]
    distance: Annotated[
        Positive | None,
        Field(
            default=None,
            exclude=True,
            description="Alias for size when op=chamfer (mm); rejected when size is also given",
        ),
    ]
    references: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def resolve_size(self):
        # Standalone-tool compatibility: round accepts radius and chamfer accepts
        # distance as an alias for size. Aliases are excluded from serialization,
        # so the native request always carries a single size field.
        alias, other = ("radius", "distance") if self.op == "round" else ("distance", "radius")
        if getattr(self, other) is not None:
            raise ValueError(f"op '{self.op}' does not accept '{other}'; use '{alias}' or 'size'")
        if self.size is not None and getattr(self, alias) is not None:
            raise ValueError(f"Provide either '{alias}' or 'size' for op '{self.op}', not both")
        if self.size is None:
            if getattr(self, alias) is None:
                raise ValueError(f"Provide 'size' or '{alias}' for op '{self.op}'")
            self.size = getattr(self, alias)
        return self


class PlaneOp(StrictModel):
    op: Literal["datum_plane"]
    label: Label
    reference: dict[str, Any]
    offset: float = 0
    angle: float | None = Field(default=None, ge=-360, le=360)
    axis: dict[str, Any] | None = None


class AxisOp(StrictModel):
    op: Literal["datum_axis"]
    label: Label
    references: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=2)]


class ShellOp(StrictModel):
    op: Literal["shell"]
    label: Label
    thickness: Positive
    remove_surfaces: list[dict[str, Any]] = []
    outward: bool = False


class DimensionValue(StrictModel):
    id: int
    value: float


class DimensionsOp(StrictModel):
    op: Literal["set_dimensions"]
    values: Annotated[list[DimensionValue], Field(min_length=1, max_length=200)]


class SketchDimensionsOp(StrictModel):
    op: Literal["set_sketch_dimensions"]
    sketch: SketchRef
    values: dict[str, float]


class ParametersOp(StrictModel):
    op: Literal["set_parameters"]
    values: dict[str, float | str | bool | int]

    @model_validator(mode="after")
    def names(self):
        for name, value in self.values.items():
            if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,30}", name):
                raise ValueError(
                    "Parameter names must be 1–31 letters/digits/_ starting with a letter"
                )
            if isinstance(value, str) and len(value) > 80:
                raise ValueError("String parameters support at most 80 characters")
        return self


class RelationsOp(StrictModel):
    op: Literal["set_relations"]
    lines: list[str]

    @model_validator(mode="after")
    def expressions(self):
        allowed = {
            "abs",
            "ceil",
            "floor",
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "atan2",
            "sqrt",
            "exp",
            "ln",
            "log",
            "mod",
            "min",
            "max",
        }
        for line in self.lines:
            if not re.fullmatch(r"\s*[a-zA-Z][a-zA-Z0-9_]*\s*=\s*[a-zA-Z0-9_ .+*/()^,\-]+", line):
                raise ValueError("Relations currently support simple arithmetic assignments")
            for fn in re.findall(r"\b([a-zA-Z][a-zA-Z0-9_]*)\s*\(", line):
                if fn.lower() not in allowed:
                    raise ValueError(f"Unsupported relation function: {fn}")
        return self


class PatternOp(StrictModel):
    op: Literal["dimension_pattern"]
    label: Label
    feature: str | int
    dimension_id: int
    count: Annotated[int, Field(ge=2, le=100)]
    increment: float

    @model_validator(mode="after")
    def nonzero(self):
        if abs(self.increment) < 1e-9:
            raise ValueError("Pattern increment must be nonzero")
        return self


class MirrorOp(StrictModel):
    op: Literal["mirror"]
    label: Label
    plane: dict[str, Any]
    references: list[dict[str, Any]] = []
    keep_original: bool = True

    @model_validator(mode="after")
    def geometry_references(self):
        allowed = {
            "curve",
            "axis",
            "quilt",
            "csys",
            "point",
            "part",
            "datum_feature",
            "datum_axis_feature",
            "datum_plane",
        }
        if any(r.get("kind") not in allowed for r in self.references):
            raise ValueError(
                "Toolkit mirror supports geometry/part references, not feature-tree selections"
            )
        if any(r.get("kind") == "part" for r in self.references) and len(self.references) != 1:
            raise ValueError("Whole-part mirror cannot mix reference types")
        return self


class SweepOp(StrictModel):
    op: Literal["sweep"]
    label: Label
    trajectory: str | int | list[dict[str, Any]]
    profile: Annotated[list[Entity], Field(min_length=1, max_length=500)]
    dimensions: list[SketchDimension] = []
    constraints: list[SketchConstraint] = []
    mode: Literal["add", "cut", "surface"] = "add"
    new_body: bool = False
    thin: float | None = Field(default=None, gt=0)
    capped: bool = False

    @model_validator(mode="after")
    def profile_valid(self):
        SketchOp(
            label=self.label,
            op="sketch",
            entities=self.profile,
            dimensions=self.dimensions,
            constraints=self.constraints,
        )
        if isinstance(self.trajectory, list) and not self.trajectory:
            raise ValueError("Sweep trajectory cannot be empty")
        return self


class LoftOp(StrictModel):
    op: Literal["loft"]
    label: Label
    sections: Annotated[list[str | int], Field(min_length=2, max_length=20)]
    mode: Literal["add", "cut", "surface"] = "add"
    interpolation: Literal["straight", "smooth"] = "straight"
    new_body: bool = False

    @field_validator("sections", mode="before")
    @classmethod
    def normalize_section_ids(cls, values: Any) -> Any:
        # Some public clients stringify integer branches of anyOf. Numeric
        # strings cannot be valid feature labels (labels start with a letter).
        if isinstance(values, list):
            values = [
                int(value) if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) else value
                for value in values
            ]
            if any(type(value) is int and not 0 <= value <= 2147483647 for value in values):
                raise ValueError("Loft section feature IDs must be nonnegative 32-bit integers")
            if any(isinstance(value, bool) for value in values):
                raise ValueError("Loft section feature IDs cannot be booleans")
        return values

    @model_validator(mode="after")
    def unique_sections(self):
        if len(self.sections) != len(set(self.sections)):
            raise ValueError("Loft sections must be distinct")
        return self


class DraftOp(StrictModel):
    op: Literal["draft"]
    label: Label
    surfaces: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=200)]
    neutral_plane: dict[str, Any]
    pull_direction: dict[str, Any] | None = None
    angle: Annotated[float, Field(gt=-85, lt=85)]
    flip: bool = False
    include_tangent: bool = False

    @model_validator(mode="after")
    def nonzero_angle(self):
        if abs(self.angle) < 1e-9:
            raise ValueError("Draft angle must be nonzero")
        return self


class SheetmetalWallOp(StrictModel):
    op: Literal["sheetmetal_wall"]
    label: Label
    sketch: SketchRef
    depth: Positive
    thickness: Positive
    direction: Literal["positive", "negative"] = "positive"


class SheetmetalFlangeOp(StrictModel):
    op: Literal["sheetmetal_flange"]
    label: Label
    edge: dict[str, Any]
    height: Positive
    angle: Annotated[float, Field(gt=0, lt=180)] = 90
    radius: Positive = 1
    flip: bool = False
    y_factor: Annotated[float, Field(gt=0, le=1)] = 0.5


class SheetmetalUnbendOp(StrictModel):
    op: Literal["sheetmetal_unbend", "sheetmetal_flat_pattern", "sheetmetal_bend_back"]
    label: Label
    fixed_surface: dict[str, Any]
    references: list[dict[str, Any]] = []


class AssemblyConstraint(StrictModel):
    type: Literal["mate", "align", "mate_offset", "align_offset", "insert", "csys"]
    assembly_reference: dict[str, Any]
    component_reference: dict[str, Any]
    offset: float = 0
    assembly_side: Literal["yellow", "red", "none"] = "yellow"
    component_side: Literal["yellow", "red", "none"] = "yellow"
    # T09: explicit same-level sibling component for the assembly side. Omitted
    # means the assembly's own geometry; identity is never inferred from an
    # item_id found in another model. A digit-only string is the stringified ID
    # branch of the public label-or-ID contract (BUG-073).
    assembly_component: Any = None

    @field_validator("assembly_component", mode="before")
    @classmethod
    def valid_assembly_component(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            value = int(value)
        if type(value) is int:
            if not 0 <= value <= 2147483647:
                raise ValueError("assembly_component IDs must be nonnegative 32-bit integers")
            return value
        if isinstance(value, str) and re.fullmatch(_LABEL_PATTERN, value):
            return value
        raise ValueError(
            "assembly_component must be a component label starting with a lowercase letter "
            "([a-z0-9_], at most 28 characters) or a nonnegative feature ID"
        )


class AssembleOp(AssemblyPose):
    op: Literal["assemble_component"]
    label: Label
    source_model_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    placement: Literal["fixed", "default", "constraints"] = "fixed"
    constraints: list[AssemblyConstraint] = []
    # T09 replay plans bind the source revision and digest they were planned
    # against; admission and the native executor re-check them before use.
    rebuild_binding: dict[str, Any] | None = None

    @model_validator(mode="after")
    def placement_valid(self):
        if self.placement == "constraints" and not self.constraints:
            raise ValueError("Constraint placement needs constraints")
        if self.placement != "constraints" and self.constraints:
            raise ValueError("Use placement=constraints when providing constraints")
        return self


class ComponentPlacementOp(AssemblyPose):
    op: Literal["component_placement"]
    component: str | int


class ComponentConstraintsOp(StrictModel):
    op: Literal["component_constraints"]
    component: str | int
    constraints: Annotated[list[AssemblyConstraint], Field(min_length=1, max_length=20)]


class RemoveComponentOp(StrictModel):
    op: Literal["remove_component"]
    component: str | int


def _normalize_feature_target(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Feature targets must be feature labels or nonnegative feature IDs")
    # A label always starts with a lowercase letter, so a digit-only string is
    # the stringified ID branch of the public label-or-ID contract (BUG-073).
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    if type(value) is int and not 0 <= value <= 2147483647:
        raise ValueError("Feature targets must be nonnegative 32-bit integers")
    return value


FeatureTarget = Annotated[Label | int, BeforeValidator(_normalize_feature_target)]


class FeatureStateOp(StrictModel):
    op: Literal["feature_state"]
    action: Literal["delete", "suppress", "resume"]
    targets: Annotated[list[FeatureTarget], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def distinct_targets(self):
        keys = [("label", t) if isinstance(t, str) else ("id", t) for t in self.targets]
        if len(keys) != len(set(keys)):
            raise ValueError("feature_state targets must be distinct")
        return self


class GenericFeatureOp(StrictModel):
    op: Literal["feature_tree"]
    label: Label
    tree: dict[str, Any]

    @model_validator(mode="after")
    def valid_tree(self):
        count = 0

        def walk(node, depth=0):
            nonlocal count
            count += 1
            if depth > 40 or count > 5000:
                raise ValueError("Element tree exceeds 40 levels or 5000 nodes")
            if not isinstance(node, dict) or set(node) - {
                "id",
                "integer",
                "double",
                "string",
                "reference",
                "references",
                "curve_collection",
                "children",
            }:
                raise ValueError("Invalid element tree node fields")
            identifier = node.get("id")
            if not (
                type(identifier) is int
                or isinstance(identifier, str)
                and re.fullmatch(r"PRO_[A-Z0-9_]+", identifier)
            ):
                raise ValueError("Element id must be a native integer or SDK constant name")
            if (
                sum(
                    k in node
                    for k in (
                        "integer",
                        "double",
                        "string",
                        "reference",
                        "references",
                        "curve_collection",
                    )
                )
                > 1
            ):
                raise ValueError("Element node may have only one value type")
            if "integer" in node and not (
                type(node["integer"]) is int
                or isinstance(node["integer"], str)
                and re.fullmatch(r"PRO_[A-Z0-9_]+", node["integer"])
            ):
                raise ValueError("Invalid integer element value")
            if "double" in node and type(node["double"]) not in (float, int):
                raise ValueError("Invalid double element value")
            if "string" in node and (
                not isinstance(node["string"], str) or len(node["string"]) > 4096
            ):
                raise ValueError("Invalid string element value")
            if not isinstance(node.get("children", []), list):
                raise ValueError("Element children must be a list")
            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(self.tree)
        return self


class SimpleOp(StrictModel):
    op: Literal["regenerate", "save"]


class Assertions(StrictModel):
    require_solid: bool = False
    volume_mm3: float | None = Field(default=None, ge=0)
    volume_tolerance: float = Field(default=0.01, gt=0)


class ExportOp(StrictModel):
    op: Literal["export"]
    format: Literal["step", "stl", "iges", "jpeg", "pdf"] = "step"


class DrawingModelOp(StrictModel):
    op: Literal["drawing_model"]
    label: Label
    source_model_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]


class DrawingSheetOp(StrictModel):
    op: Literal["drawing_sheet"]
    action: Literal["add", "resize"] = "add"
    sheet: Annotated[int, Field(ge=1, le=100)] = 1
    width: Annotated[float, Field(gt=10, le=5000)] = 297
    height: Annotated[float, Field(gt=10, le=5000)] = 210
    name: Label | None = None


ViewStyle = Literal["wireframe", "hidden", "no_hidden", "shaded", "shaded_edges"]


class DrawingViewOp(StrictModel):
    op: Literal["drawing_view"]
    label: Label
    model: Label
    sheet: Annotated[int, Field(ge=1, le=100)] = 1
    position: Point2
    orientation: Literal["front", "back", "top", "bottom", "left", "right", "isometric"] = "front"
    scale: Annotated[float, Field(gt=0, le=1000)] = 1
    display: ViewStyle = "no_hidden"


class DrawingProjectionOp(StrictModel):
    op: Literal["drawing_projection"]
    label: Label
    parent: str | int
    position: Point2
    display: ViewStyle = "no_hidden"


class DrawingViewUpdateOp(StrictModel):
    op: Literal["drawing_view_update"]
    view: str | int
    scale: Annotated[float, Field(gt=0, le=1000)] | None = None
    move: Point2 | None = None
    display: ViewStyle | None = None

    @model_validator(mode="after")
    def has_change(self):
        if all(v is None for v in (self.scale, self.move, self.display)):
            raise ValueError("Specify scale, move or display")
        return self


NoteLines = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=79)]], Field(min_length=1, max_length=50)
]


class DrawingNoteOp(StrictModel):
    op: Literal["drawing_note"]
    label: Label
    sheet: Annotated[int, Field(ge=1, le=100)] = 1
    position: Point2
    lines: NoteLines
    text_height: Annotated[float, Field(gt=0, le=100)] = 3.5


class DrawingNoteUpdateOp(StrictModel):
    op: Literal["drawing_note_update"]
    note: str | int
    lines: NoteLines | None = None
    position: Point2 | None = None
    text_height: Annotated[float, Field(gt=0, le=100)] | None = None

    @model_validator(mode="after")
    def has_change(self):
        if all(v is None for v in (self.lines, self.position, self.text_height)):
            raise ValueError("Specify lines, position or text_height")
        return self


class DrawingTableOp(StrictModel):
    op: Literal["drawing_table"]
    label: Label
    sheet: Annotated[int, Field(ge=1, le=100)] = 1
    position: Point2
    columns: Annotated[list[Positive], Field(min_length=1, max_length=50)]
    row_height: Positive = 8
    cells: Annotated[
        list[list[Annotated[str, Field(max_length=79)]]], Field(min_length=1, max_length=100)
    ]

    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row) != len(self.columns) for row in self.cells):
            raise ValueError("Each table row must match the column widths")
        return self


class DrawingTableCellOp(StrictModel):
    op: Literal["drawing_table_cell"]
    table: str | int
    row: Annotated[int, Field(ge=1, le=100)]
    column: Annotated[int, Field(ge=1, le=50)]
    text: Annotated[str, Field(max_length=79)]


class DrawingDimensionOp(StrictModel):
    op: Literal["drawing_dimension"]
    label: Label
    view: str | int
    dimension_id: Annotated[int, Field(ge=0)]
    position: Point2 | None = None


class DrawingDeleteOp(StrictModel):
    op: Literal["drawing_delete"]
    kind: Literal["view", "note", "table", "dimension"]
    target: str | int

    @model_validator(mode="after")
    def dimension_label(self):
        if self.kind == "dimension" and not isinstance(self.target, str):
            raise ValueError("Use a dimension label to identify its source model")
        return self


class UdfInspectOp(StrictModel):
    op: Literal["udf_inspect"]
    file_path: Annotated[str, Field(min_length=1, max_length=250)]
    instance: Label | None = None


class UdfCreateOp(StrictModel):
    op: Literal["udf_create"]
    label: Label
    file_path: Annotated[str, Field(min_length=1, max_length=250)]
    instance: Label | None = None
    references: dict[str, dict[str, Any]]
    dimensions: dict[str, float] = {}


class DumpTreeOp(StrictModel):
    op: Literal["dump_tree"]
    feature: str | int


class CsysOp(StrictModel):
    op: Literal["datum_csys"]
    label: Label
    reference: dict[str, Any] = {"kind": "default_csys"}
    translation: Point3 = [0, 0, 0]
    rotation: Point3 = [0, 0, 0]


class DatumPoint(StrictModel):
    name: Label
    position: Point3


class PointsOp(StrictModel):
    op: Literal["datum_points"]
    label: Label
    reference: dict[str, Any] = {"kind": "default_csys"}
    points: Annotated[list[DatumPoint], Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def unique_names(self):
        if len({p.name for p in self.points}) != len(self.points):
            raise ValueError("Datum point names must be unique")
        return self


class FillOp(StrictModel):
    op: Literal["surface_fill"]
    label: Label
    sketch: SketchRef


class ThickenOp(StrictModel):
    op: Literal["thicken"]
    label: Label
    reference: dict[str, Any]
    thickness: Positive
    side: Literal["positive", "negative", "symmetric"] = "symmetric"
    mode: Literal["add", "cut"] = "add"
    new_body: bool = False


class SolidifyOp(StrictModel):
    op: Literal["solidify"]
    label: Label
    reference: dict[str, Any]
    side: Literal["positive", "negative"] = "positive"
    mode: Literal["add", "cut"] = "add"
    new_body: bool = False


class BooleanOp(StrictModel):
    op: Literal["boolean_bodies"]
    label: Label
    method: Literal["union", "subtract", "intersect"]
    targets: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=100)]
    tools: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=100)]
    keep_tools: bool = False

    @model_validator(mode="after")
    def valid_bodies(self):
        if self.method != "subtract" and len(self.targets) != 1:
            raise ValueError("Union/intersection require one target body")
        if self.method == "subtract" and len(self.tools) != 1:
            raise ValueError("Subtract requires one tool body")
        if self.method != "subtract" and self.keep_tools:
            raise ValueError("keep_tools only applies to subtraction")
        refs = [*self.targets, *self.tools]
        if any(
            r.get("kind") != "body" or type(r.get("id")) is not int or r["id"] < 0 for r in refs
        ):
            raise ValueError("Explicit body IDs are required")
        if len({r["id"] for r in refs}) != len(refs):
            raise ValueError("Target and tool bodies must be distinct")
        return self


class RibOp(StrictModel):
    op: Literal["rib"]
    label: Label
    sketch: SketchRef
    thickness: Positive
    side: Literal["positive", "negative", "symmetric"] = "symmetric"
    flip: bool = False


Operation = Annotated[
    Union[
        FeatureGroupOp,
        ReorderOp,
        AxisPatternOp,
        GeometryTransformOp,
        TransformUpdateOp,
        AirfoilSketchOp,
        AirfoilUpdateOp,
        SketchGeometryOp,
        UdfInspectOp,
        UdfCreateOp,
        SketchOp,
        ExtrudeOp,
        RevolveOp,
        HoleOp,
        RoundOp,
        PlaneOp,
        AxisOp,
        ShellOp,
        DimensionsOp,
        SketchDimensionsOp,
        ParametersOp,
        RelationsOp,
        PatternOp,
        MirrorOp,
        SweepOp,
        LoftOp,
        DraftOp,
        SheetmetalWallOp,
        SheetmetalFlangeOp,
        SheetmetalUnbendOp,
        AssembleOp,
        ComponentPlacementOp,
        ComponentConstraintsOp,
        RemoveComponentOp,
        FeatureStateOp,
        GenericFeatureOp,
        SimpleOp,
        ExportOp,
        DumpTreeOp,
        DrawingModelOp,
        DrawingSheetOp,
        DrawingViewOp,
        DrawingProjectionOp,
        DrawingViewUpdateOp,
        DrawingNoteOp,
        DrawingNoteUpdateOp,
        DrawingTableOp,
        DrawingTableCellOp,
        DrawingDimensionOp,
        DrawingDeleteOp,
        CsysOp,
        PointsOp,
        FillOp,
        ThickenOp,
        SolidifyOp,
        BooleanOp,
        RibOp,
    ],
    Field(discriminator="op"),
]
OPERATIONS = TypeAdapter(list[Operation])


def validate_operations(operations: list[dict]) -> list[dict]:
    if not 0 <= len(operations) <= 200:
        raise ValueError("A plan supports at most 200 operations")
    result = OPERATIONS.validate_python(operations)
    labels = [x.label for x in result if hasattr(x, "label")]
    if len(labels) != len(set(labels)):
        raise ValueError("Feature labels must be unique within a plan")
    dumped = [x.model_dump(exclude_none=True) for x in result]

    def finite(x):
        if isinstance(x, float) and not math.isfinite(x):
            raise ValueError("All numeric values must be finite")
        if isinstance(x, list):
            for v in x:
                finite(v)
        if isinstance(x, dict):
            for v in x.values():
                finite(v)

    finite(dumped)
    for index, operation in enumerate(dumped):
        if operation["op"] in ("sketch", "airfoil_sketch") and isinstance(operation["plane"], dict):
            validate_sketch_plane_frame(operation["plane"], f"operations[{index}].plane")

    def references(x, path: str):
        if isinstance(x, list):
            for index, v in enumerate(x):
                references(v, f"{path}[{index}]")
        if isinstance(x, dict):
            if "kind" in x:
                k = x["kind"]
                if k in ("surface", "edge", "axis", "curve", "dimension", "csys", "point", "quilt"):
                    if type(x.get("id")) is not int or x["id"] < 0:
                        raise ValueError("Model item reference requires a nonnegative integer id")
                elif k == "feature":
                    if ("label" in x) == ("id" in x):
                        raise ValueError("Feature reference requires one label or id")
                elif k in (
                    "datum_feature",
                    "datum_axis_feature",
                    "sketch_curves",
                    "quilt_feature",
                    "datum_csys_feature",
                    "datum_point_feature",
                ):
                    if not isinstance(x.get("label"), str):
                        raise ValueError("Datum reference requires a label")
                elif k in ("plane", "datum_plane"):
                    validate_planar_reference(x, path)
                elif k not in ("body", "part", "default_csys"):
                    raise ValueError(f"Unsupported model reference kind: {k}")
            for key, v in x.items():
                references(v, f"{path}.{key}")

    references([op for op in dumped if not op["op"].startswith("drawing_")], "operations")
    sketches = {
        op["label"]: op
        for op in dumped
        if op["op"] == "sketch" and isinstance(op.get("entities"), list)
    }
    for index, operation in enumerate(dumped):
        # A solid extrude/revolve consumes the sketch section as one profile;
        # thin features may legitimately use open chains. Only same-plan sketch
        # definitions are visible here, so references to earlier jobs stay with
        # the native solver.
        if (
            operation["op"] in ("extrude", "revolve")
            and isinstance(operation.get("sketch"), str)
            and operation.get("mode") != "surface"
            and operation.get("thin") is None
        ):
            source = sketches.get(operation["sketch"])
            if source:
                try:
                    validate_solid_profile(
                        source["entities"],
                        source.get("dimensioning", "auto"),
                        operation["op"],
                    )
                except ValueError as error:
                    raise ValueError(f"operations[{index}]: {error}") from error
    return dumped
