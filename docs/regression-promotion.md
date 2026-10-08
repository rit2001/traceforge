# Regression Promotion and CI

Regression promotion is the deliberate creation of a developer-authored `RegressionSpec 0.1.0`
from selected expectations applied to a technically completed replay result. It does not change
the historical run.

```text
Capture → Replay → Understand → Promote → CI
```

The trust boundary is strict:

- **Historical evidence**: the sealed Replay Capsule records what happened. It remains immutable.
- **Approved expectation**: the regression specification records what a developer now expects. It
  is mutable source code and must be reviewed like any other test input.
- **Derived runtime values**: `ExecutionDiff`, `DivergenceAnalysis`, and `RegressionResult` explain
  or evaluate one replay. None is evidence or approval, and promotion does not modify them.

Promotion never silently accepts a replay output, snapshots the entire observation, or turns a
passing result into an approved expectation.

## Domain workflow

Use exact replay first, then select only meaningful expectations supported by the existing
`equals` and `contains` operators:

```python
import json
from pathlib import Path

from traceforge import export_pytest, promote_regression, replay_exact
from traceforge.replay import CallableFrameworkAdapter

result = replay_exact(capsule, CallableFrameworkAdapter(runner))
spec = promote_regression(
    result,
    [
        {
            "path": "output.umbrella_needed",
            "operator": "equals",
            "expected": True,
        }
    ],
    developer_approved=True,
)

spec_path = Path("regression-spec.json")
spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
export_pytest(
    Path("replay-capsule.json"),
    "my_project.traceforge_runner:run",
    spec_path,
    Path("test_traceforge_regression.py"),
)
```

`developer_approved` is required, keyword-only, and accepts only the boolean `True`. The supplied
result must report technical completion and contain diff and analysis values. Assertions must be
non-empty strict JSON, contain no exact duplicates, remain valid under the existing regression
contract, and pass against the supplied replay observation. A false `deterministic_match` does not
block promotion: repaired behavior can and often should differ from the captured failure.

`ReplayResult` is publicly constructible. The Python function trusts that caller-supplied value; it
does not attest that `replay_exact()` produced it. Its guarantee is that the caller explicitly
approved the selected assertions and that they pass against the supplied completed result.

The returned object is only the existing `RegressionSpec 0.1.0`. TraceForge does not add a second
promotion wrapper or copy runner, capsule, diff, analysis, or provenance data into the spec.

## Workbench workflow

After a replay completes technically, choose **Promote to regression**. No existing specification
is required, and a failed old `RegressionResult` does not block an intentional replacement. The
panel starts with no expectations selected. Add each JSON path, choose `equals` or `contains`, enter
the expected value as JSON, and confirm that the current capsule, replay output, and expectations
were reviewed. Artifact generation performs exact replay again on the server using the currently
submitted capsule and the startup-registered runner. Browser-supplied replay results, status,
comparison, diff, or analysis values are not promotion provenance.

Workbench offers one content-addressed ZIP download containing:

- `replay-capsule.json`, unchanged from the reviewed input;
- `regression-spec.json`, containing only explicitly selected expectations; and
- `test_traceforge_regression.py`, rendered by the same exporter used by the Python API and CLI.

These three entries use fixed, path-safe internal names and are rendered in one coherent server
operation. The ZIP filename includes a digest of its content, so a different specification or
runner produces a different advertised filename. Independent browser collision renaming can no
longer make the pytest file silently reference stale separately downloaded inputs.

The request cannot supply a runner import, output directory, server path, filename, archive entry,
or overwrite flag. Workbench constructs the bundle in memory and writes no server file.

For trusted local filesystem export, `export_pytest()` refuses an existing output by default.
Replacement requires an explicit `force=True` or CLI `--force` decision.

## Offline CI contract

The generated pytest loads a sealed capsule and separate specification, loads trusted project
runner code, and calls `replay_exact()`. Exact replay validates evidence, uses only recorded
dependencies, blocks common socket entry points, requires complete fixture consumption, and never
falls back to a live model, HTTP service, or tool. A failed approved assertion produces a non-zero
pytest exit.

After dependencies have been installed, the portable CI command is simply:

```sh
python -m pytest -q tests/regressions/test_traceforge_regression.py
```

A GitHub Actions job may use the same command as documentation-only provider configuration:

```yaml
jobs:
  replay-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: python -m pip install . pytest
      - run: python -m pytest -q tests/regressions/test_traceforge_regression.py
```

Dependency installation may have its own network policy; the generated regression execution makes
no live application dependency call. TraceForge adds no GitHub App, bot, status integration, or
provider-specific runtime behavior.

The startup-registered runner reference is embedded as a Python string literal. The project module
and callable must be installed and importable in the CI environment; the bundle is not universally
portable without that project code and its compatible TraceForge version.

## Controlled repaired-weather example

The repository test uses the sealed weather failure whose historical output is
`umbrella_needed = false`. Exact replay of the repaired runner produces `true` while
`deterministic_match` is false. The developer explicitly promotes only
`output.umbrella_needed == true`, exports pytest, and observes:

1. repaired runner: generated test passes;
2. locally changed runner returning `false`: generated test fails non-zero; and
3. restored repaired runner with a blocked live socket attempt: generated test passes again; and
4. a runner making a mismatched dependency request fails closed.

The same promotion succeeds with no prior regression specification, with a failed old expectation,
and while `deterministic_match` and `ExecutionDiff.matches` are false. All weather dependency
outcomes come from the sealed capsule. No live dependency is invoked.

## Limits

Promotion does not prove root cause, prevent future defects automatically, approve evidence,
authenticate the approving developer, mutate a capsule, create a regression-management system, or
provide hosted CI. The Python runner remains trusted local code with process authority; the socket
guard is not an operating-system sandbox.
