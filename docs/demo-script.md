# Two-Minute Portfolio Demo

## 0:00–0:20 — Problem

“This controlled weather agent completed successfully but gave incorrect umbrella advice. TraceForge preserves that failure as immutable evidence instead of relying on a live API to reproduce it.” Show `examples/weather/replay-capsule.json` and the separate regression specification.

## 0:20–0:50 — Validate and replay

Run:

```text
traceforge validate examples/weather/replay-capsule.json
traceforge replay examples/weather/replay-capsule.json --runner traceforge.examples.weather_agent:run --spec examples/weather/regression-spec.json
```

Point out the recorded model/geocoding/weather dependency sequence, original incorrect output, fresh corrected output, deterministic comparison, and passing behavioural assertions.

## 0:50–1:15 — Export

Run `traceforge export-pytest ... --output /tmp/test_weather.py`, then `pytest /tmp/test_weather.py`. Explain that the generated test retains references to developer-approved artifacts and remains offline.

## 1:15–1:45 — Dashboard

Run `traceforge serve`, upload the controlled capsule and spec, select `controlled-weather`, and replay. Show the timeline, observations, assertions, and SQLite history. Mention that web runners are allow-listed.

## 1:45–2:00 — Boundaries

“This is an experimental MVP: best-effort redaction is not a proof of safety, the network guard is process-wide, dynamic CLI runners are trusted code, and automatic fixing is not guaranteed. Framework, storage, authentication, publishing, and deployment remain separate extension seams.”
