# ADR-0005: Local Kubernetes Deployment on kind

- Status: Accepted
- Date: 2026-07-22

## Context

The verified Compose topology already packages the Go ingestion gateway and the shared Python
worker/API image and connects them to Apache Kafka and an OpenTelemetry Collector. The next
approved milestone is to prove that Kubernetes can schedule, connect, restart, configure, and
constrain those same containers on one local ARM64 kind cluster without changing capture, replay,
or evidence semantics.

This milestone is a deployment gate, not a reason to add a second gateway, worker, broker,
Collector, replay engine, or storage implementation. It also cannot substantiate cloud operation,
high availability, scale, or production security.

## Decision

TraceForge keeps native Kubernetes manifests under `deploy/kubernetes`, with a reusable Kustomize
base and a `kind` local overlay. The dedicated local cluster and namespace are both named
`traceforge`. Application images are built from the existing Dockerfiles, explicitly tagged
`0.3.0-local`, built for Linux ARM64, loaded into kind, and use `imagePullPolicy: Never`.

The local topology contains the existing Go gateway, one Apache Kafka development broker, one
Python capsule worker, the Python API/dashboard, and the OpenTelemetry Collector. Kafka and the
Collector are labelled as local-development infrastructure. ClusterIP or headless Services exist
only for in-cluster communication. Host access uses `kubectl port-forward`; no LoadBalancer or
Ingress is included.

Non-sensitive configuration is generated as ConfigMaps. No Kubernetes Secret is created because
this local controlled topology requires no credentials. Application containers run as UID/GID
10001 with privilege escalation disabled, all Linux capabilities dropped, RuntimeDefault seccomp,
and a read-only root filesystem. Kafka uses its supported non-root UID/GID 1000. Each workload has
requests, limits, graceful termination, and probes backed by an endpoint or broker command that it
actually supports.

One `ReadWriteOnce` PVC holds worker SQLite assembly state, sealed capsules, API replay history,
and the Collector's bounded local trace file in separate paths. The worker is fixed at one replica
with `Recreate` strategy. SQLite remains a single-writer local store; Kubernetes does not turn it
into distributed or highly available storage. Kafka data is ephemeral in this local gate.

Small scripts and Make targets own cluster creation, image build/load, Kustomize application,
rollout waiting, smoke/recovery verification, and deletion. Every Kubernetes command uses the
explicit `kind-traceforge` context and `traceforge` namespace, and teardown deletes only the exact
`traceforge` kind cluster.

## Consequences

- Docker continues to package and run individual containers. Kubernetes adds local scheduling,
  restart, service discovery, configuration, resource constraints, probes, and PVC attachment.
- A real kind deployment can verify the existing distributed path without creating alternative
  service implementations or changing Replay Capsule semantics.
- Deleting the dedicated kind cluster deletes its local PVC and all local verification state.
- Sharing one claim is suitable only for this single-node local topology. The API and Collector do
  not write the worker's SQLite assembly database.
- Worker readiness proves that its metrics server/process is available, not that Kafka consumption
  is progressing; the end-to-end smoke is the stronger bounded check.
- kind evidence proves a local Kubernetes deployment only. It does not prove cloud production
  readiness, high availability, scale, durability objectives, authentication, TLS, or security.
- Terraform, Helm, operators, cloud resources, authentication, TLS, autoscaling, and production
  infrastructure remain outside this decision.

## Alternatives Considered

### Helm

Rejected for this gate. Native manifests plus Kustomize are sufficient for one base and one local
overlay and avoid adding packaging machinery before another deployment target exists.

### Separate Persistent Stores or Distributed SQLite Replacement

Rejected. The measured gate requires persistence across pod replacement, not a new database or a
high-availability storage design. Replacing SQLite would change an existing service boundary.

### LoadBalancer, Ingress, or Host-Port Exposure

Rejected. Loopback `kubectl port-forward` is explicit and adequate for local verification, while
avoiding a public exposure or an ingress implementation that this milestone does not require.
