# Tool Argument Safety

This offline case records one sanitized refund request and response. Exact replay permits only that request identity. Changing the amount or customer makes replay fail closed with `DependencyMismatchError`; it never contacts a payment system and does not attempt an automatic repair.

Run with:

```console
traceforge replay examples/tool-argument-safety/replay-capsule.json --runner traceforge.examples.tool_safety_agent:run --spec examples/tool-argument-safety/regression-spec.json
```
