"""Schemas for general feature operations. Each operation is validated before queuing."""

from __future__ import annotations

import math
import re
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BeforeValidator,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from creo_mechdog import schema_base as _schema_base
from creo_mechdog.geometry_deviation import validate_tolerance_mm
from creo_mechdog.hole_standards import resolve_standard_hole, tip_cone_height_mm
from creo_mechdog.profile_diagnostics import validate_solid_profile
from creo_mechdog.references import (
    PatternAxis,
    RevolveAxis,
    validate_datum_plane_axis,
    validate_datum_plane_reference_kind,
    validate_planar_reference,
    validate_sketch_plane_frame,
)
from creo_mechdog.rotation_admission import ADMISSION_TOLERANCE, admission_status
from creo_mechdog.schema_base import Label, Point2, Point3, Positive, StrictModel
from creo_mechdog.sheetmetal import first_wall_section_problem
from creo_mechdog.surface_ops import (
    ProjectCurveOp,
    QuiltMergeOp,
    SurfaceBoundaryFillOp,
    SurfaceCurvatureOp,
    SurfaceGroupMeasureOp,
    SurfaceLoftOp,
    SurfaceRoundOp,
    SurfaceTrimOp,
    quilt_reference_problem,
)
from creo_mechdog.validation_errors import operation_validation_error

# Compatibility: the label pattern stays reachable from this module.
_LABEL_PATTERN = _schema_base._LABEL_PATTERN


def _rotation_matrix(value: Any) -> Any:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("rotation_matrix must be a nested 3x3 array")
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("rotation_matrix must be a nested 3x3 array")
        if any(type(v) not in (int, float) or not -math.inf < v < math.inf for v in row):
            raise ValueError("rotation_matrix requires finite real numbers")
    status = admission_status(value)
    residual = status["orthogonality_residual"]
    if not math.isfinite(residual) or residual > ADMISSION_TOLERANCE:
        raise ValueError(
            "rotation_matrix must be orthogonal within 1e-6 "
            f"(max |R*R^T-I| = {residual:.9g}); the input is echoed and never repaired, "
            "so supply exact orthonormal values"
        )
    determinant = status["determinant"]
    if abs(determinant - 1) > ADMISSION_TOLERANCE:
        raise ValueError(
            "rotation_matrix determinant must be +1 within 1e-6 "
            f"(det = {determinant:.9g}); the input is echoed and never repaired, "
            "so supply a right-handed orthonormal basis"
        )
    return value


RotationMatrix = Annotated[
    list[Point3], Field(min_length=3, max_length=3), BeforeValidator(_rotation_matrix)
]


#: BUG-045/FEAT-012: the one published mapping. Every pose field below states
#: it verbatim so the execute_plan schema (both assembly branches) cannot drift
#: from the native row-vector implementation.
ROTATION_CONVENTION = "row_vectors_local_to_parent"
ROTATION_FORMULA = "p_parent = p_local * rotation_matrix + translation"


class AssemblyPose(StrictModel):
    translation: Point3 = Field(
        default=[0, 0, 0],
        description=(
            "Translation in the parent frame's units (mm), added after the rotation: "
            f"{ROTATION_FORMULA}."
        ),
    )
    rotation: Point3 | None = Field(
        default=None,
        description=(
            "Euler angles in degrees, applied X then Y then Z and expanded to the same "
            "row-vector matrix; mutually exclusive with rotation_matrix. "
            f"Mapping: {ROTATION_FORMULA}."
        ),
    )
    rotation_matrix: RotationMatrix | None = Field(
        default=None,
        description=(
            f"Row-vector local-to-parent rotation: {ROTATION_FORMULA} "
            "(p_local is a row vector; the matrix is not a column-vector transpose). "
            "It is a 3x3 matrix whose rows are the local X/Y/Z axes in the parent frame, "
            "must be orthogonal (R*R^T = I) with determinant +1 within 1e-6, and is "
            "mutually exclusive with rotation (Euler). The values are applied exactly as "
            "given: never transposed, orthonormalized or repaired."
        ),
    )

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


def _strict_arc_dir(value: Any) -> int:
    # FEAT-034/T02: dir is one strict integer field. True/False, 1.0, "1" and
    # null are not directions; the validated value is the only contract.
    if type(value) is not int or value not in (-1, 1):
        raise ValueError(
            "Arc dir must be the strict integer +1 (counterclockwise) or -1 (clockwise)"
        )
    return value


