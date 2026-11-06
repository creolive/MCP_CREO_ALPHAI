"""DEV-051 T11 / FEAT-014 offline contract: bend-end relief for four-wall flanges.

Second-batch T11 takes the T05 failure candidate (185 x 232 x 1 mm base wall plus
four h80 / R2.54 / Y0.5 flanges) and the confirmed T03 thin wall as input. This
module is the offline half: it freezes what the installed Creo 12.4 Toolkit
actually exposes for relief, what the MCP contract admits, what the native tree
must therefore contain, and what geometry a live run has to confirm.

Scope of the offline design:

* one relief shape only -- ``rectangular`` with a caller-supplied blind width and
  depth in model units -- plus the compatibility default ``none``, which keeps
  both bend ends at ``PRO_BEND_RLF_NONE`` exactly as before T11;
* no automatic corner rule and no thickness-derived defaults: rip, stretch,
  obround, param, corner relief, miter cuts and edge rips stay unsupported;
* relief is a creation-time property; the named ``height`` dimension keeps its
  existing edit path and there is no in-place relief redefine.

Nothing here creates a flange. The corner overlap and the relief removal are
independent arithmetic on the T05 geometry, not native measurements.
"""

from __future__ import annotations

import math
import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations
from tests.unit import test_sheetmetal_flange as fx

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE = REPO_ROOT / "native" / "advanced.cpp"
SERVER = REPO_ROOT / "server.py"

# --- Creo 12.4 Toolkit facts, transcribed from the installed SDK -----------
SDK_VERSION = "Creo 12.4.0.0"
SDK_HEADER = "Common Files/protoolkit/includes/ProSmtFlangeWall.h"
# ProBendRlfType (ProSmtFlangeWall.h)
RELIEF_TYPES = {"none": 0, "rip": 1, "stretch": 2, "rectangular": 3, "obround": 4, "param": 5}
# ProBendRlfDepthType, expressed through ProSmdRelType (PRO_DIM_*)
RELIEF_DEPTH_TYPES = {
    "not_used": -1,
    "blind": -4,
    "up_to_bend": -7,
    "tan_to_bend": -8,
    "param": -25,
}
# ProCornerRelType, the sibling compound PRO_E_SMT_CORNER_RELIEF in the same tree
CORNER_RELIEF_TYPES = {
    "v_notch": 0,
    "circular": 1,
    "rectangular": 2,
    "obround": 3,
    "no": 5,
    "param": 6,
    "square": 7,
    "normal": 8,
}
SUPPORTED_RELIEF_TYPES = ("none", "rectangular")
UNSUPPORTED_RELIEF_TYPES = ("rip", "stretch", "obround", "param")
NOT_IMPLEMENTED_CORNER_RULES = ("corner_relief", "miter_cut", "edge_rip")

# SDK notes 5-7 (ProSmtEditBendRelief.h) restate the relief constraints for the
# same elements: width is mandatory and positive for every type except rip,
# depth type is mandatory for the same set and tan-to-bend only fits obround,
# and blind depth is mandatory and measured from the bend edge.
WIDTH_REQUIRED_TYPES = ("stretch", "rectangular", "obround", "param")
DEPTH_TYPE_REQUIRED_TYPES = WIDTH_REQUIRED_TYPES
TAN_TO_BEND_TYPES = ("obround",)


# --- request fixtures -----------------------------------------------------


def flange_op(relief: dict | None = None, **overrides) -> dict:
    op = {
        "op": "sheetmetal_flange",
        "label": "f_px",
        "edge": {"kind": "edge", "id": 211},
        "height": fx.FLANGE_HEIGHT_MM,
        "angle": fx.FLANGE_ANGLE_DEG,
        "radius": fx.FLANGE_RADIUS_MM,
        "flip": False,
        "y_factor": fx.FLANGE_Y_FACTOR,
    }
    if relief is not None:
        op["relief"] = relief
    op.update(overrides)
    return op


def validated(relief: dict | None = None, **overrides) -> dict:
    return validate_operations([flange_op(relief, **overrides)])[0]


def rejected(test: unittest.TestCase, relief: dict | None, needle: str, **overrides):
    with test.assertRaises(Exception) as caught:
        validate_operations([flange_op(relief, **overrides)])
    test.assertIn(needle, str(caught.exception))


def relief_rectangular(width: float, depth: float, ends: str = "both") -> dict:
    payload: dict = {"type": "rectangular", "width": width, "depth": depth}
    if ends != "both":
        payload["ends"] = ends
    return payload


def expected_native_sides(relief: dict | None) -> dict:
    """Independent model of the documented element rules, not production code."""
    if relief is None or relief.get("type", "none") == "none":
        return {"side1": "none", "side2": "none"}
    ends = relief.get("ends", "both")
    enabled = {"both": ("side1", "side2"), "side1": ("side1",), "side2": ("side2",)}[ends]
    return {side: "rectangular" if side in enabled else "none" for side in ("side1", "side2")}


def relief_removed_mm3(relief: dict | None, thickness: float = fx.PLATE_THICKNESS_MM) -> float:
    """A rectangular notch removes width x depth x thickness per enabled bend end."""
    if relief is None or relief.get("type", "none") == "none":
        return 0.0
    ends = 2 if relief.get("ends", "both") == "both" else 1
    return ends * float(relief["width"]) * float(relief["depth"]) * thickness


def corner_overlap_run_mm() -> float:
    """Wall run that shares a corner: height minus the bend radius (T05 bound)."""
    return max(0.0, fx.FLANGE_HEIGHT_MM - fx.FLANGE_RADIUS_MM)


# --- DEV-051 T11 2026-10-30: valid-material relief scenario ----------------
#
# The 2026-10-29 round six proved only that free plate corners remove nothing:
# both measured flanges terminated at plate corners, so "no notch" was the
# expected outcome there and says nothing about whether a relief cuts material.
# This scenario gives every relief variant a bend end that abuts existing
# material -- without using the failing third wall as the only entrance. The
# 2026-10-30 T05 contrast later proved that an attach-edge end adjacent to an
# existing bend fails flange regeneration, so whether f_ny after f_px builds at
# all (and whether its relief changes that) is exactly what the live run must
# observe; it is not guaranteed to stay buildable.
#
# Geometry: base wall 185x232x1, then f_px on +x (both bend ends at free plate
# corners), then f_ny on -y. f_ny's chain end at the +x corner runs into f_px's
# bend (one material end); its -x chain end stays a free plate corner. The
# 2026-10-29 run observed such chains trimmed by R + t per material end.

MATERIAL_SCENARIO = {
    "first": {"side": "+x", "label": "f_px", "material_ends": 0},
    "second": {"side": "-y", "label": "f_ny", "material_ends": 1},
}

