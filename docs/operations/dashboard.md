# Local Dashboard

TraceForge's dashboard is a localhost-first, unauthenticated workbench for exact replay. It
accepts only a runner registered when the process starts, uses reviewed JSON evidence, and never
falls back to a live model or tool call. It is not a sandbox: a custom runner is trusted local
Python code with the server process's authority.

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
