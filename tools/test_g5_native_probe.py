"""Q07 G5 native feasibility probe driver: offline contract/oracle checks.

Evidence boundaries fixed by this task:

* Default is strictly offline. No MCP client is created, no Toolkit call is
  made, no native build is triggered, no Creo session is touched. The offline
  stage validates the frozen G5 contract (field names, reference rules, oracle
  definitions) against the repository sources and computes the three minimal
  geometry oracles independently.
* A live run requires BOTH --live and --confirm-session-usable. The live stage
  is NOT implemented by this task: the three native probes still need the
  FEAT-009 / FEAT-039 implementations that consume this contract. This driver
  therefore refuses a live run with a clear message instead of pretending to
  have executed native probes.
* The three native probe steps (goal, what to create, what tree to extract,
  what to compare) are defined here as data so the integrator runs exactly the
  same probes the contract freezes, and records "feasible / route not
  established / unverified" for each.
* Element and enum identifiers are never hardcoded numerically: they are
  resolved by SDK symbol name through the tools/generate_constants.py
  mechanism. The offline stage verifies which symbols the current HEADERS
  list already exports, without reading or copying native/constants.inc.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

CONTRACT = ROOT / "docs" / "development" / "G5-NATIVE-CONTRACT.md"

# --- frozen contract surface ------------------------------------------------

# Element / enum symbols the three ops need. Values are never written down:
# every name is resolved by symbol through tools/generate_constants.py.
REQUIRED_SDK_SYMBOLS: dict[str, list[str]] = {
    "surface_loft": [
        "PRO_E_FEATURE_TREE",
        "PRO_E_FEATURE_TYPE",
        "PRO_E_FEATURE_FORM",
        "PRO_E_DTM_SRF_TYPE",
        "PRO_E_DTM_SRF_TYPE_BND_BLEND",
        "PRO_E_BNBLN_CURVES",
        "PRO_E_BNBLN_1DIR",
        "PRO_E_BNBLN_DIR_CURVES",
        "PRO_E_STD_CHAIN_HOLDER",
        "PRO_E_STD_CURVE_COLLECTION_APPL",
        "PRO_E_CTRL_PTS",
        "PRO_E_BLEND_TYPE",
        "PRO_FEAT_DATUM_SURF",
        "PRO_USE_SURFS",
    ],
    "project_curve": [
        "PRO_E_COPYTRIM_QUILT",
        "PRO_E_COPYTRIM_CURVES",
        "PRO_E_COPYTRIM_CURVE_TBL",
        "PRO_E_COPYTRIM_CURVE_DATA",
        "PRO_E_COPYTRIM_CURVE",
        "PRO_E_FEATURE_TYPE",
        "PRO_FEAT_CURVE",
    ],
    "surface_trim": [
        "PRO_E_FEATURE_TYPE",
        "PRO_E_FEATURE_FORM",
        "PRO_E_SRF_TRIM_TYPE",
        "PRO_E_SURF_TRIM_TYPE",
        "PRO_E_TRIM_QUILT",
        "PRO_E_STD_USEQLT_QLT",
        "PRO_E_MATERIAL_SIDE",
        "PRO_E_PRIMARY_QLTSIDE",
        "PRO_E_KEEP_TRIM_SURF_OPT",
        "PRO_SURF_TRIM_USE_QLT",
        "PRO_TRIM_MATL_SIDE_ONE",
        "PRO_TRIM_PRIM_QLT_SIDE_ONE",
        "PRO_TRIM_PRIM_QLT_SIDE_TWO",
        "PRO_KEEP_TRIM_SURF_OPT_NO",
        "PRO_FEAT_CUT",
        "PRO_USE_SURFS",
    ],
}

# Headers that declare the symbols the current HEADERS list does not export.
# Adding them is a shared change collected by the integrator.
MISSING_HEADER_SOURCES: dict[str, str] = {
    "PRO_E_DTM_SRF_TYPE_BND_BLEND": "Probbl.h",
    "PRO_SURF_TRIM_USE_QLT": "ProTrim.h",
    "PRO_TRIM_MATL_SIDE_ONE": "ProTrim.h",
    "PRO_TRIM_PRIM_QLT_SIDE_ONE": "ProTrim.h",
    "PRO_TRIM_PRIM_QLT_SIDE_TWO": "ProTrim.h",
    "PRO_KEEP_TRIM_SURF_OPT_NO": "ProTrim.h",
    "PRO_SEC_SKETCH": "ProStdSection.h",
    "PRO_SEC_SELECT": "ProStdSection.h",
    "PRO_SRF_MRG_JOIN": "ProMerge.h",
}

MEASUREMENT_APIS: dict[str, str] = {
    "surface_area": "ProSurfaceAreaEval(ProSurface, double*) - ProSurface.h",
    "region_area": "ProContourAreaEval(ProSurface, ProContour, double*) - ProContour.h",
    "quilt_volume_closed_only": "ProQuiltVolumeEval(ProQuilt, double*) - ProQuilt.h",
    "curve_length": "ProCurveLengthEval(ProCurve, double*) - ProCurve.h",
    "curve_endpoints": "ProCurveXyzdataEval(ProCurve, param, xyz, d1, d2) - ProCurve.h",
}

# Symbols the 0.10.0 feedback proposal used that this machine's SDK does not
# have. They must never appear in code, examples or documentation.
REJECTED_PROPOSAL_SYMBOLS: list[str] = [
    "PRO_E_BLEND_SECTIONS",
    "PRO_E_BLEND_ATTRIBUTES",
    "PRO_BLEND_SURF",
    "PRO_STD_BLEND",
    "ProSurfaceEval",
    "ProMeasurable",
]

# Old native routes keep their recorded outcome instead of being silently
# dropped. "route_not_established" is a fact about the probe, not a failure of
# a later implementation, and only real evidence may move an entry to feasible.
ROUTE_HISTORY: list[dict[str, str]] = [
    {
        "route": "surface_loft: Probbl.h boundary blend from two straight sections",
        "task": "S05 / FEAT-009",
        "status": "route_not_established",
        "evidence": "the earlier local probe produced no regenerated feature; the "
        "UNREGENERATED evidence is kept, so a compiled entry is not a capability",
    },
    {
        "route": "project_curve: PRO_E_COPYTRIM_* feature tree",
        "task": "S04 / FEAT-039",
        "status": "unverified",
        "evidence": "no creatable tree has been shown on this machine; the "
        "ProDtmCrv intersect route is not an equivalent of a curve projection",
    },
    {
        "route": "surface_trim: ProTrim.h use-quilt variant",
        "task": "S02 / FEAT-039",
        "status": "feasible",
        "evidence": "live 2026-11-04 on this machine (Creo 12.4.0.0), two independent "
        "models: a 40x20 fill cut at x=5 by a datum plane measured 700 mm2 for "
        "keep_side=one and 100 mm2 for two with the retained bbox on the matching "
        "side, a cylinder measured 314.16/942.48, both saved and reloaded. The "
        "binding is driven by PRO_E_MATERIAL_SIDE, not PRO_E_PRIMARY_QLTSIDE alone, "
        "and a datum-plane tool needs an axis/id reference because a label is not "
        "honoured; both corrections are in build/_live_trim_report.json and "
        "build/surface_chain/20261104-094447-635200/report.json",
    },
]

# --- frozen oracles ---------------------------------------------------------
ORACLES: list[dict[str, Any]] = [
    {
        "id": "O1",
        "op": "surface_loft",
        "description": "Two parallel straight sections -> rectangular surface",
        "sections_mm": {"length": 40.0, "separation": 20.0},
        "expected_area_mm2": 800.0,
        "tolerance_mm2": 0.5,
        "extra_assertions": [
            "feature type is a datum surface (not a solid)",
            "the echoed sections keep the submitted order",
            "exactly one quilt geometry item exists on the produced feature",
        ],
    },
    {
        "id": "O2",
        "op": "project_curve",
        "description": "A 30 mm line at z=10 projected along -Z onto a 40x20 planar target at z=0",
        "target_plane_mm": {"width": 40.0, "height": 20.0, "z": 0.0},
        "source_line_mm": {
            "length": 30.0,
            "from": [5.0, 10.0, 10.0],
            "to": [35.0, 10.0, 10.0],
            "z": 10.0,
        },
        "direction": [0.0, 0.0, -1.0],
        "expected_curve_length_mm": 30.0,
        "expected_endpoint_z": 0.0,
        "tolerance_mm": 0.5,
        "endpoint_tolerance_mm": 1e-6,
        "extra_assertions": [
            "the projected endpoints stay inside the target plane's domain",
            "the projected endpoints are not the source endpoints (z=10)",
            "projecting the other way yields no intersection and never echoes the source line",
        ],
    },
    {
        "id": "O2b",
        "op": "project_curve",
        "description": "Cylindrical target: definition pending, never a passing criterion",
        "status": "definition_pending",
        "withdrawn_oracle": "20 mm tall cylinder carrying a 30 mm source line",
        "why_withdrawn": "the source line is taller than the carrying surface, so the old "
        "oracle had no self-consistent expected value",
        "required_before_freeze": [
            "cylinder domain: circumferential angular interval and axial interval",
            "source curve domain",
            "relation between the projection direction and the surface normal",
            "branch rule when the source curve crosses both sides of the cylinder",
        ],
    },
    {
        "id": "O3",
        "op": "surface_trim",
        "description": "Rectangular surface bisected by a datum plane",
        "rectangle_mm": {"width": 40.0, "height": 20.0},
        "expected_area_before_mm2": 800.0,
        "expected_area_after_mm2": 400.0,
        "tolerance_mm2": 0.5,
        "conservation_tolerance_mm2": 1.0,
        "kept_side_domains_mm": {"one": [[0.0, 20.0]], "two": [[20.0, 40.0]]},
        "extra_assertions": [
            "each keep_side keeps the measured x interval declared here",
            "the signed offsets of the two runs have opposite signs",
            "quilt ids are compared only between two runs on the same model and revision",
        ],
    },
]

# --- frozen native probes ----------------------------------------------------

PROBES: list[dict[str, Any]] = [
    {
        "id": "P1",
        "op": "surface_loft",
        "goal": "Decide whether the Probbl.h boundary-blend tree can be created "
        "in the executor from two straight sections and yields a measurable area.",
        "create": [
            "new part with default datums",
            "two independent open straight-line sketches, 40 mm long, parallel, "
            "separated by 20 mm (oracle O1)",
            "PRO_E_FEATURE_TYPE=PRO_FEAT_DATUM_SURF, "
            "PRO_E_FEATURE_FORM=PRO_USE_SURFS, "
            "PRO_E_DTM_SRF_TYPE=PRO_E_DTM_SRF_TYPE_BND_BLEND",
            "PRO_E_BNBLN_CURVES/PRO_E_BNBLN_1DIR/PRO_E_BNBLN_DIR_CURVES holding two "
            "chain holders, each with PRO_E_STD_CHAIN_HOLDER/"
            "PRO_E_STD_CURVE_COLLECTION_APPL for one curve",
        ],
        "extract": [
            "ProFeatureElemtreeExtract of the produced feature (symbol names only)",
            "ProFeatureTypeGet feature type",
            "ProFeatureGeomitemVisit quilt geometry item count",
            "ProContourAreaEval / ProSurfaceAreaEval area",
        ],
        "compare": [
            "area == 800.0 mm2 (+/- 0.5)",
            "feature type == PRO_FEAT_DATUM_SURF, exactly one quilt item",
            "extracted tree versus the contract skeleton, item by item",
            "actual PRO_E_BLEND_TYPE value",
        ],
        "verdicts": ["feasible", "route not established", "unverified"],
        "blocks_on_failure": ["Q08 surface_loft"],
    },
    {
        "id": "P2",
        "op": "project_curve",
        "goal": "Decide whether the PRO_E_COPYTRIM_* family forms a creatable "
        "feature tree and fix the physical meaning of side=positive/negative.",
        "create": [
            "new part",
            "cylindrical surface quilt via extrude mode=surface of a circle, "
            "radius 10 mm, height 20 mm, axis along Z (oracle O2)",
            "one straight source line parallel to Z, 30 mm long, at radius 15 mm",
            "PRO_E_FEATURE_TYPE=PRO_FEAT_CURVE with PRO_E_COPYTRIM_CURVE_DATA "
            "holding PRO_E_COPYTRIM_QUILT and PRO_E_COPYTRIM_CURVE_TBL/"
            "PRO_E_COPYTRIM_CURVE",
            "on failure, record the raw ProError and every ProErrorlist entry, "
            "then try the ProDtmCrv.h PRO_CURVE_TYPE_INTSRF / PRO_CURVE_TYPE_TWO_PROJ "
            "variants and state explicitly that their semantics differ",
        ],
        "extract": [
            "extracted element tree and raw error codes",
            "produced curve geometry id, ProCurveLengthEval length, ProCurveXyzdataEval endpoints",
            "endpoint difference between side=positive and side=negative",
        ],
        "compare": [
            "curve length == 30.0 mm (+/- 0.5)",
            "endpoint z span == 30.0 mm (+/- 0.5)",
            "endpoint radius == 10.0 mm (+/- 0.5), not the source radius 15 mm",
            "the two side values give different endpoints",
        ],
        "verdicts": ["feasible", "route not established", "unverified"],
        "blocks_on_failure": ["Q09 project_curve"],
    },
    {
        "id": "P3",
        "op": "surface_trim",
        "goal": "Decide whether the ProTrim.h use-quilt tree can be created and "
        "fix the physical binding of keep_side one/two.",
        "create": [
            "new part",
            "40 x 20 mm planar rectangle quilt via surface_fill (oracle O3)",
            "a datum plane at x=5 (normal +X) as the trimming tool, referenced "
            "geometrically ({kind:'datum_plane',axis:'x'}); a label on that kind is "
            "dropped by the resolver and must not be used",
            "PRO_E_FEATURE_TYPE=PRO_FEAT_CUT, PRO_E_FEATURE_FORM=PRO_USE_SURFS, "
            "PRO_E_SRF_TRIM_TYPE=PRO_SURF_TRIM_USE_QLT and "
            "PRO_E_SURF_TRIM_TYPE=PRO_SURF_TRIM_USE_QLT, PRO_E_TRIM_QUILT=target, "
            "PRO_E_STD_USEQLT_QLT=datum plane, "
            "PRO_E_KEEP_TRIM_SURF_OPT=PRO_KEEP_TRIM_SURF_OPT_NO",
            "run twice: PRO_E_MATERIAL_SIDE=PRO_TRIM_MATL_SIDE_ONE with "
            "PRO_E_PRIMARY_QLTSIDE=PRO_TRIM_PRIM_QLT_SIDE_ONE, then both TWO",
        ],
        "extract": [
            "extracted element tree and raw error codes",
            "kept quilt geometry id, area, tool normal, target and kept centroids",
        ],
        "compare": [
            "area before == 800.0 mm2 (+/- 0.5)",
            "an asymmetric cut is required: sides of the x=5 cut measure 700 and 100 mm2, "
            "a cut at x=20 leaves 400 mm2 on both sides and proves nothing",
            "the two area-after values are 700.0 and 100.0 mm2 (+/- 0.5), summing to the "
            "area before (+/- 1.0)",
            "each retained bbox lies on its measured side (x 5..40 and x 0..5)",
            "the two signed offsets have opposite signs; signed_offset_mm may be null "
            "when no quilt centroid query exists",
        ],
        "verdicts": ["feasible", "route not established", "unverified"],
        "blocks_on_failure": ["Q10 surface_trim"],
    },
]


# --- offline checks ---------------------------------------------------------


def _resolve_sdk_include_dir() -> Path | None:
    """Locate the local Toolkit include directory without touching any config.

    The SDK root comes from the machine's ``config.json``. That file lives in
    the checkout the worktree was branched from, not in the worktree itself,
    so sibling checkouts are scanned read-only. Nothing is written and no
    configuration is modified.
    """
    candidates: list[Path] = []
    env_root = os.environ.get("MECHDOG_CREO_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    config_files: list[Path] = [ROOT / "config.json"]
    for parent in (ROOT.parent,):
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            if child.is_dir() and (child / "config.json").is_file():
                config_files.append(child / "config.json")
    for config in config_files:
        try:
            settings = json.loads(config.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        root = settings.get("creo_root")
        if root:
            candidates.append(Path(root))
    for root in candidates:
        include = root / "Common Files" / "protoolkit" / "includes"
        if include.is_dir():
            return include
    return None


def _resolve_symbols(include_dir: Path, headers: list[str]) -> set[str]:
    """Mirror tools/generate_constants.py name extraction, read-only."""
    found: set[str] = set()
    for header in headers:
        source = (include_dir / header).read_text(encoding="utf-8", errors="replace")
        source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
        found.update(
            re.findall(
                r"^\s*#define\s+(PRO_(?:E|FEAT)_[A-Z0-9_]+)\s+(?:\d+|\([^\n]+\))", source, re.M
            )
        )
        for block in re.findall(r"\benum\s*\w*\s*\{([^}]+)\}", source, re.S):
            found.update(re.findall(r"(?:^|,)\s*(PRO_[A-Z0-9_]+)\s*(?:=|,|$)", block, re.M))
    return found


def check_sdk_symbols() -> dict:
    """Report which required symbols the SDK declares and which the HEADERS list exports."""
    from tools.generate_constants import HEADERS

    include_dir = _resolve_sdk_include_dir()
    report: dict[str, Any] = {
        "include_dir": str(include_dir) if include_dir else None,
        "headers_listed": len(HEADERS),
        "ops": {},
    }
    if include_dir is None:
        report["status"] = "sdk_include_dir_not_found"
        report["note"] = (
            "The local Toolkit include directory was not found. The symbol table "
            "was not verified on this machine; the contract's SDK conclusions stay "
            "as recorded on the machine where Q07 ran."
        )
        return report
    exported = _resolve_symbols(include_dir, sorted(set(HEADERS)))
    # The full SDK scan answers "does this symbol exist at all", independently
    # of whether the generate_constants HEADERS list reaches it.
    all_sdk = _resolve_symbols(include_dir, [p.name for p in sorted(include_dir.glob("*.h"))])
    for op, symbols in REQUIRED_SDK_SYMBOLS.items():
        rows = []
        for symbol in symbols:
            if symbol in exported:
                status = "exported_by_headers"
                source = "HEADERS"
                addition = None
            elif symbol in all_sdk:
                status = "declared_in_sdk_header_not_listed"
                source = MISSING_HEADER_SOURCES.get(symbol, "unknown header")
                addition = source
            else:
                status = "absent_from_sdk"
                source = None
                addition = None
            rows.append(
                {
                    "symbol": symbol,
                    "status": status,
                    "declared_in": source,
                    "required_header_addition": addition,
                }
            )
        report["ops"][op] = rows
    report["status"] = "checked"
    report["summary"] = {
        op: {
            "exported_by_headers": sum(1 for row in rows if row["status"] == "exported_by_headers"),
            "declared_in_sdk_header_not_listed": sum(
                1 for row in rows if row["status"] == "declared_in_sdk_header_not_listed"
            ),
            "absent_from_sdk": sum(1 for row in rows if row["status"] == "absent_from_sdk"),
        }
        for op, rows in report["ops"].items()
    }
    return report


def check_rejected_proposal_symbols() -> dict:
    """The 0.10.0 proposal's names must not exist in this machine's SDK."""
    include_dir = _resolve_sdk_include_dir()
    rows = []
    for symbol in REJECTED_PROPOSAL_SYMBOLS:
        found = False
        where = None
        if include_dir is not None:
            for header in sorted(include_dir.glob("*.h")):
                source = header.read_text(encoding="utf-8", errors="replace")
                if re.search(r"\b" + re.escape(symbol) + r"\b", source):
                    found = True
                    where = header.name
                    break
        rows.append(
            {
                "symbol": symbol,
                "present_in_sdk": found,
                "declared_in": where,
                "verdict": "must not be used" if not found else "review before use",
            }
        )
    return {
        "include_dir": str(include_dir) if include_dir else None,
        "symbols": rows,
        "note": (
            "Symbols absent from the SDK cannot be resolved by the "
            "tools/generate_constants.py mechanism and must not appear in code."
        ),
    }


# Every marker the frozen contract must keep. The offline stage fails when one
# disappears, so a later edit cannot quietly unfreeze part of the surface.
REQUIRED_CONTRACT_MARKERS: list[str] = [
    "# G5 曲面链路原生契约",
    "## 0.1 S00 修订记录",
    "ID 类型规则",
    "quilt_id",
    "O2b project_curve",
    "两侧产物必须不同",
    "允许已受理 job 失败",
    "## 1. SDK 逐项核实结论表",
    "## 2. 预期原生元素树",
    "## 3. 第一版能力边界",
    "## 4. 冻结的 schema 与测量契约",
    "## 5. 最小几何 oracle",
    "## 6. 给 Q08–Q10 的确切交接",
    "## 7. 实机原生探针清单",
    "## 8. 未验证范围",
    "surface_area_mm2",
    "curve_length_mm",
    "endpoints_mm",
    "area_before_mm2",
    "area_after_mm2",
    "kept_side",
    "kept_side_basis",
    "surface_area_status",
    "curve_length_status",
    "endpoints_status",
    "area_before_status",
    "area_after_status",
    "native/surface_measure.h",
    "PRO_E_BNBLN_CURVES",
    "PRO_E_COPYTRIM_QUILT",
    "PRO_E_SRF_TRIM_TYPE",
    "PRO_SURF_TRIM_USE_QLT",
    "PRO_TRIM_PRIM_QLT_SIDE_ONE",
    "PRO_E_DTM_SRF_TYPE_BND_BLEND",
    "PRO_E_TRIM_QLT_SIDE",
    "ProSurfaceAreaEval",
    "ProContourAreaEval",
    "ProCurveLengthEval",
    "ProCurveXyzdataEval",
    "SurfaceLoftOp",
    "ProjectCurveOp",
    "SurfaceTrimOp",
    "generic_surface_loft",
    "generic_project_curve",
    "generic_surface_trim",
]


def check_contract_document() -> dict:
    """The contract must exist and keep every frozen surface the driver relies on."""
    if not CONTRACT.is_file():
        raise AssertionError(f"frozen contract missing: {CONTRACT}")
    text = CONTRACT.read_text(encoding="utf-8")
    missing = [item for item in REQUIRED_CONTRACT_MARKERS if item not in text]
    assert not missing, {"contract_missing": missing}
    for symbol in REJECTED_PROPOSAL_SYMBOLS:
        # The contract must name the rejected symbols only to reject them.
        assert symbol in text, f"contract must record the rejected symbol: {symbol}"
    return {
        "path": str(CONTRACT.relative_to(ROOT).as_posix()),
        "bytes": len(text.encode("utf-8")),
        "required_markers": len(REQUIRED_CONTRACT_MARKERS),
        "status": "complete",
    }


def check_oracles() -> dict:
    """Recompute every oracle's closed form independently of any native run."""
    rows = []
    for oracle in ORACLES:
        if oracle["id"] == "O1":
            length = oracle["sections_mm"]["length"]
            separation = oracle["sections_mm"]["separation"]
            area = length * separation
            assert abs(area - oracle["expected_area_mm2"]) < 1e-9, oracle
        elif oracle["id"] == "O2":
            start = oracle["source_line_mm"]["from"]
            end = oracle["source_line_mm"]["to"]
            assert abs(start[2] - oracle["source_line_mm"]["z"]) < 1e-9, oracle
            span = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
            assert abs(span - oracle["source_line_mm"]["length"]) < 1e-9, oracle
            assert abs(span - oracle["expected_curve_length_mm"]) < 1e-9, oracle
            # The source line must sit off the target plane, otherwise a real
            # projection and an echoed input would be indistinguishable.
            assert abs(start[2] - oracle["target_plane_mm"]["z"]) > 1e-6, oracle
            # Domain: the projected endpoints must be inside the target surface.
            half_width = oracle["target_plane_mm"]["width"] / 2.0
            half_height = oracle["target_plane_mm"]["height"] / 2.0
            assert 0.0 <= start[0] <= 2 * half_width, oracle
            assert 0.0 <= end[0] <= 2 * half_width, oracle
            assert 0.0 <= start[1] <= 2 * half_height, oracle
            assert 0.0 <= end[1] <= 2 * half_height, oracle
        elif oracle["id"] == "O2b":
            # Never a passing criterion: it must stay explicitly unfrozen.
            assert oracle["status"] == "definition_pending", oracle
            assert oracle["required_before_freeze"], oracle
        else:
            width = oracle["rectangle_mm"]["width"]
            height = oracle["rectangle_mm"]["height"]
            area = width * height
            assert abs(area - oracle["expected_area_before_mm2"]) < 1e-9, oracle
            half = width / 2.0 * height
            assert abs(half - oracle["expected_area_after_mm2"]) < 1e-9, oracle
            assert (
                abs(2 * half - oracle["expected_area_before_mm2"])
                <= oracle["conservation_tolerance_mm2"]
            ), oracle
            # The two keep sides must be told apart by measured position, not by
            # comparing quilt ids across models.
            domains = oracle["kept_side_domains_mm"]
            assert domains["one"] != domains["two"], oracle
        rows.append(oracle)
    return {"count": len(rows), "oracles": rows}


