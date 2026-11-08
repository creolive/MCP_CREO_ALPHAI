"""DEV-078 offline candidates; native regeneration and live acceptance remain required."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from creo_mechdog.schema_base import Label, Positive, StrictModel

GeometryId = Annotated[StrictInt, Field(ge=0, le=2147483647)]


class SheetmetalSurfaceRef(StrictModel):
    kind: Literal["surface"]
    id: GeometryId


class SheetmetalQuiltRef(StrictModel):
    kind: Literal["quilt"]
    id: GeometryId


class SheetmetalQuiltFeatureRef(StrictModel):
    kind: Literal["quilt_feature"]
    label: Label


class SheetmetalCornerReliefOp(StrictModel):
    op: Literal["sheetmetal_corner_relief"]
    label: Label
    flat: SheetmetalSurfaceRef
    bends: Annotated[list[SheetmetalSurfaceRef], Field(min_length=2, max_length=2)]
    width: Positive
    depth: Positive
    state: Literal["formed", "unbent"] = "formed"

    @field_validator("width", "depth", mode="before")
    @classmethod
    def real_dimension(cls, value):
        if type(value) not in (int, float):
            raise ValueError("dimensions require finite real millimetres, not bool or text")
        return value

    @model_validator(mode="after")
    def distinct_surfaces(self):
        if len({self.flat.id, *(bend.id for bend in self.bends)}) != 3:
            raise ValueError("flat and both bends must identify three distinct surfaces")
        return self


class SheetmetalQuiltFormOp(StrictModel):
    op: Literal["sheetmetal_quilt_form"]
    label: Label
    quilt: Annotated[SheetmetalQuiltRef | SheetmetalQuiltFeatureRef, Field(discriminator="kind")]
    side: Literal["face", "offset"] = "face"
    material_side: Literal["inside", "outside"] = "outside"
    keep_quilt: StrictBool = True
    trim_sides: StrictBool = False
