"""Compatibility exports; implementation lives in :mod:`creo_mechdog.seeds`."""

from typing import Any as _Any

from creo_mechdog import seeds as _implementation

__all__ = [name for name in vars(_implementation) if not name.startswith("_")]


def __getattr__(name: str) -> _Any:
    return getattr(_implementation, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_implementation)))


if __name__ == "__main__":
    raise SystemExit(_implementation.main())