# Per-material-end chain shortening observed on 2026-10-29: the bend of the
# existing wall occupies R + t of the neighbour edge.
CHAIN_TRIM_MM = fx.FLANGE_RADIUS_MM + fx.PLATE_THICKNESS_MM

# Round six of 2026-10-29 measured +18 025.291234 mm3 for the untrimmed h80 /
# R2.54 / Y0.5 flange over a 232 mm span; the model below reproduces it.
ROUND_SIX_MEASURED_INCREMENT_MM3 = 18_025.291234
ROUND_SIX_MEASURED_SPAN_MM = 232.0

# A rectangular notch only removes material where the notch footprint sits in
# material; the delta verdict never accepts a request echo alone.
RELIEF_DELTA_TOLERANCE_MM3 = 0.2


def bent_wall_increment_mm3(span_mm: float, trimmed_ends: float = 0.0) -> float:
    """Independent bent-flange increment, validated against the 2026-10-29 run.

    Cross-section = straight run (height - t - R) plus the net bend zone. The
    bend zone replaces the plate corner rectangle it occupies, so its net
    contribution is the quarter annulus minus the t x (R + t) rectangle. Each
    material end shortens the sweep by the observed chain trim (R + t).
    """
    t = fx.PLATE_THICKNESS_MM
    r = fx.FLANGE_RADIUS_MM
    h = fx.FLANGE_HEIGHT_MM
    effective = span_mm - trimmed_ends * CHAIN_TRIM_MM
    flat = h - t - r
    bend_net = math.pi / 4.0 * ((r + t) ** 2 - r**2) - t * (r + t)
    return effective * (flat + bend_net)


def notch_removed_mm3(width: float, depth: float, ends_with_material: int) -> float:
    """w x d x t per bend end whose chain end actually abuts material."""
    return ends_with_material * width * depth * fx.PLATE_THICKNESS_MM


# Material ends of the four-wall sequence: f_px/f_nx terminate at free plate
# corners (2026-10-29 round six measured zero removal there), while f_ny and
# f_py run into the bends of both neighbours on each end (round six observed
# the f_ny chain shortened by R + t per end).
FOUR_WALL_MATERIAL_ENDS = {"f_px": 0, "f_nx": 0, "f_ny": 2, "f_py": 2}


def four_wall_removed_mm3(relief_value: dict | None, label: str) -> float | None:
    """Removal expectation for one four-wall flange, from its actual material ends.

    Returns None for a single-end request on a flange with material ends: which
    native side is the material end is only observable live.
    """
    if relief_value is None or relief_value.get("type", "none") == "none":
        return 0.0
    ends = FOUR_WALL_MATERIAL_ENDS.get(label, 0)
    width = float(relief_value["width"])
    depth = float(relief_value["depth"])
    if relief_value.get("ends", "both") == "both":
        return notch_removed_mm3(width, depth, ends)
    return None if ends else 0.0


def scenario_expected_delta_mm3(relief_value: dict | None, which: str) -> float | None:
    """Expected added-volume delta vs the none baseline for one scenario flange.

    Returns None when the offline evidence cannot pin a single number: a
    side1/side2 request enables exactly one end and which of the two sides is
    the material end is only observable live. The pair check
    (:func:`single_end_pair_verdict`) covers that pair instead.
    """
    spec = MATERIAL_SCENARIO[which]
    if relief_value is None or relief_value.get("type", "none") == "none":
        return 0.0
    width = float(relief_value["width"])
    depth = float(relief_value["depth"])
    if spec["material_ends"] == 0:
        return 0.0  # free ends: removing nothing is the expected outcome, not evidence
    ends = relief_value.get("ends", "both")
    if ends == "both":
        return -notch_removed_mm3(width, depth, 1)
    return None  # single enabled end: removing side resolved live


def relief_geometry_verdict(
    scenario: str,
    relief_value: dict | None,
    echo: dict | None,
    measured_delta_mm3: float | None,
    expected_delta_mm3: float | None,
    notch_face_count: int | None,
    part_thickness_mm: float | None = None,
    tolerance_mm3: float = RELIEF_DELTA_TOLERANCE_MM3,
) -> dict:
    """Judge one relief case: request, created-tree echo and geometry must agree.

    ``scenario`` is ``"material"`` (the flange has a bend end abutting material)
    or ``"free"`` (the negative control). The 2026-10-29 round six shape - a
    rectangular request accepted and echoed, zero volume delta, no notch faces -
    fails here: parameters written but no material removed is not a pass.
    """
    reasons: list[str] = []
    requested = relief_value is not None and relief_value.get("type", "none") == "rectangular"
    if requested:
        if not echo or not (echo.get("side1") and echo.get("side2")):
            reasons.append("no relief_element_echo from the created feature tree")
        else:
            sides = {
                name: echo[name]
                for name in ("side1", "side2")
                if relief_value.get("ends", "both") in ("both", name)
            }
            for name, side in sides.items():
                if side.get("type") != RELIEF_TYPES["rectangular"]:
                    reasons.append(f"{name} did not keep type rectangular in the created feature")
                elif (
                    side.get("depth_type") != RELIEF_DEPTH_TYPES["blind"]
                    or abs(float(side.get("width_mm", 0)) - float(relief_value["width"])) > 1e-6
                    or abs(float(side.get("depth_mm", 0)) - float(relief_value["depth"])) > 1e-6
                ):
                    reasons.append(f"{name} width/depth diverged from the request")
    if part_thickness_mm is None or abs(part_thickness_mm - fx.PLATE_THICKNESS_MM) > 1e-6:
        # T03 rule: a contradicting thickness source invalidates any width/thickness
        # comparison, so a relief case cannot pass on a wrong part thickness.
        reasons.append("measured part thickness missing or not the requested sheet thickness")
    if scenario == "free":
        if measured_delta_mm3 is None or abs(measured_delta_mm3) > tolerance_mm3:
            reasons.append("free-end control must remove nothing")
    elif scenario == "material":
        if expected_delta_mm3 is not None:
            if (
                measured_delta_mm3 is None
                or abs(measured_delta_mm3 - expected_delta_mm3) > tolerance_mm3
            ):
                reasons.append(
                    f"geometry removed {measured_delta_mm3} mm3, expected {expected_delta_mm3}"
                )
            elif requested and expected_delta_mm3 < 0 and not notch_face_count:
                reasons.append("volume moved but no notch faces are observable")
        # else: a single enabled end leaves the delta to the pair verdict, which
        # resolves which native side the material end lives on.
    else:
        reasons.append(f"unknown scenario {scenario!r}")
    return {
        "scenario": scenario,
        "relief": relief_value,
        "passed": not reasons,
        "reasons": reasons,
        "evidence_class": ("none" if not requested or scenario == "free" else "relief_geometry"),
    }


