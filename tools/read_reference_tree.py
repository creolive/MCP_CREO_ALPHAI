"""Read the feature trees of a part file and keep them as evidence.

The route is: adopt the disk file as a managed copy (inspect then apply),
inspect its features, and dump each feature's element tree. A feature whose
tree the kernel refuses is recorded with the kernel's own verdict, so a
missing tree is evidence instead of a guess.

    python tools/read_reference_tree.py <file.prt> [--feature-id N] [--json out.json]

The session must be available (creo_startup_status reports connected) and the
file must be a healthy independent part in millimeters.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ELEMENT = re.compile(r"<(PRO_[A-Z_0-9]+)")


def payload(result) -> dict[str, Any]:
    if result.structured_content is not None:
        return result.structured_content
    chunks = [
        getattr(block, "text", "")
        for block in (result.content or [])
        if getattr(block, "text", None)
    ]
    if chunks:
        try:
            return json.loads(chunks[0])
        except json.JSONDecodeError:
            return {"raw": "\n".join(chunks)[:1500]}
    return {}


def summarize_tree(xml_text: str) -> dict[str, Any]:
    """Summarise an element tree: the feature type, name and element names."""
    elements: list[str] = []
    for match in ELEMENT.finditer(xml_text):
        name = match.group(1)
        if name not in elements:
            elements.append(name)
    feature_type = ""
    feature_name = ""
    match = re.search(r"<PRO_E_FEATURE_TYPE[^>]*>([^<]+)<", xml_text)
    if match:
        feature_type = match.group(1)
    match = re.search(r"<PRO_E_STD_FEATURE_NAME[^>]*>([^<]*)<", xml_text)
    if match:
        feature_name = match.group(1)
    return {
        "feature_type": feature_type,
        "feature_name": feature_name,
        "elements": elements,
        "has_blend_elements": any("BLEND" in element for element in elements),
    }


async def settle(client, job_id: str, budget: int = 300) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + budget
    final: dict[str, Any] = {}
    while asyncio.get_running_loop().time() < deadline:
        final = payload(
            await client.call_tool("creo_get_job", {"job_id": job_id, "detail": "compact"})
        )
        if final.get("status") in ("succeeded", "failed", "unknown_outcome"):
            break
        await asyncio.sleep(2)
    full = payload(await client.call_tool("creo_get_job", {"job_id": job_id, "detail": "full"}))
    if full.get("status"):
        final = full
    return final


async def adopt(path: Path, client) -> tuple[str | None, dict[str, Any]]:
    """Adopt the disk file and return the managed model id."""
    report: dict[str, Any] = {}
    inspected = payload(
        await client.call_tool("creo_adopt_file", {"file_path": [str(path)], "mode": "inspect"})
    )
    token = inspected.get("evidence_token")
    report["inspect_status"] = inspected.get("status") or inspected.get("state")
    if not token:
        report["inspect"] = json.dumps(inspected, ensure_ascii=False)[:300]
        return None, report
    applied = payload(
        await client.call_tool(
            "creo_adopt_file",
            {
                "file_path": [str(path)],
                "mode": "apply",
                "evidence_token": token,
                "idempotency_key": "reference-" + re.sub(r"[^A-Za-z0-9_-]", "_", path.stem)[:40],
            },
        )
    )
    job_id = applied.get("job_id")
    if not job_id:
        report["apply"] = json.dumps(applied, ensure_ascii=False)[:300]
        return None, report
    final = await settle(client, job_id)
    report["apply_status"] = final.get("status")
    report["apply_message"] = str(final.get("message"))[:200]
    items = list(final.get("items") or [])
    record = ROOT / "jobs" / job_id / "job.json"
    if record.exists():
        try:
            stored = json.loads(record.read_text(encoding="utf-8", errors="replace"))
            items = stored.get("items") or items
        except json.JSONDecodeError:
            pass
    for item in items:
        conflict = item.get("conflict") or {}
        if conflict.get("model_id"):
            report["reuse"] = "already adopted"
            return conflict["model_id"], report
        if item.get("model_id"):
            return item["model_id"], report
    return None, report


async def read_reference_tree(
    path: Path, feature_id: int | None = None, model_id: str | None = None
) -> dict[str, Any]:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    report: dict[str, Any] = {"file": str(path), "features": []}
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        deadline = asyncio.get_running_loop().time() + 240
        state: dict[str, Any] = {}
        while asyncio.get_running_loop().time() < deadline:
            state = payload(await client.call_tool("creo_startup_status", {}))
            if state.get("connected") or state.get("state") in ("timeout", "failed", "error"):
                break
            await asyncio.sleep(2)
        if not state.get("connected"):
            report["error"] = "the session is not connected"
            return report
        if model_id:
            report["adoption"] = {"reuse": "the caller passed the model id"}
        else:
            model_id, adoption = await adopt(path, client)
            report["adoption"] = adoption
        if not model_id:
            report["error"] = "no managed model for the file"
            return report
        report["model_id"] = model_id
        features = payload(
            await client.call_tool(
                "creo_inspect_model",
                {"model_id": model_id, "detail": "full", "section": "features", "limit": 200},
            )
        )
        rows = (features.get("data") or {}).get("features") or []
        targets = [row for row in rows if feature_id is None or row.get("id") == feature_id]
        for row in targets:
            entry: dict[str, Any] = {
                "id": row.get("id"),
                "name": row.get("name"),
                "type": row.get("type"),
            }
            current = payload(await client.call_tool("creo_inspect_model", {"model_id": model_id}))
            revision = current.get("revision") or (current.get("data") or {}).get("revision") or 1
            submitted = payload(
                await client.call_tool(
                    "creo_execute_plan",
                    {
                        "operations": [{"op": "dump_tree", "feature": row.get("id")}],
                        "model_id": model_id,
                        "expected_revision": revision,
                    },
                )
            )
            job_id = submitted.get("job_id")
            if not job_id:
                entry["status"] = "refused"
                entry["message"] = str(submitted.get("message") or submitted)[:300]
                report["features"].append(entry)
                continue
            final = await settle(client, job_id)
            entry["status"] = final.get("status")
            entry["message"] = str(final.get("message"))[:300]
            operations = (final.get("result") or {}).get("operations") or []
            tree_path = operations[-1].get("file") if operations else None
            if tree_path and Path(tree_path).exists():
                xml_text = Path(tree_path).read_text(encoding="utf-8-sig", errors="replace")
                entry["tree_file"] = tree_path
                entry["tree"] = summarize_tree(xml_text)
            report["features"].append(entry)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="the .prt file to read")
    parser.add_argument("--feature-id", type=int, default=None)
    parser.add_argument(
        "--model-id", default="", help="read a managed model directly instead of adopting the file"
    )
    parser.add_argument("--json", default="", help="write the report to this path")
    args = parser.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(json.dumps({"error": f"file not found: {args.file}"}))
        return 1
    report = asyncio.run(read_reference_tree(path, args.feature_id, args.model_id or None))
    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2)[:6000])
    return 0 if not report.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
