# Controlled Weather Exact Replay

This credential-free example keeps the original incorrect umbrella advice in `replay-capsule.json` as immutable evidence. The desired behaviour lives separately in `regression-spec.json`. Exact replay runs application formatting and umbrella reasoning again while the model, geocoding, and current-weather outcomes remain recorded.

From an environment with TraceForge installed:

```text
traceforge replay examples/weather/replay-capsule.json \
  --runner traceforge.examples.weather_agent:run \
  --spec examples/weather/regression-spec.json
```

The `--runner` target is trusted local Python code and executes with the current process's authority. The example uses reserved `.invalid` URLs only as request identities; exact replay performs no HTTP calls.
