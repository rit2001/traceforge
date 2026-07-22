# RAG Citation Grounding

This offline case records an authoritative retrieval response while preserving an original, incorrectly cited 90-day claim. Exact replay reruns grounding logic, produces the supported 30-day answer, and evaluates a separate regression specification. No retrieval service is contacted.

Run with:

```console
traceforge replay examples/rag-citation/replay-capsule.json --runner traceforge.examples.rag_agent:run --spec examples/rag-citation/regression-spec.json
```