def check_reference_rules() -> dict:
    """The reference kinds the three ops allow must exist in the shared schema."""
    allowed = {"quilt_feature", "curve", "datum_plane", "datum_axis_feature", "edge"}
    source = (ROOT / "src" / "creo_mechdog" / "schema.py").read_text(encoding="utf-8")
    for kind in allowed:
        assert f'"{kind}"' in source, f"reference kind not registered in schema.py: {kind}"
    # A quilt reference must resolve to exactly one quilt geometry item; the
    # native resolver enforces that and the contract freezes the rule.
    native = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
    assert "quilt_feature" in native
    assert "Feature reference must identify exactly one geometry item" in native
    # S00 R1: an explicit quilt geometry id is a native resolver kind, not a
    # schema-only alias, and it is never interchangeable with a surface id.
    assert 'kind == "quilt"' in native or '|| kind == "quilt"' in native, (
        "native resolver must accept {kind:'quilt', id}"
    )
    contract = CONTRACT.read_text(encoding="utf-8")
    assert "ID 类型规则" in contract
    assert "surface_id" in contract and "quilt_id" in contract
    return {
        "allowed_reference_kinds": sorted(allowed),
        "native_only_reference_kinds": ["quilt"],
        "uniqueness_rule": "exactly one geometry item per reference; zero or many is rejected",
        "body_boolean_not_allowed": True,
        "quilt_and_surface_ids_interchangeable": False,
    }


