"""P12 staged driver. Default invocation only checks the offline manifest."""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from tools.convert_p12_feedback import SOURCE, convert_recipe

ROOT = Path(__file__).resolve().parents[1]


def stage_batches(manifest, strips):
    if strips not in (1, 4, 48):
        raise ValueError("stage must contain 1, 4, or 48 strips")
    labels = {label for seq, group in manifest["source_seq_map"].items()
              if int(seq) <= 2 + 8 * strips for label in group}
    selected = [op for batch in manifest["batches"] for op in batch["operations"]
                if op.get("label") in labels]
    if len(selected) != 2 + 12 * strips:
        raise ValueError("source stage does not form complete strips")
    chunks = [selected[:194]]
    chunks.extend(selected[start:start + 192] for start in range(194, len(selected), 192))
    return [chunk for chunk in chunks if chunk]


async def run_live(batches, model_name):
    from fastmcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=120) as client:
        model_id = revision = None
        for index, operations in enumerate(batches, 1):
            arguments = {"operations": operations}
            if model_id is None:
                arguments["model_name"] = model_name
            else:
                arguments.update(model_id=model_id, expected_revision=revision)
            reply = await client.call_tool("creo_execute_plan", arguments)
            if reply.is_error:
                raise RuntimeError(f"batch {index} rejected; no resubmission: {reply.content}")
            created = reply.structured_content or {}
            job_id = created.get("job_id")
            if not job_id:
                raise RuntimeError(f"batch {index} returned no job_id")
            deadline = time.monotonic() + 900
            while True:
                reply = await client.call_tool("creo_get_job", {"job_id": job_id, "detail": "full"})
                if reply.is_error:
                    raise RuntimeError(f"job {job_id} query failed; stop")
                terminal = reply.structured_content or {}
                if terminal.get("status") not in ("queued", "running"):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"job {job_id} timed out; do not resubmit")
                await asyncio.sleep(1)
            print(json.dumps({"batch": index, "job_id": job_id, "status": terminal.get("status"), "model_id": terminal.get("model_id"), "revision": terminal.get("revision")}, ensure_ascii=False))
            if terminal.get("status") != "succeeded" or terminal.get("result", {}).get("saved_file_reloaded_and_verified") is not True:
                raise RuntimeError(f"batch {index} incomplete; stop and inspect original job")
            model_id, revision = terminal["model_id"], terminal["revision"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("one", "four", "blade", "hub_array_assembly"), default="one")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    args = parser.parse_args()
    manifest = convert_recipe(json.loads(SOURCE.read_text(encoding="utf-8")), route="strip_prism")
    assert manifest["source_feature_count"] == 391
    assert manifest["split_only_operation_count"] == 583
    assert all(len(batch["operations"]) <= 200 for batch in manifest["batches"])
    assert len({op["label"] for batch in manifest["batches"] for op in batch["operations"] if "label" in op}) == manifest["operation_count"]
    print(json.dumps({"status": manifest["status"], "source_sha256": manifest["source_sha256"], "operation_count": manifest["operation_count"], "batch_sizes": [len(b["operations"]) for b in manifest["batches"]], "unresolved": manifest["unresolved"]}, ensure_ascii=False, indent=2))
    if not args.live:
        return
    if not args.confirm_session_usable:
        parser.error("live requires --confirm-session-usable")
    if args.stage == "hub_array_assembly":
        parser.error("hub/array/assembly remain unresolved")
    from creo_mechdog.schema import validate_operations

    batches = stage_batches(manifest, {"one": 1, "four": 4, "blade": 48}[args.stage])
    for batch in batches:
        validate_operations(batch)
    asyncio.run(run_live(batches, f"p12_{args.stage}_{int(time.time())}"))


if __name__ == "__main__":
    main()