def single_end_pair_verdict(
    side_results: dict, width: float, depth: float, tolerance_mm3=RELIEF_DELTA_TOLERANCE_MM3
) -> dict:
    """side1/side2 must split into exactly one removing and one dormant end.

    ``side_results`` maps "side1"/"side2" to a measured delta (mm3, positive when
    material was added relative to the none baseline). Exactly one side must
    remove w*d*t and that side is the material end; this is how the live run
    resolves which native side the material end lives on.
    """
    removed = notch_removed_mm3(width, depth, 1)
    deltas = {name: side_results.get(name) for name in ("side1", "side2")}
    removing = sorted(
        name for name, delta in deltas.items() if delta is not None and -delta > tolerance_mm3
    )
    dormant = sorted(
        name for name, delta in deltas.items() if delta is None or abs(delta) <= tolerance_mm3
    )
    reasons: list[str] = []
    if len(removing) != 1 or len(dormant) != 1:
        reasons.append(
            f"expected exactly one end to remove {removed} mm3 and one to remove nothing; "
            f"got {deltas}"
        )
    elif abs(-deltas[removing[0]] - removed) > tolerance_mm3:
        reasons.append(f"the removing end took {deltas[removing[0]]} mm3, expected {-removed}")
    return {
        "deltas_mm3": deltas,
        "material_end": removing[0] if len(removing) == 1 else None,
        "removed_mm3": removed,
        "passed": not reasons,
        "reasons": reasons,
    }


# --- DEV-051 T05 proven boundary classification ---------------------------
#
# The 2026-10-30 contrast probes proved the trigger: a flange whose
# attach-edge END is adjacent to an existing bend / bend fillet fails feature
# regeneration -- one adjacent end is enough and the full edge length is
# irrelevant. The 2026-10-29 round six and the 2026-10-30/31 relief run hit it
# on f_ny with exactly the signature below (span 177.92 = 185 - 2x3.54).

T05_REGEN_FAILURE_MESSAGE = "Regeneration produced a failed, suppressed or incomplete feature"
T05_FAILURE_STAGE = "execute_sheetmetal_flange"
T05_FAILURE_TOOLKIT_CODE = -1  # PRO_TK_GENERAL_ERROR (ProToolkitErrors.h)


def classify_flange_failure(shared_corners: object, shortfall_mm: object, failure: object) -> dict:
    """Classify one failed live flange against the proven T05 boundary.

    ``known_t05_boundary`` requires positive evidence on BOTH sides; anything
    missing, non-numeric or contradictory stays a plain ``failed`` so an
    unexplained failure -- a possible regression -- can never hide behind the
    boundary label:

    * geometry: ``shared_corners >= 1`` (an attach-edge end abuts the bend of a
      previously built flange) and the measured shortfall shows bend-end
      consumption without going beyond two ends:
      ``0 < shortfall_mm <= 2 * (R + t) + tol``;
    * failure signature: ``Regeneration produced a failed, suppressed or
      incomplete feature`` at ``execute_sheetmetal_flange`` with
      ``toolkit_code == -1``.
    """
    evidence = {
        "shared_corners": shared_corners,
        "shortfall_mm": shortfall_mm,
        "message": (failure or {}).get("message") if isinstance(failure, dict) else None,
        "toolkit_code": (failure or {}).get("toolkit_code") if isinstance(failure, dict) else None,
        "failed_stage": (failure or {}).get("failed_stage") if isinstance(failure, dict) else None,
    }
    reasons: list[str] = []
    corners_ok = (
        isinstance(shared_corners, int)
        and not isinstance(shared_corners, bool)
        and shared_corners >= 1
    )
    if not corners_ok:
        reasons.append(
            "no attach-edge end abutting an existing bend: shared_corners must be a "
            f"positive int, got {shared_corners!r}"
        )
    max_shortfall = 2.0 * CHAIN_TRIM_MM
    shortfall_ok = (
        isinstance(shortfall_mm, (int, float))
        and not isinstance(shortfall_mm, bool)
        and math.isfinite(shortfall_mm)
        and 0.0 < shortfall_mm <= max_shortfall + fx.SPAN_TOL_MM
    )
    if not shortfall_ok:
        reasons.append(
            "measured shortfall does not show bend-end consumption: expected "
            f"0 < shortfall_mm <= {max_shortfall + fx.SPAN_TOL_MM:.3f}, got {shortfall_mm!r}"
        )
    signature_ok = (
        evidence["message"] is not None
        and T05_REGEN_FAILURE_MESSAGE in evidence["message"]
        and evidence["toolkit_code"] == T05_FAILURE_TOOLKIT_CODE
        and evidence["failed_stage"] == T05_FAILURE_STAGE
    )
    if not signature_ok:
        reasons.append(
            "failure signature is not the proven regeneration failure "
            f"({T05_REGEN_FAILURE_MESSAGE!r} at {T05_FAILURE_STAGE} with "
            f"toolkit_code {T05_FAILURE_TOOLKIT_CODE})"
        )
    return {
        "verdict": "known_t05_boundary" if not reasons else "failed",
        "reasons": reasons,
        "evidence": evidence,
    }


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.find("\nstatic ", start + len(signature))
    return source[start : end if end > 0 else len(source)]


# --- SDK evidence ---------------------------------------------------------


class SdkEvidenceTest(unittest.TestCase):
    def test_relief_types_are_the_documented_order(self):
        self.assertEqual(sorted(RELIEF_TYPES.values()), list(range(6)))
        self.assertEqual(RELIEF_TYPES["none"], 0)
        self.assertEqual(RELIEF_TYPES["rectangular"], 3)

    def test_admitted_types_are_a_subset_of_the_sdk_enum(self):
        for name in SUPPORTED_RELIEF_TYPES:
            self.assertIn(name, RELIEF_TYPES)
        for name in UNSUPPORTED_RELIEF_TYPES:
            self.assertIn(name, RELIEF_TYPES)
            self.assertNotIn(name, SUPPORTED_RELIEF_TYPES)

    def test_depth_rule_picks_blind(self):
        self.assertIn("blind", RELIEF_DEPTH_TYPES)
        self.assertNotIn("rectangular", TAN_TO_BEND_TYPES)
        for name in UNSUPPORTED_RELIEF_TYPES:
            if name in ("stretch", "obround", "param"):
                self.assertIn(name, WIDTH_REQUIRED_TYPES)
        self.assertIn("rectangular", DEPTH_TYPE_REQUIRED_TYPES)

    def test_corner_and_miter_families_exist_but_are_out_of_scope(self):
        self.assertEqual(CORNER_RELIEF_TYPES["rectangular"], 2)
        self.assertEqual(CORNER_RELIEF_TYPES["no"], 5)
        self.assertEqual(len(NOT_IMPLEMENTED_CORNER_RULES), 3)