class Arc(Circle):
    type: Literal["arc"]
    start_angle: float
    end_angle: float
    # FEAT-034/T02: +1 sweeps counterclockwise from start_angle to end_angle in
    # the sketch-local frame (the legacy start/end meaning); -1 sweeps
    # clockwise. The default keeps every legacy request's geometry unchanged.
    dir: Annotated[int, BeforeValidator(_strict_arc_dir)] = 1

    @model_validator(mode="after")
    def span(self):
        if not math.isfinite(self.start_angle) or not math.isfinite(self.end_angle):
            raise ValueError("Arc angles must be finite degrees")
        sweep = (
            (self.end_angle - self.start_angle) % 360
            if self.dir > 0
            else (self.start_angle - self.end_angle) % 360
        )
        if sweep < 1e-10:
            raise ValueError(
                "Arc sweep must be strictly between 0 and 360 degrees; "
                "use circle for a complete circle"
            )
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
    # FEAT-039/W01: the endpoint weld policy. The create and the update
    # entry share one definition, so the same request means the same thing
    # on both paths. "report" only reports the pairing evidence, "reject"
    # refuses a profile whose endpoints could be welded, and "weld" stays
    # refused until the native solver exists.
    endpoint_policy: Literal["report", "reject", "weld"] = "report"
    # The weld plan the policy layer derived: the native side regularises
    # exactly these endpoint pairs before it writes the entities.
    weld_pairs: list[dict[str, Any]] = []
    max_endpoint_move_mm: Annotated[float, Field(gt=0)] | None = None

    @field_validator("max_endpoint_move_mm", mode="before")
    @classmethod
    def _endpoint_move_is_finite_positive(cls, value):
        return validate_tolerance_mm(value)

    dimensions: list[SketchDimension] = []
    constraints: list[SketchConstraint] = []
    dimensioning: Literal["auto", "autodim", "coordinates"] = "auto"
    # FEAT-010/BUG-049: optional post-solve fidelity gate. Omitted keeps the
    # mode defaults (coordinates 1e-5 mm rejection, autodim 1e-3 mm warning);
    # an explicit value forces the threshold. bool/NaN/Inf/0/negative rejected.
    geometry_tolerance_mm: Annotated[float, Field(gt=0)] | None = None

    @field_validator("geometry_tolerance_mm", mode="before")
    @classmethod
    def _tolerance_is_finite_positive(cls, value):
        # pydantic lax mode would coerce bool to float; the contract rejects it.
        return validate_tolerance_mm(value)

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
    # FEAT-039/W01: the endpoint weld policy. The create and the update
    # entry share one definition, so the same request means the same thing
    # on both paths. "report" only reports the pairing evidence, "reject"
    # refuses a profile whose endpoints could be welded, and "weld" stays
    # refused until the native solver exists.
    endpoint_policy: Literal["report", "reject", "weld"] = "report"
    # The weld plan the policy layer derived: the native side regularises
    # exactly these endpoint pairs before it writes the entities.
    weld_pairs: list[dict[str, Any]] = []
    max_endpoint_move_mm: Annotated[float, Field(gt=0)] | None = None

    @field_validator("max_endpoint_move_mm", mode="before")
    @classmethod
    def _endpoint_move_is_finite_positive(cls, value):
        return validate_tolerance_mm(value)

    dimensioning: Literal["auto", "autodim", "coordinates"] = "auto"
    # Same fidelity contract as SketchOp; both entries share one definition.
    geometry_tolerance_mm: Annotated[float, Field(gt=0)] | None = None

    @field_validator("geometry_tolerance_mm", mode="before")
    @classmethod
    def _tolerance_is_finite_positive(cls, value):
        return validate_tolerance_mm(value)

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


def equivalent_rotation_deg(value: float) -> float:
    """Map an angle into (-180, 180] so a rejected request can name the usable value."""
    angle = math.fmod(value, 360.0)
    if angle <= -180.0:
        angle += 360.0
    elif angle > 180.0:
        angle -= 360.0
    return angle


def _check_rotation(rotation: list[float]) -> None:
    """BUG-111: the kernel is usable inside (-180, 180]; refuse anything else early.

    The old +/-360 bound let 225 deg through to a bare ``-1``. The message names
    the equivalent angle instead of silently rewriting the request.
    """
    for axis, value in enumerate(rotation):
        if abs(value) > 180:
            raise ValueError(
                f"rotation[{axis}]={value:g} deg is outside the supported range of "
                f"-180..180 deg; use the equivalent {equivalent_rotation_deg(value):g} deg"
            )


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
        if any(abs(v) > 100000 for v in self.translation):
            raise ValueError("Translation is outside the supported range")
        _check_rotation(self.rotation)
        return self


class TransformUpdateOp(StrictModel):
    op: Literal["set_geometry_transform"]
    feature: Label
    translation: Point3
    rotation: Point3

    @model_validator(mode="after")
    def bounded_values(self):
        if any(abs(v) > 100000 for v in self.translation):
            raise ValueError("Translation is outside the supported range")
        _check_rotation(self.rotation)
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


class Counterbore(StrictModel):
    diameter: Positive
    depth: Positive


class Countersink(StrictModel):
    diameter: Positive
    angle: Annotated[float, Field(gt=0, lt=180)]


