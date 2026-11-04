"""Shared schema primitives (FEAT-039/S09).

The general operators and the surface-chain operators live in separate package
modules; the primitives both of them use live here so neither module has to
import the other.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidatorFunctionWrapHandler,
    WrapValidator,
)
from pydantic_core import PydanticCustomError


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