# --- compatibility default -------------------------------------------------


class DefaultCompatibilityTest(unittest.TestCase):
    def test_omitted_relief_keeps_the_old_payload(self):
        dumped = validated()
        self.assertNotIn("relief", dumped)
        self.assertEqual(dumped["flip"], False)
        self.assertEqual(dumped["height"], fx.FLANGE_HEIGHT_MM)
        self.assertEqual(dumped["radius"], fx.FLANGE_RADIUS_MM)
        self.assertEqual(dumped["y_factor"], fx.FLANGE_Y_FACTOR)

    def test_omitted_and_explicit_none_apply_the_same_tree(self):
        self.assertEqual(expected_native_sides(None), {"side1": "none", "side2": "none"})
        dumped = validated({"type": "none"})
        self.assertEqual(dumped["relief"], {"type": "none", "ends": "both"})
        self.assertEqual(expected_native_sides(dumped["relief"]), expected_native_sides(None))

    def test_none_cannot_carry_geometry_or_ends(self):
        rejected(self, {"type": "none", "width": 1.0}, "takes no width or depth")
        rejected(self, {"type": "none", "depth": 1.0}, "takes no width or depth")
        rejected(self, {"type": "none", "ends": "side1"}, "no ends to select")

    def test_default_end_selection_is_both(self):
        dumped = validated(relief_rectangular(1.0, 1.0))
        self.assertEqual(dumped["relief"]["ends"], "both")


# --- admission ------------------------------------------------------------


class ReliefAdmissionTest(unittest.TestCase):
    def test_rectangular_requires_explicit_width_and_depth(self):
        rejected(self, {"type": "rectangular", "width": 1.0}, "requires width")
        rejected(self, {"type": "rectangular", "depth": 1.0}, "requires width")
        rejected(self, {"type": "rectangular"}, "requires width")

    def test_width_is_positive_and_depth_non_negative(self):
        rejected(self, relief_rectangular(0.0, 1.0), "greater than 0")
        rejected(self, relief_rectangular(-1.0, 1.0), "greater than 0")
        rejected(self, relief_rectangular(1.0, -0.5), "greater than or equal to 0")
        dumped = validated(relief_rectangular(1.0, 0.0))
        self.assertEqual(dumped["relief"]["depth"], 0.0)

    def test_values_are_absolute_model_units(self):
        dumped = validated(relief_rectangular(2.5, 0.75))
        self.assertEqual(dumped["relief"]["width"], 2.5)
        self.assertEqual(dumped["relief"]["depth"], 0.75)
        # No thickness multiple is accepted as a substitute for a number.
        rejected(self, {"type": "rectangular", "width": "1t", "depth": 1.0}, "valid number")

    def test_non_finite_and_boolean_values_are_rejected(self):
        rejected(self, {"type": "rectangular", "width": True, "depth": 1.0}, "not booleans")
        rejected(self, {"type": "rectangular", "width": 1.0, "depth": False}, "not booleans")
        rejected(self, {"type": "rectangular", "width": float("inf"), "depth": 1.0}, "finite")

    def test_unknown_keys_are_rejected(self):
        rejected(
            self,
            {"type": "rectangular", "width": 1.0, "depth": 1.0, "corner": "miter"},
            "Extra inputs are not permitted",
        )

    def test_relief_type_is_a_closed_set(self):
        rejected(self, {"type": "tear"}, "Input should be")
        rejected(self, {"type": "auto"}, "Input should be")
        rejected(self, {"type": None}, "Input should be")


class UnsupportedShapeTest(unittest.TestCase):
    def test_other_sdk_shapes_are_named_unsupported_not_mapped_to_none(self):
        for name in UNSUPPORTED_RELIEF_TYPES:
            with self.subTest(shape=name):
                rejected(self, {"type": name}, "Input should be")

    def test_corner_rules_are_not_part_of_the_operation(self):
        for name in NOT_IMPLEMENTED_CORNER_RULES:
            with self.subTest(rule=name):
                rejected(
                    self,
                    {"type": "rectangular", "width": 1.0, "depth": 1.0, "rule": name},
                    "Extra inputs are not permitted",
                )


class EndSelectionTest(unittest.TestCase):
    def test_each_end_selection_maps_to_one_or_two_sides(self):
        cases = {
            "both": {"side1": "rectangular", "side2": "rectangular"},
            "side1": {"side1": "rectangular", "side2": "none"},
            "side2": {"side1": "none", "side2": "rectangular"},
        }
        for ends, expected in cases.items():
            with self.subTest(ends=ends):
                dumped = validated(relief_rectangular(1.0, 1.0, ends))
                self.assertEqual(expected_native_sides(dumped["relief"]), expected)

    def test_unknown_end_selection_is_rejected(self):
        rejected(self, relief_rectangular(1.0, 1.0, "left"), "Input should be")
        rejected(self, relief_rectangular(1.0, 1.0, "both_ends"), "Input should be")


class MaterialSideTest(unittest.TestCase):
    def test_relief_does_not_touch_the_trajectory_normal_control(self):
        for relief in (None, {"type": "none"}, relief_rectangular(1.0, 1.0)):
            with self.subTest(relief=relief):
                self.assertEqual(validated(relief)["flip"], False)
                self.assertEqual(validated(relief, flip=True)["flip"], True)

    def test_relief_has_no_material_side_or_auto_field(self):
        dumped = validated(relief_rectangular(1.0, 1.0))
        self.assertEqual(set(dumped["relief"]), {"type", "ends", "width", "depth"})
        self.assertNotIn("side", dumped["relief"])
        self.assertNotIn("material_side", dumped["relief"])


# --- native element tree --------------------------------------------------


class NativeTreeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = NATIVE.read_text(encoding="utf-8", errors="replace")
        cls.flange = _function_body(cls.source, "static void generic_sheetmetal_flange")
        cls.request = _function_body(cls.source, "static FlangeReliefRequest flange_relief_request")
        cls.side = _function_body(cls.source, "static void flange_relief_side")
        cls.record = _function_body(cls.source, "static J flange_relief_record")

    def test_relief_compound_covers_both_bend_ends(self):
        for token in (
            "PRO_E_SMT_BEND_RELIEF",
            "PRO_E_SMT_BEND_RELIEF_SIDE1",
            "PRO_E_SMT_BEND_RELIEF_SIDE2",
        ):
            self.assertIn(token, self.flange)

    def test_default_tree_is_still_none_on_both_ends(self):
        self.assertIn("PRO_BEND_RLF_NONE", self.side)
        self.assertIn("enabled ? PRO_BEND_RLF_RECTANGULAR : PRO_BEND_RLF_NONE", self.side)

    def test_rectangular_sets_width_depth_type_and_blind_depth(self):
        for token in (
            "PRO_BEND_RLF_RECTANGULAR",
            "PRO_E_BEND_RELIEF_WIDTH",
            "PRO_E_BEND_RELIEF_DEPTH_TYPE",
            "PRO_BEND_RLF_DEPTH_BLIND",
            "PRO_E_BEND_RELIEF_DEPTH",
        ):
            self.assertIn(token, self.side)

    def test_unimplemented_shapes_are_absent_from_the_native_tree(self):
        for token in (
            "PRO_BEND_RLF_RIP",
            "PRO_BEND_RLF_STRETCH",
            "PRO_BEND_RLF_OBROUND",
            "PRO_BEND_RLF_PARAM",
            "PRO_BEND_RLF_DEPTH_TAN_TO_BEND",
            "PRO_E_SMT_CORNER_RELIEF",
            "PRO_E_SMT_EDGE_RIP",
        ):
            self.assertNotIn(token, self.flange + self.side + self.record)

    def test_relief_length_and_angle_stay_unset(self):
        # Neither the flange feature mapping nor the SDK require a length for a
        # rectangular notch; leaving them unset is deliberate and is one of the
        # items a live creation has to confirm.
        for token in ("PRO_E_BEND_RELIEF_LENGTH", "PRO_E_BEND_RELIEF_ANGLE"):
            self.assertNotIn(token, self.side)

    def test_request_is_validated_before_any_element_is_built(self):
        self.assertLess(
            self.flange.index("flange_relief_request(op)"),
            self.flange.index("node(nullptr, PRO_E_FEATURE_TREE)"),
        )

    def test_parent_body_stays_implicit(self):
        self.assertNotIn("PRO_E_BODY", self.flange + self.side + self.record)

    def test_attachment_edge_must_border_a_wall_face(self):
        # DEV-051 T05/T11: an edge between side/rim surfaces answers
        # PRO_TK_BAD_CONTEXT (-8) and Creo then fails the create with a bare -1 and an
        # empty element error list, so the edge is checked before the tree exists.
        self.assertIn("ProSmtedgeContourGet", self.flange)
        self.assertIn("PRO_TK_BAD_CONTEXT", self.flange)
        self.assertLess(
            self.flange.index("ProSmtedgeContourGet"),
            self.flange.index("node(nullptr, PRO_E_FEATURE_TREE)"),
        )

    def test_unknown_type_and_ends_throw_instead_of_falling_back(self):
        self.assertIn("Unsupported sheetmetal flange relief type", self.request)
        self.assertIn("relief ends must be both, side1 or side2", self.request)
        self.assertIn("requires width and depth", self.request)

    def test_record_reports_measured_thickness_and_request_arithmetic(self):
        for token in (
            "part_thickness_read(&thickness)",
            '"part_thickness_mm"',
            '"corner_overlap_run_mm"',
            '"width_at_least_thickness"',
            '"depth_covers_corner_run"',
        ):
            self.assertIn(token, self.record)
        self.assertIn('op.contains("relief")', self.flange)

    def test_record_is_only_written_when_relief_was_requested(self):
        self.assertIn('extra["relief"] = flange_relief_record(op, relief_request)', self.flange)
        self.assertIn('if (op.contains("relief") && !op.at("relief").is_null())', self.flange)


# --- geometry -------------------------------------------------------------


class ReliefGeometryTest(unittest.TestCase):
    def test_a_rectangular_notch_removes_width_by_depth_by_thickness(self):
        self.assertAlmostEqual(relief_removed_mm3(relief_rectangular(2.0, 3.0)), 12.0, places=6)
        self.assertAlmostEqual(
            relief_removed_mm3(relief_rectangular(2.0, 3.0, "side1")), 6.0, places=6
        )
        self.assertEqual(relief_removed_mm3(None), 0.0)

    def test_thickness_scale_relief_does_not_cover_the_corner_run(self):
        run = corner_overlap_run_mm()
        self.assertAlmostEqual(run, 77.46, places=6)
        relief = relief_rectangular(fx.PLATE_THICKNESS_MM, fx.PLATE_THICKNESS_MM)
        self.assertLess(relief["depth"], run)

    def test_corner_run_profile_reaches_the_shared_corner(self):
        run = corner_overlap_run_mm()
        relief = relief_rectangular(fx.PLATE_THICKNESS_MM, run)
        self.assertGreaterEqual(relief["depth"], run)
        self.assertAlmostEqual(relief_removed_mm3(relief), 2 * 1.0 * run * 1.0, places=6)

    def test_four_wall_volume_expectation_with_relief(self):
        # Offline prediction over the full fixture spans; live chains of f_ny/f_py
        # are shorter (R + t per material end), so the live spans are authoritative.
        spans = [232.0, 232.0, 185.0, 185.0]
        labels = ["f_px", "f_nx", "f_ny", "f_py"]
        relief_value = relief_rectangular(1.0, 1.0)
        walls = sum(bent_wall_increment_mm3(span) for span in spans)
        removed = sum(four_wall_removed_mm3(relief_value, label) for label in labels)
        self.assertAlmostEqual(bent_wall_increment_mm3(185.0), 14_373.615854, places=4)
        self.assertAlmostEqual(removed, 4.0, places=6)
        self.assertAlmostEqual(fx.PLATE_VOLUME_MM3 + walls - removed, 107_713.814175, places=4)

    def test_free_ends_remove_nothing_and_material_ends_drive_removal(self):
        self.assertEqual(four_wall_removed_mm3(relief_rectangular(4.0, 4.0), "f_px"), 0.0)
        self.assertEqual(four_wall_removed_mm3(relief_rectangular(4.0, 4.0), "f_nx"), 0.0)
        self.assertAlmostEqual(
            four_wall_removed_mm3(relief_rectangular(1.0, 1.0), "f_ny"), 2.0, places=6
        )
        self.assertAlmostEqual(
            four_wall_removed_mm3(relief_rectangular(4.0, 4.0), "f_py"), 32.0, places=6
        )
        self.assertIsNone(four_wall_removed_mm3(relief_rectangular(1.0, 1.0, "side1"), "f_ny"))
        self.assertEqual(four_wall_removed_mm3(relief_rectangular(1.0, 1.0, "side1"), "f_px"), 0.0)
        self.assertEqual(four_wall_removed_mm3(None, "f_ny"), 0.0)

    def test_corner_overlap_bound_is_unchanged_by_the_contract(self):
        self.assertAlmostEqual(fx.corner_overlap_volume_mm3(1), 77.46, places=6)
        self.assertAlmostEqual(fx.corner_overlap_volume_mm3(2), 154.92, places=6)