def check_measurement_apis() -> dict:
    """The measurement APIs the contract names must exist in the local SDK."""
    include_dir = _resolve_sdk_include_dir()
    rows = []
    for name, description in MEASUREMENT_APIS.items():
        symbol = description.split("(")[0].strip()
        declared = False
        where = None
        if include_dir is not None:
            for header in sorted(include_dir.glob("*.h")):
                source = header.read_text(encoding="utf-8", errors="replace")
                if re.search(r"\b" + re.escape(symbol) + r"\s*\(", source):
                    declared = True
                    where = header.name
                    break
        rows.append(
            {
                "api": symbol,
                "description": description,
                "declared_in_sdk": declared,
                "header": where,
            }
        )
    return {"apis": rows, "include_dir": str(include_dir) if include_dir else None}


def check_route_history() -> dict:
    """Old native routes keep an explicit status; none is silently promoted."""
    statuses = {"feasible", "route_not_established", "unverified"}
    for entry in ROUTE_HISTORY:
        assert entry["status"] in statuses, entry
        assert entry["evidence"], entry
        assert entry["route"] and entry["task"], entry
    return {
        "count": len(ROUTE_HISTORY),
        "statuses": [entry["status"] for entry in ROUTE_HISTORY],
        "routes": ROUTE_HISTORY,
    }