class StandardHoleSpec(StrictModel):
    """FEAT-035 frozen shape: a table row plus a usable thread depth.

    ``fastener_id`` is the installed hole chart's own name for the row
    ("M6x1"). It is optional here because the resolver supplies it; a caller
    value is only accepted when it matches the frozen table row.
    """

    series: str
    size: str
    thread_depth: Annotated[float, Field(gt=0)]
    fastener_id: str | None = None
    nominal_diameter_mm: float | None = None
    tap_drill_mm: float | None = None
    thread_depth_limit_mm: float | None = None

    @field_validator("series", "size", "fastener_id", mode="before")
    @classmethod
    def table_name(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("standard hole series and size are table names, not booleans")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("standard hole series and size must not be empty")
        text = value.strip()
        if text in {".", ".."} or "/" in text or "\\" in text or ":" in text:
            raise ValueError("standard hole series and size must be table names, not paths")
        return text

    @field_validator("thread_depth", mode="before")
    @classmethod
    def thread_depth_is_finite(cls, value: Any) -> Any:
        # A bool is an int in Python and Inf passes a plain gt=0 bound; both
        # would otherwise become a hole depth instead of a refused request.
        if isinstance(value, bool):
            raise ValueError("standard hole thread depth must be a number, not a boolean")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("standard hole thread depth must be finite")
        return value


class HoleOp(StrictModel):
    op: Literal["hole"]
    label: Label
    placement: dict[str, Any]
    reference1: dict[str, Any]
    reference2: dict[str, Any]
    offset1: float = 0
    offset2: float = 0
    diameter: Positive | None = None
    depth: Positive | None = None
    flip: bool = False
    counterbore: Counterbore | None = None
    countersink: Countersink | None = None
    standard: StandardHoleSpec | None = None

    @model_validator(mode="after")
    def hole_options_valid(self):
        if self.counterbore is not None and self.countersink is not None:
            raise ValueError("counterbore and countersink are mutually exclusive")
        if self.standard is not None:
            if self.counterbore is not None or self.countersink is not None:
                raise ValueError(
                    "standard threaded holes cannot be combined with counterbore or countersink"
                )
            self._check_standard_hole()
            return self
        if self.diameter is None:
            raise ValueError("a hole without standard requires diameter")
        self._check_plain_hole(self.diameter)
        return self

    def _check_plain_hole(self, diameter: float) -> None:
        if self.counterbore is not None:
            if self.counterbore.diameter <= diameter:
                raise ValueError("counterbore diameter must exceed hole diameter")
            if self.depth is not None and self.counterbore.depth >= self.depth:
                raise ValueError("counterbore depth must be less than blind hole depth")
        if self.countersink is not None:
            if self.countersink.diameter <= diameter:
                raise ValueError("countersink diameter must exceed hole diameter")
            sink_depth = (self.countersink.diameter - diameter) / (
                2 * math.tan(math.radians(self.countersink.angle / 2))
            )
            if self.depth is not None and sink_depth >= self.depth:
                raise ValueError("countersink cone must be shallower than blind hole depth")

    def _check_standard_hole(self) -> None:
        assert self.standard is not None
        row = resolve_standard_hole(self.standard.series, self.standard.size)
        if "fastener_id" not in row:
            raise ValueError(
                f"standard hole {row['series']} {row['size']} has no hole-chart fastener id"
            )
        if self.standard.fastener_id not in (None, row["fastener_id"]):
            raise ValueError(
                f"standard hole {row['series']} {row['size']} fastener id is "
                f"{row['fastener_id']!r}, not {self.standard.fastener_id!r}"
            )
        if self.standard.tap_drill_mm is not None and (
            abs(self.standard.tap_drill_mm - row["tap_drill_diameter_mm"]) > 1e-9
        ):
            raise ValueError(
                f"standard hole {row['series']} {row['size']} tap drill is "
                f"{row['tap_drill_diameter_mm']} mm, not {self.standard.tap_drill_mm} mm"
            )
        if self.standard.nominal_diameter_mm is not None and (
            abs(self.standard.nominal_diameter_mm - row["nominal_diameter_mm"]) > 1e-9
        ):
            raise ValueError(
                f"standard hole {row['series']} {row['size']} nominal diameter is "
                f"{row['nominal_diameter_mm']} mm, not {self.standard.nominal_diameter_mm} mm"
            )
        if self.standard.thread_depth_limit_mm is not None and (
            abs(self.standard.thread_depth_limit_mm - row["thread_depth_limit_mm"]) > 1e-9
        ):
            raise ValueError(
                f"standard hole {row['series']} {row['size']} thread depth limit is "
                f"{row['thread_depth_limit_mm']} mm, not "
                f"{self.standard.thread_depth_limit_mm} mm"
            )
        if self.diameter is not None and (abs(self.diameter - row["nominal_diameter_mm"]) > 1e-9):
            raise ValueError(
                f"standard hole {row['series']} {row['size']} has a nominal diameter of "
                f"{row['nominal_diameter_mm']} mm, but diameter is {self.diameter} mm"
            )
        if self.standard.thread_depth > row["thread_depth_limit_mm"]:
            raise ValueError(
                f"thread depth {self.standard.thread_depth} mm exceeds the "
                f"{row['series']} {row['size']} table limit of "
                f"{row['thread_depth_limit_mm']} mm"
            )
        if self.depth is None:
            raise ValueError(
                "a standard threaded hole requires an explicit depth: the usable thread must "
                "stay strictly inside the drilled tip depth"
            )
        tip_depth = self.depth + tip_cone_height_mm(row["tap_drill_diameter_mm"])
        if self.standard.thread_depth >= tip_depth:
            raise ValueError(
                f"thread depth {self.standard.thread_depth} mm must be strictly inside the "
                f"{row['series']} {row['size']} tip depth {tip_depth:.4f} mm"
            )


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

    @model_validator(mode="after")
    def datum_plane_contract(self):
        # BUG-094: a kindless reference reached the native executor as a JSON
        # missing-key error, and an angled plane silently dropped a nonzero offset.
        validate_datum_plane_reference_kind(self.reference, "reference")
        if self.reference.get("kind") == "through_points":
            # FEAT-053: three points fully determine the plane; the angle/axis
            # and offset modes are separate constraint forms and cannot mix in.
            if self.angle is not None:
                raise ValueError(
                    "datum_plane reference {kind:'through_points'} is fully determined by its "
                    "three points and cannot be combined with angle"
                )
            if self.axis is not None:
                raise ValueError(
                    "datum_plane reference {kind:'through_points'} is fully determined by its "
                    "three points and cannot be combined with axis"
                )
            if self.offset != 0:
                raise ValueError(
                    "datum_plane reference {kind:'through_points'} is fully determined by its "
                    "three points and cannot be combined with a nonzero offset"
                )
            return self
        if self.angle is not None:
            if self.offset != 0:
                raise ValueError(
                    "datum_plane cannot combine angle with a nonzero offset: the angled "
                    "constraint silently drops the offset. Submit two explicit datum_plane "
                    "operations - first the angled plane (angle with axis, offset 0), then "
                    "an offset plane measured from it"
                )
            # angle=0 is still the explicit angle mode, so the axis stays required.
            validate_datum_plane_axis(self.axis, "axis")
        return self


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
    # FEAT-004 guards: pin what the plan observed so a shifted dimension is
    # refused instead of moved. All three are optional, so old payloads keep
    # their exact behaviour.
    expected_value: float | None = None
    expected_symbol: str | None = None
    expected_owner: str | int | None = None

    @field_validator("value", "expected_value", mode="before")
    @classmethod
    def numeric_value(cls, value: Any) -> Any:
        # bool is an int in Python; True would otherwise become 1.0 mm.
        if isinstance(value, bool):
            raise ValueError("dimension values are numbers of model units, not booleans")
        return value

    @field_validator("expected_owner", mode="before")
    @classmethod
    def owner_reference(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("expected_owner is a feature id or label, not a boolean")
        if isinstance(value, str) and not value.strip():
            raise ValueError("expected_owner must not be empty")
        return value


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
    # DEV-051 T03 / BUG-032 contract: the first wall is one open straight line
    # of length L. `thickness` is the sheet thickness and becomes the in-plane
    # width of the thin section; `depth` is the extrusion distance along the
    # sketch normal. The native wall keeps volume = L x thickness x depth and
    # rejects sections it cannot drive (see creo_mechdog.sheetmetal).
    op: Literal["sheetmetal_wall"]
    label: Label
    sketch: SketchRef
    depth: Positive
    thickness: Positive
    direction: Literal["positive", "negative"] = "positive"


class SheetmetalPlanarWallOp(StrictModel):
    """FEAT-058: native rectangular unattached planar wall (the primary wall).

    Creo Toolkit builds the primary wall as the Fill feature carrying the
    sheetmetal branch (PRO_E_IS_UNATTACHED_WALL, PRO_E_BODY_USE=NEW,
    PRO_E_SMT_NEW_BODY_LINKED), not as a PRO_FEAT_WALL. It therefore needs a
    sheetmetal part, and the part must still be empty. `length` runs along the
    sketch u axis, `width` along v, and `thickness` is the sheet gauge along the
    signed sketch normal. The internal sketch is named `<label>_sk`.

    R10: `origin=[u0,v0]` moves the rectangle to u0..u0+length / v0..v0+width in
    the sketch frame (mm) instead of starting at 0,0, so the first wall can be
    placed around a model origin. The named plane frame, its signed envelope and
    the growth direction do not change; a resize keeps the recorded origin.
    """

    op: Literal["sheetmetal_planar_wall"]
    label: Label
    plane: Literal["XY", "XZ", "YZ"] | dict[str, Any] = "XY"
    length: Positive
    width: Positive
    thickness: Positive
    direction: Literal["positive", "negative"] = "positive"
    origin: list[float] = Field(default_factory=lambda: [0.0, 0.0])

    @field_validator("origin", mode="before")
    @classmethod
    def origin_is_two_finite_mm(cls, value: Any) -> Any:
        # The origin is a sketch-local [u, v] pair in mm. A three-element point,
        # a bool (True is an int) or a NaN would reach the native frame as a
        # different request than the caller wrote.
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError("sheetmetal_planar_wall origin must be [u0, v0] in mm")
        components = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError("sheetmetal_planar_wall origin components must be numbers")
            number = float(item)
            if not math.isfinite(number):
                raise ValueError("sheetmetal_planar_wall origin components must be finite")
            if abs(number) > 1_000_000:
                raise ValueError("sheetmetal_planar_wall origin is limited to +/-1000000 mm")
            components.append(number)
        return components

    @model_validator(mode="after")
    def label_leaves_room_for_sketch(self):
        # The internal driving sketch is a real Creo feature, so the wall label
        # has to leave room for the suffix instead of colliding with the native
        # 28-character feature-name limit.
        if len(self.label) > 25:
            raise ValueError("sheetmetal_planar_wall label must be at most 25 characters")
        if not isinstance(self.plane, str) and any(abs(value) > 0 for value in self.origin):
            # A dictionary plane already carries its own world-coordinate origin;
            # combining it with a sketch-local [u0, v0] would be ambiguous.
            raise ValueError(
                "sheetmetal_planar_wall origin is a sketch-local offset on XY/XZ/YZ; "
                "a dictionary plane carries its own origin"
            )
        return self


class SheetmetalPlanarWallResizeOp(StrictModel):
    """FEAT-058: resize the rectangular planar wall in place.

    The resize drives the wall's own sketch coordinate dimensions, so the wall
    feature id and its thickness stay untouched. Downstream features and
    unsupported frames are refused instead of being silently rebuilt.
    """

    op: Literal["resize_sheetmetal_planar_wall"]
    feature: Label
    length: Positive
    width: Positive


class FlangeRelief(StrictModel):
    # DEV-051 T11 / FEAT-014. Creo 12.4 exposes one relief compound per bend end
    # (ProSmtFlangeWall.h: PRO_E_SMT_BEND_RELIEF_SIDE1/SIDE2) with the types
    # PRO_BEND_RLF_NONE/RIP/STRETCH/RECTANGULAR/OBROUND/PARAM. Only "none" (the
    # pre-T11 tree) and "rectangular" with an explicit blind width and depth are
    # admitted: width and depth stay absolute model units, are never derived from
    # the sheet thickness, and no corner rule is guessed from the edge geometry.
    # This is bend-end relief, not corner relief or a miter: it is not proven to
    # resolve corner overlap, and the adjacent_bend_ends guard still refuses such
    # a flange when this relief is supplied.
    # Rip/stretch/obround/param, corner relief, miter cuts and edge rips remain
    # unsupported and are rejected instead of being silently replaced by "none".
    type: Literal["none", "rectangular"] = "none"
    ends: Literal["both", "side1", "side2"] = "both"
    width: Annotated[float, Field(gt=0, le=100000)] | None = None
    depth: Annotated[float, Field(ge=0, le=100000)] | None = None

    @field_validator("width", "depth", mode="before")
    @classmethod
    def numeric_dimension(cls, value: Any) -> Any:
        # bool is an int in Python; accepting True as a 1 mm notch would be a
        # silent reinterpretation instead of a rejected request.
        if isinstance(value, bool):
            raise ValueError("relief width and depth are numbers of model units, not booleans")
        return value

    @model_validator(mode="after")
    def relief_valid(self):
        if self.type == "none":
            if self.width is not None or self.depth is not None:
                raise ValueError(
                    "relief type none takes no width or depth; omit them or use type rectangular"
                )
            if self.ends != "both":
                raise ValueError(
                    "relief type none has no ends to select; ends applies to rectangular"
                )
        elif self.width is None or self.depth is None:
            raise ValueError(
                "relief type rectangular requires width (>0) and depth (>=0) in model units"
            )
        return self


class FlangeMiterCuts(StrictModel):
    # FEAT-014 2026-11-06. The native miter-cut section of the same flange feature
    # (ProSmtFlangeWall.h: PRO_E_SMT_MTR_CUTS), GAP width and offset in model
    # units. A flange whose attachment-edge ends abut existing bends must carry
    # this request to pass the adjacent_bend_ends guard; without it the guard
    # keeps refusing before creation. The live geometry meaning of the gap is
    # measured by the box driver - this request alone claims no cut amount.
    width: Annotated[float, Field(gt=0, le=100000)]
    offset: Annotated[float, Field(ge=0, le=100000)] | None = None

    @field_validator("width", "offset", mode="before")
    @classmethod
    def numeric_dimension(cls, value: Any) -> Any:
        # bool is an int in Python; accepting True as a 1 mm gap would be a
        # silent reinterpretation instead of a rejected request.
        if isinstance(value, bool):
            raise ValueError("miter_cuts width and offset are numbers of model units, not booleans")
        return value

    @model_validator(mode="after")
    def miter_valid(self):
        if self.offset is None:
            self.offset = self.width
        return self


class SheetmetalFlangeOp(StrictModel):
    op: Literal["sheetmetal_flange"]
    label: Label
    # R09/R10: the plan path is operations[i].edge. Two shapes reach the native
    # resolver: a bare current-geometry edge id {kind:'edge',id:N}, or the two
    # straight-edge endpoints in millimetres {kind:'edge_geometry',endpoints_mm:
    # [[x,y,z],[x,y,z]],tolerance_mm:1e-6}. The geometry form is what makes a
    # plan survive a rebuild that renumbers edges; the native side re-queries the
    # model for every operation and requires exactly one match.
    edge: dict[str, Any] = Field(
        description=(
            "Edge reference for operations[i].edge: {kind:'edge',id:N} with the "
            "current edge id from creo_inspect_model, or "
            "{kind:'edge_geometry',endpoints_mm:[[x,y,z],[x,y,z]],"
            "tolerance_mm:1e-6} matching exactly one straight model edge"
        )
    )
    height: Positive
    angle: Annotated[float, Field(gt=0, lt=180)] = 90
    radius: Positive = 1
    flip: bool = False
    y_factor: Annotated[float, Field(gt=0, le=1)] = 0.5
    relief: FlangeRelief | None = None
    # FEAT-014: optional native miter cuts on the same flange feature. An explicit
    # request is the only way a wall whose attachment-edge ends abut existing
    # bends passes the adjacent_bend_ends guard; omitting it keeps the previous
    # refusal exactly. relief and miter_cuts are orthogonal and may be combined.
    miter_cuts: FlangeMiterCuts | None = None
    # DEV-051 T05 third-wall contrast: shorten the wall at both chain ends by this
    # absolute model-unit length (both depth sides become blind with this offset).
    # Omitting it keeps the previous full-edge tree. Whether Creo measures the blind
    # offset as a setback from each chain end or a length from the section is a live
    # measurement; the T05 driver probes that on a free wall before the trimmed
    # third wall, so no geometric claim is made from this field alone.
    end_trim_mm: Annotated[float, Field(gt=0, le=100000)] | None = None

    @field_validator("end_trim_mm", mode="before")
    @classmethod
    def trim_is_a_number(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("end_trim_mm is a length in model units, not a boolean")
        return value

    @field_validator("edge", mode="before")
    @classmethod
    def edge_is_a_current_reference(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("kind") not in {"edge", "edge_geometry"}:
            raise ValueError(
                "sheetmetal_flange edge must be {kind:'edge',id:N} or "
                "{kind:'edge_geometry',endpoints_mm:[[x,y,z],[x,y,z]],tolerance_mm:1e-6}"
            )
        if value["kind"] == "edge":
            if set(value) != {"kind", "id"}:
                raise ValueError("edge {kind:'edge'} accepts exactly kind and id")
            edge_id = value.get("id")
            if (
                isinstance(edge_id, bool)
                or not isinstance(edge_id, int)
                or not 0 <= edge_id < 2**31
            ):
                raise ValueError(
                    "edge {kind:'edge'} id must be the nonnegative 32-bit integer from "
                    "creo_inspect_model"
                )
            return value
        extra = set(value) - {"kind", "endpoints_mm", "tolerance_mm"}
        if extra:
            raise ValueError(
                "edge_geometry accepts endpoints_mm and tolerance_mm only; the length unit "
                f"comes from the model, not from {sorted(extra)}"
            )
        endpoints = value.get("endpoints_mm")
        if not isinstance(endpoints, list) or len(endpoints) != 2:
            raise ValueError("edge_geometry endpoints_mm must be two [x,y,z] points")
        for point in endpoints:
            if not isinstance(point, list) or len(point) != 3:
                raise ValueError("edge_geometry endpoints_mm must be two [x,y,z] points")
            for coordinate in point:
                if (
                    isinstance(coordinate, bool)
                    or not isinstance(coordinate, (int, float))
                    or not math.isfinite(coordinate)
                ):
                    raise ValueError(
                        "edge_geometry endpoints_mm coordinates must be finite numbers"
                    )
        if math.dist(endpoints[0], endpoints[1]) <= 0:
            raise ValueError("edge_geometry endpoints_mm must describe a non-degenerate edge")
        tolerance = value.get("tolerance_mm", 1e-6)
        if (
            isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance)
            or not 1e-9 <= tolerance <= 1000
        ):
            raise ValueError("edge_geometry tolerance_mm must be between 1e-9 and 1000")
        return {
            "kind": "edge_geometry",
            "endpoints_mm": [[float(coordinate) for coordinate in point] for point in endpoints],
            "tolerance_mm": float(tolerance),
        }


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


# FEAT-052 recolor shape validation. It lives here (not in appearance.py)
# because RecolorAssemblyOp validates at import time of this module and the
# installed package must stay importable without the repo root (bridge is a
# root-only module); appearance.py imports these helpers from here.
FAMILY_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,27}$"
SOURCE_MODEL_PATTERN = re.compile(r"^[a-f0-9]{32}\Z")
MEMBER_ID_MAX = 2147483647
MAX_FAMILIES = 200
MAX_MEMBERS_PER_FAMILY = 500
MAX_MEMBERS_TOTAL = 2000


def validate_rgb(value: Any, path: str = "rgb") -> list[float]:
    """Three finite numbers in 0..1; booleans are refused, even nested in lists."""
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{path} must be exactly three numbers [r,g,b] in 0..1")
    color = []
    for item in value:
        if isinstance(item, bool) or type(item) not in (int, float):
            raise ValueError(
                f"{path} components must be finite numbers in 0..1; booleans and non-numbers "
                "are refused"
            )
        if not math.isfinite(item) or not 0.0 <= item <= 1.0:
            raise ValueError(f"{path} components must be finite numbers in 0..1")
        color.append(float(item))
    return color


def validate_family_name(value: Any, path: str = "family name") -> str:
    """Project label rule: lowercase start, [a-z0-9_], at most 28 characters."""
    if not isinstance(value, str) or not re.fullmatch(FAMILY_NAME_PATTERN, value):
        raise ValueError(
            f"{path} must start with a lowercase letter and contain only [a-z0-9_], "
            "at most 28 characters"
        )
    return value


def normalize_member_ref(value: Any, path: str = "component reference") -> str | int:
    """A family member is a component label or a nonnegative feature ID."""
    if isinstance(value, bool):
        raise ValueError(f"{path} must be a component label or feature ID, not a boolean")
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    if type(value) is int:
        if not 0 <= value <= MEMBER_ID_MAX:
            raise ValueError(f"{path} feature IDs must be nonnegative 32-bit integers")
        return value
    if isinstance(value, str) and re.fullmatch(FAMILY_NAME_PATTERN, value):
        return value
    raise ValueError(
        f"{path} must be a component label starting with a lowercase letter "
        "([a-z0-9_], at most 28 characters) or a nonnegative feature ID"
    )


def validate_families(families: Any, path: str = "families") -> dict[str, list[str | int]] | None:
    if families is None:
        return None
    if not isinstance(families, dict) or not families:
        raise ValueError(
            f"{path} must be a non-empty object mapping family names to component lists "
            "(omit it entirely for automatic grouping)"
        )
    if len(families) > MAX_FAMILIES:
        raise ValueError(f"{path} supports at most {MAX_FAMILIES} families")
    checked: dict[str, list[str | int]] = {}
    total = 0
    for raw_name, members in families.items():
        name = validate_family_name(raw_name, f"{path} key {raw_name!r}")
        if not isinstance(members, list) or not members:
            raise ValueError(
                f"{path}.{name} must be a non-empty list of component labels or feature IDs"
            )
        if len(members) > MAX_MEMBERS_PER_FAMILY:
            raise ValueError(f"{path}.{name} supports at most {MAX_MEMBERS_PER_FAMILY} components")
        refs = [
            normalize_member_ref(item, f"{path}.{name}[{position}]")
            for position, item in enumerate(members)
        ]
        total += len(refs)
        checked[name] = refs
    if total > MAX_MEMBERS_TOTAL:
        raise ValueError(f"{path} supports at most {MAX_MEMBERS_TOTAL} component references")
    return checked


def validate_palette(palette: Any, path: str = "palette") -> dict[str, list[float]] | None:
    if palette is None:
        return None
    if not isinstance(palette, dict) or not palette:
        raise ValueError(
            f"{path} must be a non-empty object mapping family names to [r,g,b] colors "
            "(omit it entirely for a dry_run preview without colors)"
        )
    checked: dict[str, list[float]] = {}
    for key, value in palette.items():
        if not isinstance(key, str) or not key or len(key) > 64:
            raise ValueError(f"{path} keys must be non-empty names of at most 64 characters")
        checked[key] = validate_rgb(value, f"{path}[{key!r}]")
    return checked


def validate_recolor_shape(
    families: Any, palette: Any
) -> tuple[dict[str, list[str | int]] | None, dict[str, list[float]] | None]:
    """Shape validation shared by the tool entry, the plan op and submission.

    Palette key identity depends on the grouping mode: automatic (families
    omitted) keys must look like source model ids or component labels (the
    registry resolves a label to its single source family); explicit keys must
    name the supplied families. Completeness of the palette is an execution
    rule and is checked later against the resolved families.
    """
    checked_families = validate_families(families)
    checked_palette = validate_palette(palette)
    if checked_palette is not None:
        if checked_families is None:
            for key in checked_palette:
                if SOURCE_MODEL_PATTERN.fullmatch(key) or re.fullmatch(_LABEL_PATTERN, key):
                    continue
                raise ValueError(
                    "palette keys must be source model_ids (32 lowercase hex characters) or "
                    f"component labels when families is omitted; got {key!r}"
                )
        else:
            for key in checked_palette:
                if key not in checked_families:
                    raise ValueError(
                        f"palette key {key!r} does not name a family; "
                        f"known families: {sorted(checked_families)}"
                    )
    return checked_families, checked_palette


class RecolorAssemblyOp(StrictModel):
    # FEAT-052 plan operation: paint existing components of a managed
    # single-level assembly by part family. It reuses the exact validation of
    # creo_recolor_assembly in execution mode: palette required and complete,
    # families optional (automatic grouping by source_model_id). The preview
    # parameters of the standalone tool (dry_run/limit/cursor) are not part of
    # a plan and are refused by extra="forbid"; only components that already
    # exist before the plan runs may be selected (plan-created ones refuse).
    op: Literal["recolor_assembly"]
    palette: dict[str, Any]
    families: dict[str, Any] | None = None
    # BUG-104: explicit escape hatch for checkpoints saved before FEAT-052
    # (no component ``appearance`` snapshot). It only relaxes that one gate;
    # ``random`` is a tool-level convenience and stays refused in a plan.
    refresh_baseline: bool = False

    @model_validator(mode="after")
    def recolor_request_valid(self):
        self.families, self.palette = validate_recolor_shape(self.families, self.palette)
        return self


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
    format: Literal["step", "stl", "iges", "jpeg", "pdf", "native_bundle"] = "step"


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


class MassPropertiesOp(StrictModel):
    """FEAT-057: read-only mass properties of the model itself.

    ``density_g_cm3`` is an explicit what-if input, used only when the model's
    own material carries no usable density. It never replaces a real material
    density, and the receipt reports which source produced the mass.
    """

    op: Literal["mass_properties"]
    density_g_cm3: Annotated[float | None, Field(gt=0, le=30)] = None


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


class SurfaceOffsetOp(StrictModel):
    op: Literal["surface_offset"]
    label: Label
    reference: dict[str, Any]
    distance: Positive
    side: Literal["positive", "negative"] = "positive"

    @model_validator(mode="after")
    def reference_is_a_quilt(self):
        # FEAT-039/S07: an offset acts on a surface, so the reference must be a
        # quilt; a body or a datum plane is refused before a job exists.
        problem = quilt_reference_problem(self.reference, allow_datum_plane=False)
        if problem:
            raise ValueError(f"surface_offset reference {problem}")
        return self


class SolidifyOp(StrictModel):
    op: Literal["solidify"]
    label: Label
    reference: dict[str, Any]
    side: Literal["positive", "negative"] = "positive"
    mode: Literal["add", "cut"] = "add"
    new_body: bool = False

    @model_validator(mode="after")
    def reference_matches_mode(self):
        # FEAT-039/S06: adding a solid needs one quilt; a body is not a quilt
        # and the boolean body tools cannot stand in for the quilt semantics.
        # The cut mode trims a solid with a datum plane and keeps its own
        # reference spellings.
        if self.mode == "add":
            problem = quilt_reference_problem(self.reference, allow_datum_plane=False)
            if problem:
                raise ValueError(f"solidify reference {problem}")
        return self


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
        if any(r.get("kind") != "body" or type(r.get("id")) is not int for r in refs):
            raise ValueError("Explicit body IDs are required")
        if any(r["id"] < 0 for r in refs):
            raise ValueError(
                "BOOLEAN_BODY_REFERENCE_UNSUPPORTED: negative body IDs can be returned by "
                "inspection but are not supported by this Boolean feature path; this is a "
                "capability limit, not a malformed body reference. Sheetmetal-to-solid fusion "
                "is unverified even with positive IDs; keep separate bodies or use verified "
                "sheetmetal wall/flange operations"
            )
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
        SheetmetalPlanarWallOp,
        SheetmetalPlanarWallResizeOp,
        SheetmetalFlangeOp,
        SheetmetalUnbendOp,
        AssembleOp,
        ComponentPlacementOp,
        ComponentConstraintsOp,
        RemoveComponentOp,
        RecolorAssemblyOp,
        FeatureStateOp,
        GenericFeatureOp,
        SimpleOp,
        ExportOp,
        DumpTreeOp,
        MassPropertiesOp,
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
        SurfaceOffsetOp,
        SolidifyOp,
        SurfaceTrimOp,
        SurfaceLoftOp,
        SurfaceBoundaryFillOp,
        SurfaceRoundOp,
        SurfaceCurvatureOp,
        SurfaceGroupMeasureOp,
        QuiltMergeOp,
        ProjectCurveOp,
        BooleanOp,
        RibOp,
    ],
    Field(discriminator="op"),
]
OPERATIONS = TypeAdapter(list[Operation])


