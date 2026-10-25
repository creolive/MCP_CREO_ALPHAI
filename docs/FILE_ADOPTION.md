# Path and batch adoption (FEAT-048)

Developer live acceptance passed on 2026-10-25/26 (two real-fixture batches, rev 1, save/reload, window/source-byte preservation, same-key replay); WorkBuddy black-box acceptance remains pending. Evidence and report SHA256s: [development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md](development/BATCH2-LIVE-ACCEPTANCE-2026-10-26.md).

`creo_adopt_file(file_path, mode="inspect", evidence_token=None, idempotency_key=None)` accepts one absolute Windows native file path or an ordered list of 1-20 paths. Explicit `.prt.N` selects that exact numeric version. `.prt` selects the highest numeric version, falling back to the extension-only file when no numbered file exists. Target names are generated internally.

1. Call `inspect` with the paths. Inspect is synchronous, uses one channel, may retrieve absent source models without displaying them, and reports per-item findings and source provenance. It produces a token valid for 600 seconds. Review the returned source identities and refusals.
2. Call `apply` with the same ordered paths, token and a new 8-80 character idempotency key. One accepted parent job owns the sequential batch; poll its `job_id` with `creo_get_job` until a recognized terminal status.
3. Reuse successful item `model_id` values for later assembly occurrences and edits. An `item_job_id` identifies durable internal execution/recovery evidence; it is not a separately submitted job or an instruction to resubmit.

Only healthy independent millimeter parts and sheetmetal are eligible. Assemblies, unhealthy features, external dependencies, and other length units are refused. A duplicate exact selected origin receives `duplicate_source` with a zero-based `duplicate_of` index. Managed output or an already-adopted origin returns its existing model identity and reuse guidance.

## Source provenance and window behavior

The selector uses the exact origin path, disk SHA256, session fingerprint, native model ID, version stamp, modification flag and live inspection. It never chooses the source through the current window. Every actual copy independently rechecks the recorded identities, health, units and dependencies; hashing also occurs before and after execution.

- `fresh_retrieval`: the source name was absent and the exact selected file was retrieved without display. The source remains resident, reported through `resident_set_changed`. A failed retrieve may also leave resident objects; a `possible` change is reported and never erased automatically.
- `existing_resident`: the source is already resident, its exact origin matches, and its modification flag is proven false. Apply copies that explicitly inspected resident state. `disk_resident_content_equality="unknown"` is deliberate: Toolkit does not provide a disk version-stamp comparison, so a file replaced externally before inspection cannot be proven identical to the resident content. Session identity, stamp, source state, and disk bytes are still bound and rechecked independently.

Modified, wrong-origin, unresolved identity, and ambiguous sources are refused. For fresh disk semantics, arrange for the source name to be absent through prior manual session management before inspecting. The tool never erases, saves, backs up or renames source models, and never activates their windows. It copies, saves, erases and reloads only the new managed target. Active-window preservation is checked natively, and still requires live acceptance on the target Creo environment.

## Partial results, protection and replay

Each item has its own durable journal. A successful item has a saved/reloaded verified target, `revision=1`, and a committed managed registry before the next item starts. A known pre-copy refusal continues to the next item. A copy/delivery/disconnect timeout or uncertain durable commit stops dispatch and marks the remaining eligible items `not_attempted`; unresolved models keep their reservation. Successful siblings are never rolled back.

The parent uses existing terminal statuses: `succeeded` when at least one item committed and no outcome is unknown, `failed` when all attempted items were known refusals, and `unknown_outcome` when execution or commit is unconfirmed. Check `items`, `item_counts`, `all_adopted` and `partial_result`; parent success does not imply every input was adopted.

The same idempotency key replays the original parent/result without native execution, including after token expiry. A different ordered path list, selected file identity or evidence token under that key is rejected. Polling may materialize an already-durable commit after a metadata interruption, but never resumes native execution or dispatches unfinished items. A different key does not bypass existing source ownership/protection.

Each native child remains bounded by 115 seconds; builds and file hashes retain their existing limits. Parent polling derives its fixed lifetime from the admitted 1-20 item count, allowing the full sequential work instead of applying the ordinary single-job timeout. This is not a queue, parallel execution, automatic retry, or a configurable general budget API.

## Validation and live scenarios

Offline regression covers invalid structures, version selection, duplicate origins, inspection refusals, source changes, token expiry, idempotency changes/replay, ordinary refusal after success, unknown/timeout stop, reservation retention, durable commit/materialization interruption, one parent lock/runner, and revision exactly once. The production `adoption_source.h` admission helper has a C++ harness. Existing current-model adoption and open-file tests remain applicable.

After session clearance, the developer driver is:

```powershell
.\.venv\Scripts\python.exe tools\test_file_adoption.py 'E:\external\part_a.prt.1' 'E:\external\part_b.prt.2'
```

Supply at least one healthy external source, and optionally an unhealthy/non-mm/dependent one. The driver adds one duplicate, verifies current-model preservation, file SHA before/after, independent save/reload/revision, partial results and same-key replay. It never injects timeouts or cleans session objects. Exercise a fresh absent source and a healthy source already loaded by an assembly in separate permitted runs. Wrong-origin and modified resident refusal need explicit prepared live cases.

WorkBuddy acceptance uses connected public MCP tools only: confirm public environment/tool identity, inspect supplied sources, review provenance, apply once and poll the accepted parent, then record IDs, source fingerprints, per-item terminal states, save/reload/revision and actual Creo windows. Repeat the key to verify replay, and include duplicate, already-managed, unhealthy, modified-resident and wrong-origin cases. Record concurrency and any internal mechanism not actually observed as unverified. Do not ask WorkBuddy to read source/config, run local scripts, clear protection, terminate Creo or inject faults.