def check_probe_plan() -> dict:
    """The three native probes must be complete and mutually exclusive in blocking."""
    ids = [probe["id"] for probe in PROBES]
    assert ids == ["P1", "P2", "P3"], ids
    blocked = [probe["blocks_on_failure"] for probe in PROBES]
    assert blocked == [["Q08 surface_loft"], ["Q09 project_curve"], ["Q10 surface_trim"]], blocked
    for probe in PROBES:
        for key in ("goal", "create", "extract", "compare", "verdicts"):
            assert probe.get(key), (probe["id"], key)
        assert probe["verdicts"] == ["feasible", "route not established", "unverified"]
    return {"probes": PROBES}


# --- report plumbing --------------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "g5_native_probe" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance as collect

    evidence = collect(
        ROOT,
        (
            "docs/development/G5-NATIVE-CONTRACT.md",
            "tools/test_g5_native_probe.py",
            "tools/generate_constants.py",
            "src/creo_mechdog/schema.py",
            "native/generic.cpp",
            "native/surfaces.cpp",
            "native/blend_create.cpp",
        ),
    )
    return {
        "version": evidence["version"],
        "commit": evidence["commit"],
        "branch": evidence["branch"],
        "dirty": evidence["dirty"],
        "git_status": evidence["git_status"],
        "source_sha256": evidence["source_sha256"],
        "source_fingerprint": evidence["source_fingerprint"],
        "environment": evidence["environment"],
        "creo_connected": False,
        "native_build_triggered": False,
    }