class FourWallReliefPlanTest(unittest.TestCase):
    def test_reported_four_wall_plan_still_validates_with_relief(self):
        inspection = fx.box_inspection()
        operations = [fx.wall_sketch(), fx.wall_base_op()]
        for side, label in fx.FLANGE_SEQUENCE:
            reference = fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, side, face="top")
            operation = fx.flange_op(side, label, reference)
            operation["relief"] = relief_rectangular(1.0, 1.0)
            operations.append(operation)
        dumped = validate_operations(operations)
        self.assertEqual(len(dumped), 6)
        flanges = [item for item in dumped if item["op"] == "sheetmetal_flange"]
        self.assertEqual(len(flanges), 4)
        for item in flanges:
            self.assertEqual(
                expected_native_sides(item["relief"]),
                {"side1": "rectangular", "side2": "rectangular"},
            )

    def test_legacy_plan_without_relief_is_unchanged(self):
        operations, _ = fx.four_wall_plan(fx.box_inspection())
        dumped = validate_operations(operations)
        self.assertTrue(all("relief" not in item for item in dumped))


# --- 2026-10-30 material-scenario oracle -----------------------------------


def material_first_flange_reference() -> dict:
    inspection = fx.box_inspection()
    return fx.select_wall_edge(
        inspection, fx.PLATE_BOUNDS, MATERIAL_SCENARIO["first"]["side"], face="top"
    )


def material_wall_plan() -> list[dict]:
    """The live base plan for one material-scenario model: the first wall only.

    Live flanges are always submitted as their own jobs with edges re-selected
    from a fresh snapshot. The 2026-10-30/31 live run submitted
    :func:`material_scenario_plan` as one wall+flange plan; its baked flange
    edge id came from the offline fixture box and Creo refused the attachment
    (PRO_TK_NOT_EXIST, -23) -- a driver fixture defect, never a modelling
    failure.
    """
    return [fx.wall_sketch(), fx.wall_base_op()]


def material_scenario_plan() -> tuple:
    """Offline request shape for one material-scenario model: wall plus f_px.

    f_ny (-y) is submitted as its own job after f_px exists so its edge is
    re-selected from a fresh snapshot; see :func:`material_second_flange_op`.

    The baked f_px reference comes from the synthetic box_inspection fixture,
    so its edge id only exists offline. Never submit this plan live: use
    :func:`material_wall_plan` for the base wall and let the live driver
    re-select every flange edge from a fresh snapshot.
    """
    reference = material_first_flange_reference()
    operations = [
        fx.wall_sketch(),
        fx.wall_base_op(),
        fx.flange_op(
            MATERIAL_SCENARIO["first"]["side"], MATERIAL_SCENARIO["first"]["label"], reference
        ),
    ]
    return operations, reference


def material_second_flange_op(relief_value: dict | None) -> dict:
    """The f_ny (-y) request; the live edge is re-selected after f_px exists."""
    inspection = fx.box_inspection()
    reference = fx.select_wall_edge(
        inspection, fx.PLATE_BOUNDS, MATERIAL_SCENARIO["second"]["side"], face="top"
    )
    operation = fx.flange_op(
        MATERIAL_SCENARIO["second"]["side"], MATERIAL_SCENARIO["second"]["label"], reference
    )
    if relief_value is not None:
        operation["relief"] = dict(relief_value)
    return operation


class BentWallVolumeTest(unittest.TestCase):
    def test_increment_model_reproduces_the_round_six_measurement(self):
        # 2026-10-29 22:27 run: f_px over the 232 mm span added 18 025.291234 mm3.
        self.assertAlmostEqual(
            bent_wall_increment_mm3(ROUND_SIX_MEASURED_SPAN_MM),
            ROUND_SIX_MEASURED_INCREMENT_MM3,
            delta=1e-3,
        )

    def test_each_material_end_shortens_the_sweep_by_the_observed_trim(self):
        full = bent_wall_increment_mm3(fx.PLATE_WIDTH_MM)
        trimmed = bent_wall_increment_mm3(fx.PLATE_WIDTH_MM, trimmed_ends=1)
        area = full / fx.PLATE_WIDTH_MM
        self.assertAlmostEqual(full - trimmed, CHAIN_TRIM_MM * area, places=6)
        self.assertAlmostEqual(trimmed, (fx.PLATE_WIDTH_MM - CHAIN_TRIM_MM) * area, places=6)

    def test_increment_is_smaller_than_the_flat_span_proxy(self):
        # The old span x height x t oracle over-counts by the bend geometry; the
        # material scenario must use the model that matches the measured walls.
        self.assertLess(
            bent_wall_increment_mm3(ROUND_SIX_MEASURED_SPAN_MM),
            fx.wall_volume_mm3(ROUND_SIX_MEASURED_SPAN_MM),
        )


class MaterialScenarioTest(unittest.TestCase):
    def test_first_flange_has_only_free_ends_and_second_has_one_material_end(self):
        self.assertEqual(MATERIAL_SCENARIO["first"]["material_ends"], 0)
        self.assertEqual(MATERIAL_SCENARIO["second"]["material_ends"], 1)

    def test_scenario_plan_and_second_flange_validate_for_every_variant(self):
        operations, _ = material_scenario_plan()
        dumped = validate_operations(operations + [material_second_flange_op(None)])
        self.assertEqual([item["op"] for item in dumped][2:], ["sheetmetal_flange"] * 2)
        for variant in (
            relief_rectangular(1.0, 1.0),
            relief_rectangular(4.0, 4.0),
            relief_rectangular(1.0, 1.0, "side1"),
            relief_rectangular(1.0, 1.0, "side2"),
        ):
            with self.subTest(variant=variant):
                validate_operations([material_second_flange_op(variant)])

    def test_free_first_flange_never_removes_material(self):
        self.assertEqual(scenario_expected_delta_mm3(None, "first"), 0.0)
        self.assertEqual(scenario_expected_delta_mm3(relief_rectangular(4.0, 4.0), "first"), 0.0)

    def test_second_flange_expectations_follow_the_intersecting_material(self):
        self.assertEqual(scenario_expected_delta_mm3(None, "second"), 0.0)
        self.assertEqual(scenario_expected_delta_mm3(relief_rectangular(1.0, 1.0), "second"), -1.0)
        self.assertEqual(scenario_expected_delta_mm3(relief_rectangular(4.0, 4.0), "second"), -16.0)
        self.assertIsNone(
            scenario_expected_delta_mm3(relief_rectangular(1.0, 1.0, "side1"), "second")
        )
        self.assertIsNone(
            scenario_expected_delta_mm3(relief_rectangular(1.0, 1.0, "side2"), "second")
        )

    def test_notch_removal_is_width_by_depth_by_thickness_per_material_end(self):
        self.assertAlmostEqual(notch_removed_mm3(1.0, 1.0, 1), 1.0, places=6)
        self.assertAlmostEqual(notch_removed_mm3(4.0, 4.0, 1), 16.0, places=6)
        self.assertAlmostEqual(notch_removed_mm3(4.0, 4.0, 0), 0.0, places=6)


