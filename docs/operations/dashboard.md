# Local Dashboard

TraceForge's dashboard is a localhost-first, unauthenticated workbench for exact replay. It
accepts only a runner registered when the process starts, uses reviewed JSON evidence, and never
falls back to a live model or tool call. It is not a sandbox: a custom runner is trusted local
Python code with the server process's authority.

The Workbench has three top-level views:

- **Original runs** come from the capture worker's SQLite assembly state and point to sealed
  filesystem Replay Capsules.
- **Exact Replay Lab** runs one trusted startup-registered runner against reviewed evidence.
- **Replay attempts** come from `replay_history` and never create or replace original runs.
  Opening Replay Attempts refreshes this list from the authoritative `/api/history` endpoint, so a
  replay completed in the current page appears without a browser reload. Historical attempts stay
  visible when a custom runner is no longer registered, but show **Runner unavailable** instead of
  an action that cannot succeed.

The browser receives presentation-neutral JSON. It does not query SQLite, open capsule paths, or
compute integrity, replay, diff, or regression semantics.

## Start with an original-run catalog

Point the server at the assembly database written by the local capture worker:

```sh
traceforge serve \
  --assembly-database .traceforge-data/assembly.sqlite3 \
  --capsule-directory .traceforge-data/capsules
```

The optional distributed Compose stack supplies `/data/assembly.sqlite3` through
`TRACEFORGE_ASSEMBLY_PATH` and `/data/capsules` through `TRACEFORGE_CAPSULE_DIRECTORY`. A host
Workbench reading that Compose-produced database must point its trusted capsule directory at the
host side of the same volume. Without an assembly database the Workbench shows an empty
original-run view while the existing replay lab remains available. The UI distinguishes no
configured source, an unavailable configured source, and a valid source with zero captures.

For the repository's default local data directory:

```sh
TRACEFORGE_ASSEMBLY_PATH="$PWD/.traceforge-data/assembly.sqlite3" \
TRACEFORGE_CAPSULE_DIRECTORY="$PWD/.traceforge-data/capsules" \
TRACEFORGE_HISTORY_PATH="$PWD/.traceforge-data/history.sqlite3" \
traceforge serve --host 127.0.0.1 --port 18000
```

## Recreate the controlled manual-review catalog

The developer-only generator creates one synthetic, reviewed Replay Capsule `0.2.0` run with the
subject **Agentic Chatbot — Controlled Demo** and a model → `tool:web.search` → model dependency
sequence. It uses no Kafka, Docker, network access, or external API. Generated databases and
capsules stay outside the repository and are not committed.

From the repository root:

```sh
python scripts/create_workbench_review_data.py \
  --output ~/.traceforge/workbench-review

TRACEFORGE_ASSEMBLY_PATH="$HOME/.traceforge/workbench-review/assembly.sqlite3" \
TRACEFORGE_CAPSULE_DIRECTORY="$HOME/.traceforge/workbench-review/capsules" \
TRACEFORGE_HISTORY_PATH="$HOME/.traceforge/workbench-review/history.sqlite3" \
traceforge serve --host 127.0.0.1 --port 18000
```

The generator safely replaces only a directory carrying its ownership marker and refuses output
inside the repository or a directory containing unrelated files. Re-running it restores a clean
catalog with exactly one original run and an empty replay-attempt history.

Use this deterministic flow to prepare a human review; it is not a claim of visual acceptance:

1. Open `http://127.0.0.1:18000/#runs` and inspect **Agentic Chatbot — Controlled Demo**. Its
   execution map contains model → `web.search` → model and its evidence is completed, sealed,
   integrity verified, and replayable.
2. Open `http://127.0.0.1:18000/#replay`, select **Weather Grounding**, choose **Load verified
   example**, then choose **Run exact replay**. Inspect the returned technical status,
   changed deterministic match, Evidence-backed Divergence Analysis, `ExecutionDiff`, and any
   existing regression assertions.
3. After technical completion, choose **Promote to regression**. Confirm the assertion selection is
   initially empty. Add only the reviewed expectation
   `output.umbrella_needed`, choose `equals`, enter JSON value `true`, and confirm the explicit
   developer approval. Review the generated specification and download the one atomic ZIP bundle
   containing the unchanged capsule, specification, and pytest artifact.
4. Open `http://127.0.0.1:18000/#attempts` and refresh once. The completed replay appears in the
   persisted replay-attempt history.

The catalog preserves a recorded capsule path when it exists in the current process environment.
If a container-local path such as `/data/capsules/<capture-id>.json` does not exist on the host, it
resolves only `<capture-id>.json` under the trusted startup capsule directory. Invalid capture IDs,
path traversal, and symlink escape are rejected. No HTTP input can set this directory, and no raw
path is returned by the API.