def write_offline_report(output: Path, run_id: str, checks: dict) -> dict:
    report = {
        "task": "Q07 G5 feasibility and interface freeze (FEAT-009 / FEAT-039)",
        "scope": "G5 native contract freeze: SDK symbol verification, frozen schema "
        "and measurement surface, three minimal geometry oracles, three native probes",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: the frozen contract was checked against the "
            "repository sources, the SDK symbol table was resolved by symbol name "
            "through the tools/generate_constants.py mechanism, and the three "
            "geometry oracles were recomputed analytically. No MCP client, no "
            "Toolkit call, no native build, no Creo connection. The three native "
            "probes are defined but not executed; they remain the integrator's "
            "serial live-window work."
        ),
        "checks": checks,
        "provenance": local_provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    if args.live:
        print(
            "LIVE NOT IMPLEMENTED by Q07: the three native probes need the "
            "FEAT-009 / FEAT-039 implementations that consume "
            "docs/development/G5-NATIVE-CONTRACT.md. No job was submitted, no "
            "Creo session was contacted. Run the offline stage for the frozen "
            "probe steps, then execute them in the approved serial live window.",
            file=sys.stderr,
        )
        return 2

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    checks = {
        "contract_document": check_contract_document(),
        "sdk_symbols": check_sdk_symbols(),
        "rejected_proposal_symbols": check_rejected_proposal_symbols(),
        "measurement_apis": check_measurement_apis(),
        "oracles": check_oracles(),
        "reference_rules": check_reference_rules(),
        "probe_plan": check_probe_plan(),
        "route_history": check_route_history(),
    }
    write_offline_report(output, run_id, checks)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print("sdk_symbols: " + json.dumps(checks["sdk_symbols"].get("summary", {}), sort_keys=True))
    print("native_acceptance: not_run (offline stage only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