def _echo(width=1.0, depth=1.0, ends="both", side_type=3, dormant_type=0) -> dict:
    def enabled_side():
        return {
            "type": side_type,
            "width_mm": width,
            "depth_type": RELIEF_DEPTH_TYPES["blind"],
            "depth_mm": depth,
            "length_type": 0,
            "length_mm": 0.0,
            "angle": 0.0,
        }

    dormant = {"type": dormant_type, "width_mm": 0.0, "depth_type": 0, "depth_mm": 0.0}
    if ends == "both":
        side1, side2 = enabled_side(), enabled_side()
    elif ends == "side1":
        side1, side2 = enabled_side(), dormant
    else:
        side1, side2 = dormant, enabled_side()
    return {"side1": side1, "side2": side2}


class ReliefGeometryVerdictTest(unittest.TestCase):
    def test_request_echo_alone_is_never_a_pass(self):
        verdict = relief_geometry_verdict(
            "material",
            relief_rectangular(1.0, 1.0),
            _echo(),
            0.0,
            -1.0,
            0,
            part_thickness_mm=1.0,
        )
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("geometry removed 0.0" in reason for reason in verdict["reasons"]))

    def test_volume_without_notch_faces_is_not_a_pass(self):
        verdict = relief_geometry_verdict(
            "material",
            relief_rectangular(1.0, 1.0),
            _echo(),
            -1.0,
            -1.0,
            0,
            part_thickness_mm=1.0,
        )
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("no notch faces" in reason for reason in verdict["reasons"]))

    def test_missing_created_feature_echo_fails(self):
        for echo in (None, {}, {"side1": _echo()["side1"]}):
            with self.subTest(echo=echo):
                verdict = relief_geometry_verdict(
                    "material",
                    relief_rectangular(1.0, 1.0),
                    echo,
                    -1.0,
                    -1.0,
                    2,
                    part_thickness_mm=1.0,
                )
                self.assertFalse(verdict["passed"])
                self.assertTrue(any("relief_element_echo" in r for r in verdict["reasons"]))

    def test_diverged_echo_fails_even_with_a_matching_delta(self):
        verdict = relief_geometry_verdict(
            "material",
            relief_rectangular(1.0, 1.0),
            _echo(width=3.71),
            -1.0,
            -1.0,
            2,
            part_thickness_mm=1.0,
        )
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("diverged" in reason for reason in verdict["reasons"]))

    def test_reset_to_param_type_fails(self):
        verdict = relief_geometry_verdict(
            "material",
            relief_rectangular(1.0, 1.0),
            _echo(side_type=RELIEF_TYPES["param"]),
            -1.0,
            -1.0,
            2,
            part_thickness_mm=1.0,
        )
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("rectangular" in reason for reason in verdict["reasons"]))

    def test_contradicting_part_thickness_fails(self):
        verdict = relief_geometry_verdict(
            "material",
            relief_rectangular(1.0, 1.0),
            _echo(),
            -1.0,
            -1.0,
            2,
            part_thickness_mm=3.71,
        )
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("part thickness" in reason for reason in verdict["reasons"]))

    def test_consistent_material_removal_passes(self):
        verdict = relief_geometry_verdict(
            "material",
            relief_rectangular(1.0, 1.0),
            _echo(),
            -1.0,
            -1.0,
            2,
            part_thickness_mm=1.0,
        )
        self.assertTrue(verdict["passed"], verdict["reasons"])
        self.assertEqual(verdict["evidence_class"], "relief_geometry")

    def test_free_end_control_requires_zero_and_stays_no_evidence(self):
        passed = relief_geometry_verdict(
            "free",
            relief_rectangular(4.0, 4.0),
            _echo(4.0, 4.0),
            0.0,
            None,
            0,
            part_thickness_mm=1.0,
        )
        self.assertTrue(passed["passed"], passed["reasons"])
        self.assertEqual(passed["evidence_class"], "none")
        removed = relief_geometry_verdict(
            "free",
            relief_rectangular(4.0, 4.0),
            _echo(4.0, 4.0),
            -16.0,
            None,
            4,
            part_thickness_mm=1.0,
        )
        self.assertFalse(removed["passed"])
        self.assertTrue(any("remove nothing" in reason for reason in removed["reasons"]))

    def test_round_six_shape_is_reproduced_and_rejected(self):
        # 2026-10-29: rectangular both 1x1 accepted and echoed, delta 0.000000,
        # no notch faces, thickness read 3.71 - the exact contradiction this
        # verdict exists to reject.
        verdict = relief_geometry_verdict(
            "material",
            relief_rectangular(1.0, 1.0),
            _echo(),
            0.0,
            -1.0,
            0,
            part_thickness_mm=3.71,
        )
        self.assertFalse(verdict["passed"])
        self.assertGreaterEqual(len(verdict["reasons"]), 2)


class SingleEndPairVerdictTest(unittest.TestCase):
    def test_exactly_one_side_removing_is_the_material_end(self):
        verdict = single_end_pair_verdict({"side1": -1.0, "side2": 0.0}, 1.0, 1.0)
        self.assertTrue(verdict["passed"], verdict["reasons"])
        self.assertEqual(verdict["material_end"], "side1")
        self.assertAlmostEqual(verdict["removed_mm3"], 1.0, places=6)
        mirrored = single_end_pair_verdict({"side1": 0.0, "side2": -1.0}, 1.0, 1.0)
        self.assertTrue(mirrored["passed"], mirrored["reasons"])
        self.assertEqual(mirrored["material_end"], "side2")

    def test_both_or_neither_sides_removing_fails(self):
        for deltas in (
            {"side1": -1.0, "side2": -1.0},
            {"side1": 0.0, "side2": 0.0},
            {"side1": None, "side2": 0.0},
        ):
            with self.subTest(deltas=deltas):
                verdict = single_end_pair_verdict(deltas, 1.0, 1.0)
                self.assertFalse(verdict["passed"])

    def test_a_side_removing_the_wrong_amount_fails(self):
        verdict = single_end_pair_verdict({"side1": -16.0, "side2": 0.0}, 1.0, 1.0)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("expected" in reason for reason in verdict["reasons"]))


class NativeReliefEchoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = NATIVE.read_text(encoding="utf-8", errors="replace")
        cls.flange = _function_body(cls.source, "static void generic_sheetmetal_flange")
        cls.expect = _function_body(cls.source, "static void flange_relief_expect")
        cls.side_echo = _function_body(cls.source, "static J flange_relief_side_echo")

    def test_created_tree_is_extracted_after_the_successful_regen(self):
        self.assertIn("ProFeatureElemtreeExtract", self.flange)
        self.assertIn("ProFeatureElemtreeFree", self.flange)
        self.assertLess(
            self.flange.index("ProSolidRegenerate"),
            self.flange.index("ProFeatureElemtreeExtract"),
        )

    def test_echo_is_only_read_when_relief_was_requested(self):
        self.assertIn("if (relief_request.side1 || relief_request.side2)", self.flange)

    def test_divergence_fails_with_a_named_message(self):
        self.assertIn("did not persist into the created feature", self.expect)
        self.assertIn("PRO_BEND_RLF_RECTANGULAR", self.expect)
        self.assertIn("PRO_BEND_RLF_NONE", self.expect)

    def test_echo_and_log_are_staged_into_the_result(self):
        self.assertIn('extra["relief_element_echo"]', self.flange)
        self.assertIn("SHEETMETAL_FLANGE_RELIEF_ELEMS", self.flange)
        self.assertIn("PRO_E_BEND_RELIEF_LENGTH_TYPE", self.side_echo)

    def test_write_path_still_only_writes_type_width_depth(self):
        # The read-back may look at length/angle; the write path must not set them.
        side = _function_body(self.source, "static void flange_relief_side")
        for token in ("PRO_E_BEND_RELIEF_LENGTH", "PRO_E_BEND_RELIEF_ANGLE"):
            self.assertNotIn(token, side)


# --- edit path ------------------------------------------------------------


class EditPathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = NATIVE.read_text(encoding="utf-8", errors="replace")
        cls.flange = _function_body(cls.native, "static void generic_sheetmetal_flange")
        cls.server = SERVER.read_text(encoding="utf-8", errors="replace")

    def test_height_dimension_and_section_path_survive(self):
        self.assertIn('{"name", "height"}', self.flange)
        self.assertIn('extra["section_path"]', self.flange)

    def test_relief_is_creation_time_only(self):
        self.assertNotIn("ProFeatureRedefine", self.flange)
        self.assertNotIn("ProElemtreeElementModify", self.flange)
        self.assertIn("fixed when the flange", self.server)
        self.assertIn("deleting/re-creating the flange", self.server)

    def test_tool_exposes_relief_as_an_optional_parameter(self):
        self.assertIn("relief: Annotated[", self.server)
        self.assertIn('operation["relief"] = relief', self.server)
        self.assertIn("relief is not None", self.server)

    def test_tool_description_states_the_supported_subset(self):
        for token in ("'none'|'rectangular'", "Rip/stretch/obround/param", "miter cuts"):
            self.assertIn(token, self.server)


class FlangeFailureClassificationTest(unittest.TestCase):
    """known_t05_boundary needs positive evidence on both sides (DEV-051 T05)."""

    @staticmethod
    def failure(**overrides) -> dict:
        record = {
            "job_status": "failed",
            "message": T05_REGEN_FAILURE_MESSAGE,
            "toolkit_code": T05_FAILURE_TOOLKIT_CODE,
            "failed_stage": T05_FAILURE_STAGE,
            "rollback_succeeded": True,
        }
        record.update(overrides)
        return record

    def test_round_six_shape_is_the_known_boundary(self):
        # 2026-10-29/31 f_ny: both ends consumed (2 x 3.54 mm), regen failure -1.
        verdict = classify_flange_failure(2, 7.08, self.failure())
        self.assertEqual(verdict["verdict"], "known_t05_boundary")
        self.assertEqual(verdict["reasons"], [])

    def test_single_adjacent_end_is_the_known_boundary(self):
        # The 2026-10-30 contrast: one consumed end (3.54 mm) already fails.
        verdict = classify_flange_failure(1, 3.54, self.failure())
        self.assertEqual(verdict["verdict"], "known_t05_boundary")

    def test_free_edge_regeneration_failure_stays_a_plain_failure(self):
        # Without adjacency evidence a regeneration failure is unexplained and
        # must never be absorbed into the boundary label (N01 regression guard).
        verdict = classify_flange_failure(0, 0.0, self.failure())
        self.assertEqual(verdict["verdict"], "failed")
        self.assertTrue(any("shared_corners" in reason for reason in verdict["reasons"]))

    def test_missing_or_contradictory_geometry_never_classifies(self):
        for corners, shortfall in (
            (None, 7.08),
            (2, None),
            (2, 0.0),
            (2, float("nan")),
            (2, 20.0),
            ("2", 7.08),
            (True, 7.08),
        ):
            with self.subTest(corners=corners, shortfall=shortfall):
                verdict = classify_flange_failure(corners, shortfall, self.failure())
                self.assertEqual(verdict["verdict"], "failed")

    def test_other_failure_signatures_never_classify(self):
        for overrides in (
            {"message": "Toolkit call ProModelitemInit(board, id, t, &mi) failed with code -23"},
            {"toolkit_code": -23},
            {"toolkit_code": None},
            {"failed_stage": "admission"},
            {"failed_stage": None},
            {"message": None},
        ):
            with self.subTest(**overrides):
                verdict = classify_flange_failure(2, 7.08, self.failure(**overrides))
                self.assertEqual(verdict["verdict"], "failed")
                self.assertTrue(
                    any("signature" in reason for reason in verdict["reasons"]), verdict
                )

    def test_missing_failure_record_never_classifies(self):
        for failure in (None, {}, "failed"):
            with self.subTest(failure=failure):
                self.assertEqual(classify_flange_failure(2, 7.08, failure)["verdict"], "failed")


class MaterialLivePlanTest(unittest.TestCase):
    """Live submissions never carry the offline fixture's synthetic edge ids."""

    def test_wall_plan_is_the_wall_only(self):
        operations = material_wall_plan()
        self.assertEqual([item["op"] for item in operations], ["sketch", "sheetmetal_wall"])
        validate_operations(operations)

    def test_fixture_plan_edge_ids_come_from_the_synthetic_box(self):
        _, reference = material_scenario_plan()
        self.assertIn(reference["edge"]["id"], fx.EDGE_IDS)

    def test_live_material_case_never_submits_the_baked_fixture_plan(self):
        source = (
            Path(__file__).resolve().parents[2] / "tools" / "test_sheetmetal_relief.py"
        ).read_text(encoding="utf-8")
        start = source.index("async def run_material_case")
        end = source.find("\ndef ", start)
        body = source[start : end if end > 0 else len(source)]
        self.assertNotIn("material_scenario_plan", body)
        self.assertIn("material_wall_plan", body)
        self.assertIn("select_wall_edge", body)


if __name__ == "__main__":
    unittest.main()