The read-only endpoints are:

```text
GET /api/runs
GET /api/runs/{run_id}
GET /api/run-source
```

`GET /api/run-source` returns only `state`, a bounded reason code, and `run_count`; it never returns
the configured database or capsule path. Assembly SQLite is opened with SQLite read-only mode.
A nonexistent configured path is reported as unavailable and is never created by a catalog read.

Run detail includes operational completion/correlation metadata and validated capsule-derived
invocation, original execution, ordered dependencies, output, and evidence metadata. It never
returns the capsule filesystem path. Unknown run IDs return `run-not-found` with HTTP 404.

Evidence states are explicit:

- `pending`: capture is incomplete;
- `missing`: a completed capture has no usable capsule reference or file;
- `invalid`: the referenced file cannot pass existing capsule validation; and
- `verified`: the sealed capsule passed structural, semantic, fingerprint, and integrity checks.

`replayable` additionally requires the existing recorded-tool-error preflight. It does not imply
that a matching application runner has been registered.

## Start and register a local runner

The three built-in demos are available by default. Register a project runner only through the
trusted local command line at startup; this may be repeated:

```sh
traceforge serve --runner my-agent=my_project.traceforge_runner:run
```

`my-agent` is a stable lowercase ID; the target must be `MODULE:FUNCTION` and must be callable.
Duplicate IDs (including built-ins), malformed registrations, and import failures stop startup.
The browser, an upload, a capsule, and an HTTP request cannot provide module paths or import code.
Custom runners have no synthetic example: upload or paste reviewed evidence from that project.

The browser cannot provide `--assembly-database`, `TRACEFORGE_ASSEMBLY_PATH`,
`--capsule-directory`, `TRACEFORGE_CAPSULE_DIRECTORY`, a capsule path, or a runner import. Those are
trusted process-startup boundaries only.

Promotion likewise accepts no browser-provided server path, output directory, filename, or
overwrite option. An existing regression specification is optional. Promotion performs exact replay
again with the currently submitted capsule and startup-registered runner, validates only the
assertions the developer added, and returns one content-addressed ZIP with fixed internal names.
This prevents separate browser collision renames from mixing artifact generations. The server
writes nothing. Trusted Python/CLI filesystem export still refuses an existing target unless
replacement is explicitly requested.

## Capture to replay

The current public APIs keep recording, sealing, and replay separate:

```python
from traceforge import CaptureSession, seal_capsule

session = CaptureSession(
    capsule_id="reviewed-capsule", run_id="local-run", capture_kind="agent-run",
    producer={"name": "my-project", "version": "local"},
    subject={"name": "my-agent", "version": "local"}, operation="answer",
    invocation_input={"question": "..."},
)
# CaptureSession applies BestEffortRedactionScanner before data enters the draft.
session.record_model("chat", {"messages": []}, lambda request: {"output": "recorded"})
draft = session.finish("completed", {"answer": "recorded"})
sealed = seal_capsule(draft)
```

Write a separate developer-approved regression specification with `version: "0.1.0"` and
non-empty `assertions` containing `path`, `operator`, and `expected`; do not put expectations in
the capsule. Save the sealed capsule and specification as reviewed JSON, then use the dashboard's
Upload JSON or Paste JSON mode. The runner receives the invocation input and a recorded
`DependencyAdapter`; exact replay validates, consumes the recorded dependencies in order, and
blocks common Python socket entry points.

Built-in demonstrations use one canonical reviewed source under `examples/`; package installation
places those JSON files under the TraceForge data directory so the wheel and Docker image offer
the same examples. Fixtures are sanitized but best-effort redaction cannot prove secret absence.

## Current Workbench limitations

- Run summaries synchronously read and validate every referenced capsule on each catalog request.
  One malformed or unreadable capsule is isolated as `invalid`, but a large capsule or large local
  catalog can delay the entire response; size bounds, pagination, and cached projections are
  deferred until measured need.
- Files in a cloud-managed or optimized local directory must be materially present. On macOS a
  `dataless` placeholder may block while the operating system tries to retrieve its contents;
  materialize the file or use a resident local review directory before launching Workbench.
- Current assembly rows store service-local absolute paths. The startup capsule-root fallback is
  backward compatible, but a portable durable reference remains follow-up storage debt.
- Replay history stores compact attempt summaries, not replay observations, `ExecutionDiff`, or
  assertion details. A structured diff is shown from a live technically completed replay response but is not
  persisted into original evidence.
- Original runs do not yet retain an application-runner association, so run detail does not expose
  a replay button that could guess which runner to use.
- Trace/span IDs are displayed when assembly state contains them; parent-child spans and causal or
  multi-agent graphs are not implemented.
- The service remains localhost-first and unauthenticated. Do not expose it publicly.
