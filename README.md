# Kubernetes Capacity Planner — Python-served Zero-Build Version

## Run

Requires only Python 3:

```bash
cd k8s-capacity-planner-python-static
python3 server.py
```

Then open:

http://localhost:8080

Or use Python directly:

```bash
python3 -m http.server 8080
```

## Input

The application accepts the following columns:

- Microsevice Name
- Namespace
- Environment (DEV, TEST, UAT, Pre-Prod and Prod)
- CPU Request
- Mem Request
- CPU Limits
- Mem Limits
- Istio sidecar CPU
- Istio sidecar Mem
- Replicas

The browser implementation has zero external dependencies. CSV upload is fully supported.

For maximum compatibility with a pure zero-build/no-dependency browser application, save Excel workbooks as CSV before upload. XLSX files are detected and the UI explains this limitation rather than silently producing incorrect results.

## Capacity rules

- Total Pods = sum of replicas.
- Istio cores = Istio sidecar CPU request × replicas, converted from millicores to cores.
- Worker sizing considers application CPU request + Istio CPU request and memory request.
- Node CPU reserve defaults to 20%.
- DEV, TEST, UAT and Pre-Prod share workers.
- Prod is calculated separately and spread across 3 AZs.
- Prod has a configurable minimum of 1, 2 or 3 workers per AZ.
- New Cluster = YES adds 3 control-plane nodes.
- New Cluster = NO adds no control-plane nodes.
- Worker configurations: 8, 16 and 32 cores.

## Important

CPU/memory *limits* are displayed but are not used for node sizing. Requests are the appropriate baseline for Kubernetes capacity planning; this can be changed later if your sizing methodology requires limits, QoS, DaemonSets, kube/system reservations, pod-density limits, N+1, or other overhead.
