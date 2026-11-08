"""FEAT-039/W01: the endpoint weld contract, policy layer.

Python decides which endpoint pairs may be welded and reports the evidence; it
never moves geometry and never pretends the kernel welded anything. The native
solver does the real coincidence work, so until that exists the ``weld``
policy is refused and the receipt says so.

The endpoint view is the one the profile diagnostics already use: the curves
come from :mod:`creo_mechdog.profile_diagnostics`, so this module adds no
parallel gap diagnostics. Two scales stay apart:

* ``CLUSTER_TOLERANCE_MM`` (1e-4 mm) is the closure-diagnostic scale: two
  endpoints that close at that distance are candidates for one weld;
* ``EXACT_TOLERANCE_MM`` (1e-9 mm) is the published native sketch epsilon, the
  only existing constant between the two observations of BUG-101 (an 8.215e-7
  mm gap was welded by the kernel, a 7.83e-13 mm gap was welded too). Neither
  number is the calibrated weld threshold for a pair; that stays open and the
  receipt says which source it used.

Rules, in the order they are applied:

1. a candidate pair is two endpoints of *different* curves within the cluster
   tolerance;
2. an endpoint belongs to at most one accepted pair (smallest gap wins, a tie
   is ambiguous and is refused instead of being resolved arbitrarily);
3. a pair may not bridge two chains: welding the ends of one open chain closes
   it, welding two different chains would merge two contours;
4. two arcs may only be welded when they live on the same circle (centre and radius
   agree) and both carry a real sweep; at the cluster tolerance this is already
   implied by the endpoints meeting, so it stays a guard against a geometry that
   would change the arc;
5. the symmetric move each endpoint would need is gap/2, and a request may
   cap it with ``max_move_mm``.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from creo_mechdog.profile_diagnostics import EXACT_TOLERANCE_MM, _expand

POLICIES = ("report", "reject", "weld")
SAMPLE_LIMIT = 20
# The closure-diagnostic scale (1e-4 mm) already published for contour
# closure; it decides which endpoints may be considered one point, not whether
# the kernel welds them.
CLUSTER_TOLERANCE_MM = 1e-4
# The weld plan handed to the native side is bounded like every other receipt field.
WELD_PLAN_LIMIT = 200
# The 2026-10-31 feedback: the kernel welded an 8.215e-7 mm gap on Creo 12.4,
# so the 1e-9 mm bound is a risk flag, never a guarantee.
OBSERVED_KERNEL_WELD_MM = 8.21534267e-7


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.dist(a, b)


def _endpoints(curves: list) -> list[dict]:
    """Every weldable endpoint of the expanded profile, in a stable order."""
    ends: list[dict] = []
    for index, curve in enumerate(curves):
        if curve.kind not in ("line", "arc"):
            continue
        if curve.start is None or curve.end is None:
            continue
        ends.append({"curve": index, "end": "start", "point": curve.start})
        ends.append({"curve": index, "end": "end", "point": curve.end})
    return ends


def _chains(curves: list, ends: list[dict], tolerance: float) -> dict[int, int]:
    """Group curves into chains by exactly coincident endpoints.

    The mapping is curve index -> chain id. Two curves are chained when one of
    their endpoints coincides within the strict tolerance, so a chain is an
    open chain of curves and a closed contour is a chain whose two ends meet.
    """
    parent = list(range(len(curves)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for i, first in enumerate(ends):
        for second in ends[i + 1 :]:
            if first["curve"] == second["curve"]:
                continue
            if _distance(first["point"], second["point"]) <= tolerance:
                union(first["curve"], second["curve"])
    return {index: find(index) for index in range(len(curves))}


def _arc_consistent(first, second, tolerance: float) -> bool:
    if first.kind != "arc" or second.kind != "arc":
        return True
    if first.center is None or second.center is None:
        return False
    if _distance(first.center, second.center) > tolerance:
        return False
    if abs(first.radius - second.radius) > tolerance:
        return False
    # The sweeps stay as they are: the policy layer never rewrites an arc, it
    # only checks that both arcs live on the same circle, so welding their ends
    # keeps one consistent arc geometry.
    return abs(first.sweep) > 0.0 and abs(second.sweep) > 0.0


def _plan(
    entities: list[dict[str, Any]], max_move_mm: float | None
) -> tuple[list, list[dict], list[dict], list[dict]]:
    """The shared candidate/accepted/refused decision used by every entry."""
    curves, _names = _expand(entities)
    ends = _endpoints(curves)
    chain_of = _chains(curves, ends, EXACT_TOLERANCE_MM)

    candidates: list[dict] = []
    for i, first in enumerate(ends):
        for second in ends[i + 1 :]:
            if first["curve"] == second["curve"]:
                continue
            gap = _distance(first["point"], second["point"])
            # A candidate is a pair inside the closure diagnostic scale. The
            # 2026-11-05 live measurement showed the sketch epsilon is not the
            # coincidence tolerance, so a bound alone cannot widen this.
            if gap <= 0.0 or gap > CLUSTER_TOLERANCE_MM:
                # An exact join is already one point, not a candidate weld.
                continue
            candidates.append(
                {
                    "curve_a": first["curve"],
                    "curve_b": second["curve"],
                    "end_a": first["end"],
                    "end_b": second["end"],
                    "gap_mm": gap,
                    "required_move_mm": gap / 2.0,
                    "entity_a": curves[first["curve"]].name,
                    "entity_b": curves[second["curve"]].name,
                    "same_chain": chain_of[first["curve"]] == chain_of[second["curve"]],
                    "arc_consistent": _arc_consistent(
                        curves[first["curve"]], curves[second["curve"]], CLUSTER_TOLERANCE_MM
                    ),
                }
            )
    candidates.sort(key=lambda entry: (entry["gap_mm"], entry["curve_a"], entry["curve_b"]))

    accepted: list[dict] = []
    refused: list[dict] = []
    used: dict[tuple[int, str], str] = {}
    for candidate in candidates:
        key_a = (candidate["curve_a"], candidate["end_a"])
        key_b = (candidate["curve_b"], candidate["end_b"])
        reason = None
        if not candidate["same_chain"]:
            reason = "separate_loops"
        elif not candidate["arc_consistent"]:
            reason = "arc_inconsistent"
        elif max_move_mm is not None and candidate["required_move_mm"] > max_move_mm:
            reason = "max_move_exceeded"
        elif key_a in used or key_b in used:
            reason = "ambiguous_pair"
        if reason is not None:
            refused.append({**candidate, "reason": reason})
            continue
        used[key_a] = key_b
        used[key_b] = key_a
        accepted.append(candidate)
    return curves, candidates, accepted, refused


def _entity_named(entities: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for entity in entities:
        if entity.get("type") in ("line", "arc") and str(entity.get("name")) == name:
            return entity
    return None


def _snap_entities(
    entities: list[dict[str, Any]],
    curves: list,
    accepted: list[dict],
) -> tuple[list[dict[str, Any]], list[dict], str | None]:
    """Rewrite accepted line endpoints to one shared point.

    Arcs never move: an arc endpoint is tied to its centre and radius, so the
    line side of an arc/line pair is anchored to the arc endpoint. Two lines
    meet at the midpoint. A pair involving an expanded rectangle/polyline
    segment, or two arcs, is refused because the rewrite would change geometry
    the request did not describe.
    """
    result = copy.deepcopy(entities)
    applied: list[dict] = []
    for pair in accepted:
        first = curves[pair["curve_a"]]
        second = curves[pair["curve_b"]]
        entity_a = _entity_named(result, pair["entity_a"])
        entity_b = _entity_named(result, pair["entity_b"])
        if entity_a is None or entity_b is None:
            return result, applied, "entity_not_snappable"
        if first.kind == "arc" and second.kind == "arc":
            return result, applied, "arc_pair_not_snappable"
        point_a = first.start if pair["end_a"] == "start" else first.end
        point_b = second.start if pair["end_b"] == "start" else second.end
        if first.kind == "arc":
            target, anchor = point_a, "a"
        elif second.kind == "arc":
            target, anchor = point_b, "b"
        else:
            target = ((point_a[0] + point_b[0]) / 2.0, (point_a[1] + point_b[1]) / 2.0)
            anchor = "midpoint"
        shift_a = _distance(point_a, target)
        shift_b = _distance(point_b, target)
        if first.kind != "arc":
            entity_a[pair["end_a"]] = [target[0], target[1]]
        if second.kind != "arc":
            entity_b[pair["end_b"]] = [target[0], target[1]]
        applied.append(
            {
                "entity_a": pair["entity_a"],
                "entity_b": pair["entity_b"],
                "end_a": pair["end_a"],
                "end_b": pair["end_b"],
                "gap_mm": pair["gap_mm"],
                "anchor": anchor,
                "shift_a_mm": shift_a,
                "shift_b_mm": shift_b,
                "point": [target[0], target[1]],
            }
        )
    return result, applied, None


def prepare_endpoint_weld(
    entities: list[dict[str, Any]],
    *,
    policy: str = "report",
    max_move_mm: float | None = None,
    snap: bool = False,
) -> dict[str, Any]:
    """Describe which endpoint pairs may be welded.

    With ``snap=False`` no geometry moves. With ``snap=True`` an accepted
    line-line pair meets at the midpoint and a line-arc pair moves the line to
    the arc endpoint; the rewritten copy is returned privately for submission
    and the published receipt records every pair, gap and shift. In both cases
    the native solver still owns its own coincidence check.

    The receipt is the frozen contract: policy, whether anything was applied,
    the threshold and its source, the candidate and accepted pair counts, the
    largest move the pairs would need, the failure reason and a bounded sample
    of the pairs. ``requested_geometry`` is what the caller sent; the actual
    geometry stays ``None`` until the native solver reports it.
    """
    if policy not in POLICIES:
        raise ValueError(f"endpoint_policy must be one of {', '.join(POLICIES)}")
    if max_move_mm is not None:
        if not isinstance(max_move_mm, (int, float)) or isinstance(max_move_mm, bool):
            raise ValueError("max_move_mm must be a number")
        if not math.isfinite(float(max_move_mm)) or max_move_mm <= 0.0:
            raise ValueError("max_move_mm must be a finite number greater than 0")

    curves, candidates, accepted, refused = _plan(entities, max_move_mm)

    receipt: dict[str, Any] = {
        "policy": policy,
        "applied": False,
        "applied_by": None,
        "native_applied": False,
        "threshold_mm": CLUSTER_TOLERANCE_MM,
        "threshold_source": "closure_diagnostic_cluster",
        "kernel_weld_bound_mm": EXACT_TOLERANCE_MM,
        "kernel_weld_bound_source": "creo_mechdog.profile_diagnostics.EXACT_TOLERANCE_MM",
        "observed_kernel_weld_mm": OBSERVED_KERNEL_WELD_MM,
        "candidate_pairs": len(candidates),
        "accepted_pairs": len(accepted),
        "welded_pairs": 0,
        "refused_pairs": len(refused),
        "max_move_mm": None,
        "max_residual_mm": None,
        "failure_reason": None,
        "pairs": [],
        "refused": [],
        # The weld plan names the entities and the endpoints, so the native
        # side can regularise exactly these coordinates before it writes them.
        "weld_plan": [
            {
                "a": {"entity": candidate["entity_a"], "point": candidate["end_a"]},
                "b": {"entity": candidate["entity_b"], "point": candidate["end_b"]},
                "gap_mm": candidate["gap_mm"],
                "required_move_mm": candidate["required_move_mm"],
            }
            for candidate in accepted[:WELD_PLAN_LIMIT]
        ],
        "requested_geometry": {"entity_count": len(entities), "curve_count": len(curves)},
        "actual_geometry": None,
        "note": (
            "Python reports the pairing evidence only; the native solver owns the "
            "coincidence, so applied stays false until the kernel reports it"
        ),
    }
    if accepted:
        receipt["max_move_mm"] = max(entry["required_move_mm"] for entry in accepted)
    receipt["pairs"] = [
        {
            "curve_a": entry["curve_a"],
            "curve_b": entry["curve_b"],
            "end_a": entry["end_a"],
            "end_b": entry["end_b"],
            "entity_a": entry["entity_a"],
            "entity_b": entry["entity_b"],
            "gap_mm": entry["gap_mm"],
            "required_move_mm": entry["required_move_mm"],
        }
        for entry in accepted[:SAMPLE_LIMIT]
    ]
    receipt["refused"] = [
        {
            "curve_a": entry["curve_a"],
            "curve_b": entry["curve_b"],
            "gap_mm": entry["gap_mm"],
            "reason": entry["reason"],
        }
        for entry in refused[:SAMPLE_LIMIT]
    ]
    # DEV-077/R01: an explicit snap request rewrites the caller's line
    # endpoints before the payload leaves Python, so the receipt states that
    # this time Python did move the geometry and names every pair, gap and
    # shift. The native solver still owns its own coincidence work.
    receipt["snap"] = {
        "requested": bool(snap),
        "applied": False,
        "failure_reason": None,
        "rule": None,
        "max_shift_mm": None,
        "residual_max_mm": None,
        "pairs": [],
    }
    if snap:
        if policy == "reject":
            raise ValueError("snap_endpoints cannot be combined with endpoint_policy=reject")
        if accepted:
            snapped, applied_pairs, failure = _snap_entities(entities, curves, accepted)
            if failure is not None:
                receipt["snap"]["failure_reason"] = failure
            else:
                residual = _plan(snapped, max_move_mm)[2]
                rules = sorted({entry["anchor"] for entry in applied_pairs})
                receipt["snap"].update(
                    {
                        "applied": True,
                        "rule": "+".join(rules),
                        "pairs": applied_pairs[:SAMPLE_LIMIT],
                        "max_shift_mm": max(
                            max(entry["shift_a_mm"], entry["shift_b_mm"]) for entry in applied_pairs
                        ),
                        "residual_max_mm": (
                            max(entry["gap_mm"] for entry in residual) if residual else 0.0
                        ),
                    }
                )
                receipt["applied"] = True
                receipt["applied_by"] = "python_request_rewrite"
                receipt["actual_geometry"] = {
                    "entity_count": len(snapped),
                    "max_endpoint_shift_mm": receipt["snap"]["max_shift_mm"],
                }
                receipt["note"] = (
                    "Python rewrote the accepted line endpoints into one shared point before "
                    "submission; the native solver still owns its own coincidence check"
                )
                receipt["_snapped_entities"] = snapped
    if policy == "reject" and accepted:
        receipt["failure_reason"] = "endpoint_pairs_present"
        receipt["would_reject"] = True
    else:
        receipt["would_reject"] = False
    return receipt


SKETCH_OPS = ("sketch", "airfoil_sketch", "update_sketch_geometry")


def prepare_operations(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Refuse a profile the policy rejects, before a job exists.

    "reject" refuses the plan when the requested endpoints could be welded;
    "report" and the default change nothing. The receipt itself is published
    with the job result, not here, so the plan payload stays the caller's.
    """
    for operation in operations:
        if operation.get("op") not in SKETCH_OPS:
            continue
        policy = operation.get("endpoint_policy", "report")
        snap = bool(operation.get("snap_endpoints"))
        if policy == "report" and not snap:
            continue
        receipt = prepare_endpoint_weld(
            operation.get("entities", []),
            policy=policy,
            max_move_mm=operation.get("max_endpoint_move_mm"),
            snap=snap,
        )
        snapped = receipt.pop("_snapped_entities", None)
        if snap:
            # The rewrite replaces the request geometry; the receipt keeps the
            # before/after evidence and is published with the job result.
            if snapped is not None:
                operation["entities"] = snapped
            operation["snap_endpoint_receipt"] = receipt
        if policy == "weld":
            # The weld policy hands the native side the pairs to regularise.
            # Python still decides and still reports; the native side owns the
            # coordinates it writes.
            operation["weld_pairs"] = receipt.get("weld_plan") or []
        if receipt["would_reject"]:
            pairs = receipt["pairs"][:SAMPLE_LIMIT]
            raise ValueError(
                "endpoint policy reject: the requested profile has "
                f"{receipt['accepted_pairs']} weldable endpoint pair(s); "
                f"largest gap {receipt['max_move_mm']} mm; sample {pairs}"
            )
    return operations


def annotate_result(result: dict[str, Any], operations: list[dict[str, Any]]) -> None:
    """Publish the endpoint weld receipt on the matching operation result."""
    if not isinstance(result, dict):
        return
    entries = result.get("operations")
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        index = entry.get("index")
        if not isinstance(index, int) or not 0 <= index < len(operations):
            continue
        operation = operations[index]
        if operation.get("op") not in SKETCH_OPS:
            continue
        policy = operation.get("endpoint_policy", "report")
        stored = operation.get("snap_endpoint_receipt")
        if isinstance(stored, dict):
            receipt = stored
        else:
            receipt = prepare_endpoint_weld(
                operation.get("entities", []),
                policy=policy,
                max_move_mm=operation.get("max_endpoint_move_mm"),
            )
        if (
            policy == "report"
            and receipt.get("accepted_pairs", 0) == 0
            and not isinstance(stored, dict)
        ):
            continue
        native_block = entry.get("endpoint_weld_native")
        receipt["native"] = native_block if isinstance(native_block, dict) else None
        entry["endpoint_weld"] = receipt