def dump_plan_operations(operations) -> list[dict]:
    """Dump validated plan models so extrude omissions stay visible (W05).

    ExtrudeOp applies the 1 mm / blind defaults for execution, but the receipt
    must distinguish an omitted field from an explicit one, so a depth or
    depth_type the caller never set is dropped here. validate_operations
    re-applies the defaults and marks them in defaulted_fields.
    """
    dumped = []
    for op in operations:
        data = op.model_dump(exclude_none=True)
        provided = getattr(op, "model_fields_set", ())
        if data.get("op") == "extrude":
            for field in ("depth", "depth_type"):
                if field not in provided:
                    data.pop(field, None)
        dumped.append(data)
    return dumped


def validate_operations(operations: list[dict]) -> list[dict]:
    if not 0 <= len(operations) <= 200:
        raise ValueError("A plan supports at most 200 operations")
    # W05: the model below applies the depth/depth_type defaults, which would
    # erase the difference between "omitted" and "explicitly 1 / blind". The
    # omission is therefore captured from the caller's dicts (dump_plan_operations
    # already removed the keys the plan entry never set) and marked on the
    # normalized operation for the native receipt.
    defaulted_extrude_fields: dict[int, list[str]] = {}
    for index, raw in enumerate(operations):
        if not isinstance(raw, dict) or raw.get("op") != "extrude":
            continue
        missing = [field for field in ("depth", "depth_type") if field not in raw]
        if missing:
            defaulted_extrude_fields[index] = missing
    try:
        result = OPERATIONS.validate_python(operations)
    except ValidationError as exc:
        raise operation_validation_error(exc, single_operation=len(operations) == 1) from None
    labels = [x.label for x in result if hasattr(x, "label")]
    if len(labels) != len(set(labels)):
        raise ValueError("Feature labels must be unique within a plan")
    dumped = [x.model_dump(exclude_none=True) for x in result]
    for index, missing in defaulted_extrude_fields.items():
        dumped[index]["defaulted_fields"] = missing

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
    # FEAT-052: recolor_assembly paints only components that already exist
    # before the plan runs; a label this same plan creates with
    # assemble_component is refused instead of silently matching the
    # component once the plan has built it.
    plan_components = {op["label"] for op in dumped if op["op"] == "assemble_component"}
    for index, operation in enumerate(dumped):
        if operation["op"] != "recolor_assembly":
            continue
        members = [ref for refs in (operation.get("families") or {}).values() for ref in refs]
        offenders = sorted({ref for ref in members if ref in plan_components})
        if offenders:
            raise ValueError(
                f"operations[{index}]: recolor_assembly only selects components that already "
                "exist before the plan runs; these labels are created by assemble_component "
                f"operations inside the same plan: {offenders}"
            )

    # FEAT-053: a through_points reference names datum_points feature labels
    # created earlier in this same plan. Each producer must be a single-point
    # datum_points operation; a plan cannot forward-reference features that do
    # not exist yet when the plane runs, and it never guesses a point out of a
    # multi-point feature.
    producers: dict[str, tuple[int, str, int]] = {}
    for index, operation in enumerate(dumped):
        label = operation.get("label")
        if isinstance(label, str):
            point_count = len(operation["points"]) if operation["op"] == "datum_points" else -1
            producers[label] = (index, operation["op"], point_count)
    for index, operation in enumerate(dumped):
        if operation["op"] != "datum_plane":
            continue
        reference = operation.get("reference") or {}
        if not isinstance(reference, dict) or reference.get("kind") != "through_points":
            continue
        for slot, label in enumerate(reference.get("points") or []):
            where = f"operations[{index}].reference.points[{slot}]"
            entry = producers.get(label)
            if entry is None:
                raise ValueError(
                    f"{where}: through_points label '{label}' must be created by a "
                    "datum_points operation earlier in the same plan; this plan does "
                    "not create it"
                )
            producer_index, producer_op, point_count = entry
            if producer_index == index:
                raise ValueError(
                    f"{where}: through_points label '{label}' is the plane's own label; "
                    "the three points must be created earlier in the same plan"
                )
            if producer_index > index:
                raise ValueError(
                    f"{where}: through_points label '{label}' is created later in this "
                    f"plan (operations[{producer_index}]); the three points must exist "
                    "before the datum_plane runs"
                )
            if producer_op != "datum_points":
                raise ValueError(
                    f"{where}: through_points label '{label}' is created by "
                    f"operations[{producer_index}] (op '{producer_op}'); through_points "
                    "requires a datum_points feature"
                )
            if point_count != 1:
                raise ValueError(
                    f"{where}: datum_points label '{label}' defines {point_count} points; "
                    "through_points requires a single-point datum_points feature"
                )

    # BUG-115: a thicken that names the quilt_feature of a surface_trim fails on
    # hardware 3/3 with ProFeatureGeomitemVisit(PRO_QUILT) = -4 when the trim's
    # own target quilt is also created in that same plan: the fresh chain
    # fill -> trim -> thicken has not regenerated yet when thicken visits it.
    # The proven working projected_dependency route trims an older quilt, so the
    # guard only refuses the all-new same-plan chain. Refuse before a job exists
    # and give an executable alternative instead of relaying the raw -4.
    quilt_producers = {
        operation["label"]: index
        for index, operation in enumerate(dumped)
        if operation["op"] in ("surface_fill", "surface_trim")
        and isinstance(operation.get("label"), str)
    }
    for index, operation in enumerate(dumped):
        if operation["op"] != "thicken":
            continue
        reference = operation.get("reference") or {}
        if not isinstance(reference, dict) or reference.get("kind") != "quilt_feature":
            continue
        label = reference.get("label")
        trim_index = quilt_producers.get(label)
        if trim_index is None or trim_index >= index:
            continue
        trim = dumped[trim_index]
        if trim["op"] != "surface_trim":
            continue
        target = trim.get("target") or {}
        target_label = target.get("label") if isinstance(target, dict) else None
        target_index = quilt_producers.get(target_label)
        if (
            target.get("kind") != "quilt_feature"
            or target_index is None
            or target_index >= trim_index
        ):
            continue
        raise ValueError(
            f"operations[{index}].reference: thicken names quilt_feature '{label}' from "
            f"operations[{trim_index}], whose own target quilt '{target_label}' is created in "
            f"operations[{target_index}] of the same plan; Creo returns "
            "ProFeatureGeomitemVisit(PRO_QUILT) -4 before the fresh trim chain regenerates "
            "(BUG-115). Submit fill/trim first, then submit thicken in a second plan referencing "
            "the existing quilt feature, or pass an explicit {kind:'quilt',id:N} read back from "
            "creo_inspect_model."
        )

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
                elif k == "through_points":
                    # FEAT-053: the three-point datum_plane reference. Its shape
                    # is validated by PlaneOp and its producers by the plan-level
                    # check below; nothing else accepts this kind.
                    pass
                elif k == "edge_geometry":
                    # R10: a flange attachment edge named by its two current
                    # endpoints. Shape and bounds are enforced by
                    # SheetmetalFlangeOp.edge_is_a_current_reference; every other
                    # operation rejects the kind in its own field validator.
                    pass
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
        # DEV-051 T03 / BUG-032: the sheetmetal first wall is defined by one open
        # straight line only. A section from an earlier job is enforced by the
        # native operation; a same-plan section is rejected before modelling.
        if operation["op"] == "sheetmetal_wall" and isinstance(operation.get("sketch"), str):
            source = sketches.get(operation["sketch"])
            if source:
                problem = first_wall_section_problem(source["entities"])
                if problem:
                    raise ValueError(f"operations[{index}]: {problem}")
    return dumped
