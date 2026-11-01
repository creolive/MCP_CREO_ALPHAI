"""Offline, source preserving conversion of the archived P12 prism recipe."""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

SOURCE = next(
    Path(__file__)
    .resolve()
    .parents[1]
    .glob("docs/validation/feedback-0.10.0-2026-11-01/originals/06_P12*/p12_v12_native_tree.json")
)
ROUTES = ("strip_prism",)
THICKNESS = 9.87008714331235


def _geometry(points):
    a, b, c = (p["position"] for p in points)
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    length = math.dist(a, b)
    if length <= 0:
        raise ValueError("degenerate triangle edge")
    u = [x / length for x in ab]
    projection = sum(ac[i] * u[i] for i in range(3))
    perpendicular = [ac[i] - projection * u[i] for i in range(3)]
    height = math.sqrt(sum(x * x for x in perpendicular))
    if height <= 0:
        raise ValueError("degenerate triangle")
    area = length * height / 2
    return a, ab, projection, height, area


def convert_recipe(tree: dict, *, route: str) -> dict:
    if route not in ROUTES:
        raise ValueError(f"unsupported route: {route}")
    if (
        not isinstance(tree, dict)
        or not isinstance(tree.get("meta"), dict)
        or not isinstance(tree.get("features"), list)
    ):
        raise ValueError("tree requires meta and features")
    features = tree["features"]
    if not features:
        raise ValueError("empty feature tree")
    canonical = json.dumps(tree, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    if tree == json.loads(SOURCE.read_text(encoding="utf-8")):
        digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    unresolved, mapped, seq_map, triangles = [], [], {}, []
    used = set()
    current = None
    allowed = {
        "sketch": {"seq", "op", "label", "plane", "offset", "entities"},
        "extrude": {"seq", "op", "label", "sketch", "depth", "direction", "new_body", "mode"},
        "datum_points": {"seq", "op", "label", "points"},
        "datum_plane": {"seq", "op", "label", "thru_points", "note"},
        "axis_pattern": {"seq", "op", "label", "leader", "axis", "count", "increment_deg", "note"},
        "round": {"seq", "op", "label", "radius", "edge_anchor"},
        "merge_all_bodies": {"seq", "op"},
    }
    for expected, feature in enumerate(features, 1):
        if (
            not isinstance(feature, dict)
            or feature.get("seq") != expected
            or not isinstance(feature.get("op"), str)
        ):
            raise ValueError(f"invalid feature at sequence {expected}")
        op, seq = feature["op"], feature["seq"]
        seq_map[str(seq)] = []
        if op not in allowed:
            unresolved.append({"seq": seq, "field": "op", "reason": f"unknown op {op}"})
            continue
        for field in sorted(feature.keys() - allowed[op]):
            unresolved.append({"seq": seq, "field": field, "reason": "unmapped source field"})
        item = copy.deepcopy(feature)
        item.pop("seq")
        item.pop("note", None)
        if op == "datum_points":
            points = feature.get("points")
            label = feature.get("label")
            if not isinstance(label, str) or not isinstance(points, list) or len(points) != 3:
                raise ValueError(f"invalid datum_points at {seq}")
            current = {}
            for point in points:
                if (
                    not isinstance(point, dict)
                    or set(point) != {"name", "position"}
                    or not isinstance(point["name"], str)
                    or len(point["position"]) != 3
                ):
                    raise ValueError(f"invalid point at {seq}")
                name = point["name"]
                if name in current:
                    raise ValueError(f"duplicate point at {seq}")
                suffix = {"p_a": "a", "p_b": "b", "p_c": "c"}.get(name)
                if suffix is None:
                    unresolved.append(
                        {
                            "seq": seq,
                            "field": "points.name",
                            "reason": f"unmapped point name {name}",
                        }
                    )
                    continue
                new_label = f"{label}_{suffix}"
                if len(new_label) > 28 or new_label in used or not new_label[0].islower():
                    raise ValueError(f"invalid or duplicate generated label {new_label}")
                used.add(new_label)
                current[(label, name)] = new_label
                mapped.append(
                    {
                        "op": "datum_points",
                        "label": new_label,
                        "points": [{"name": new_label, "position": point["position"]}],
                    }
                )
                seq_map[str(seq)].append(new_label)
            current["source_label"] = label
            current["points"] = points
            continue
        if op == "datum_plane":
            if current is None or feature.get("thru_points") != ["p_a", "p_b", "p_c"]:
                unresolved.append(
                    {
                        "seq": seq,
                        "field": "thru_points",
                        "reason": "cannot resolve group scoped point names",
                    }
                )
                continue
            source_label = current["source_label"]
            item.pop("thru_points")
            item["reference"] = {
                "kind": "through_points",
                "points": [current[(source_label, n)] for n in feature["thru_points"]],
            }
            current["plane"] = feature["label"]
        elif op == "sketch" and isinstance(feature.get("entities"), dict):
            if (
                current is None
                or feature.get("plane") != {"datum_plane_label": current.get("plane")}
                or set(feature["entities"]) != {"triangle_uv"}
            ):
                unresolved.append(
                    {
                        "seq": seq,
                        "field": "sketch",
                        "reason": "unresolved triangle or plane placeholder",
                    }
                )
                continue
            a, ab, projection, height, area = _geometry(current["points"])
            item["plane"] = {
                "type": "frame",
                "origin": a,
                "reference": {"kind": "datum_feature", "label": current["plane"]},
                "u_axis": ab,
            }
            item["dimensioning"] = "coordinates"
            item["entities"] = [
                {
                    "type": "polyline",
                    "name": "tri",
                    "points": [
                        [0, 0],
                        [math.dist(a, current["points"][1]["position"]), 0],
                        [projection, height],
                    ],
                    "closed": True,
                }
            ]
            triangles.append({"source_seq": seq, "area_mm2": area, "volume_mm3": area * THICKNESS})
        elif op == "sketch" and (
            not isinstance(feature.get("entities"), list)
            or not isinstance(feature.get("plane"), str)
        ):
            unresolved.append({"seq": seq, "field": "sketch", "reason": "unmapped sketch payload"})
            continue
        elif op == "axis_pattern":
            unresolved.append(
                {
                    "seq": seq,
                    "field": "note",
                    "reason": "leader requires unioned blade body; body grouping unproven",
                }
            )
            continue
        elif op == "merge_all_bodies":
            unresolved.append(
                {"seq": seq, "field": "op", "reason": "no equivalent supported operation"}
            )
            continue
        elif op == "round":
            unresolved.append(
                {
                    "seq": seq,
                    "field": "edge_anchor",
                    "reason": "edge anchor has no proven round reference mapping",
                }
            )
            continue
        if op == "extrude" and feature.get("new_body") and feature.get("depth") != THICKNESS:
            unresolved.append(
                {
                    "seq": seq,
                    "field": "depth",
                    "reason": "strip thickness differs from source precision",
                }
            )
        if "label" in item:
            if item["label"] in used:
                raise ValueError(f"duplicate label {item['label']}")
            used.add(item["label"])
            seq_map[str(seq)].append(item["label"])
        mapped.append(item)
    if len(triangles) != 96:
        unresolved.append({"field": "triangles", "reason": f"expected 96, found {len(triangles)}"})
    unresolved.extend(
        [
            {
                "field": "family_table",
                "reason": "80 entry index to component mapping has no source proof",
            },
            {
                "field": "surface_chain",
                "reason": "Q08-Q10 loft/project/trim and thicken chain not present in prism source",
            },
        ]
    )
    batches = []
    starts = (
        [0, 194, 386, 578, len(mapped)]
        if len(mapped) == 580
        else list(range(0, len(mapped), 196)) + [len(mapped)]
    )
    for start, stop in zip(starts, starts[1:]):
        batch_id = f"p12_{len(batches) + 1:02d}"
        batches.append(
            {
                "batch_id": batch_id,
                "depends_on": [batches[-1]["batch_id"]] if batches else [],
                "operations": mapped[start:stop],
            }
        )
    return {
        "status": "blocked" if unresolved else "ready",
        "route": route,
        "source_sha256": digest,
        "source_seq_map": seq_map,
        "source_feature_count": len(features),
        "split_only_operation_count": len(features) + 192,
        "operation_count": len(mapped),
        "batches": batches,
        "unresolved": unresolved,
        "triangles": triangles,
        "approximation": "96 independent triangle prisms over 48 strips; overlap prevents summing to union volume",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", choices=ROUTES, default="strip_prism")
    args = parser.parse_args()
    tree = json.loads(SOURCE.read_text(encoding="utf-8"))
    manifest = convert_recipe(tree, route=args.route)
    print(
        json.dumps(
            {
                k: v
                for k, v in manifest.items()
                if k not in {"batches", "source_seq_map", "triangles"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("batch_sizes:", [len(b["operations"]) for b in manifest["batches"]])


if __name__ == "__main__":
    main()
