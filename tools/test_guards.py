"""Verify stale edits are rejected and partial native mutations roll back."""

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "tools.test_guards", *sys.argv[1:]], cwd=ROOT)
    )

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tools.test_extended import call, job
from version import VERSION


async def main():
    report = {"version": VERSION}
    core = json.loads((ROOT / "build/general_integration_test.json").read_text(encoding="utf-8"))
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as c:
        model = await call(c, "creo_inspect_model", {"model_id": core["main_models"]["disk"]})
        stale = await c.call_tool(
            "creo_set_parameters",
            {
                "model_id": model["model_id"],
                "expected_revision": model["revision"] - 1,
                "values": {"SIZE": 18},
            },
        )
        assert stale.is_error
        report["stale_revision_rejected"] = True
        before = hashlib.sha256(Path(model["part_file"]).read_bytes()).hexdigest()
        request = await call(
            c,
            "creo_execute_plan",
            {
                "model_id": model["model_id"],
                "expected_revision": model["revision"],
                "operations": [
                    {"op": "set_parameters", "values": {"SIZE": 18.0}},
                    {"op": "set_dimensions", "values": [{"id": 2000000000, "value": 12}]},
                ],
            },
        )
        for _ in range(720):
            result = await call(c, "creo_get_job", {"job_id": request["job_id"]})
            if result["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(1)
        assert result["status"] == "failed" and result["result"]["rollback_succeeded"], result.get(
            "message"
        )
        after = await call(c, "creo_inspect_model", {"model_id": model["model_id"]})
        assert after["status"] == "ready" and after["revision"] == model["revision"]
        assert hashlib.sha256(Path(model["part_file"]).read_bytes()).hexdigest() == before
        # Fresh native query confirms the first operation's parameter/volume change was undone.
        fresh = await job(c, "creo_refresh_model", {"model_id": model["model_id"]})
        actual = fresh["result"]["inspection"]
        assert actual["parameters"] == model["inspection"]["parameters"]
        assert abs(actual["volume_mm3"] - model["inspection"]["volume_mm3"]) < 1e-6
        report.update(
            rollback_succeeded=True,
            original_file_unchanged=True,
            revision_unchanged=True,
            live_geometry_and_parameters_restored=True,
            failed_job=result,
            refresh_job=fresh,
            success=True,
        )
        (ROOT / "build/guards_integration_test.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("GUARDS_SUCCESS=1", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
