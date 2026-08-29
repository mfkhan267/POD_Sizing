# Kubernetes Pod Capacity Planner v4

Python-served, zero-build static website.

## Run
python3 server.py

Then open http://localhost:8080

## Confirmed units
The supplied template uses:
- CPU: **millicores (mCPU)**. A unit-less `500` means 500m = 0.5 core.
- Memory: **MiB**. A unit-less `6144` means 6144 Mi.

## Confirmed sizing model
- Total Pod Cores = SUM(CPU Request × Replicas)
- Istio Cores = SUM(Istio sidecar CPU), deliberately NOT multiplied by replicas
- Scheduling CPU = SUM((CPU Request + Istio CPU) × Replicas)
- Scheduling Memory = SUM((Mem Request + Istio Mem) × Replicas)
- Worker nodes = MAX(CPU-driven nodes, Memory-driven nodes)
- Node profiles: 8/32, 16/64, 32/128 CPU/GiB
- 80% usable CPU and memory
- DEV + TEST + UAT + Pre-Prod share one worker pool
- Prod is separate and has at least one worker per AZ across 3 AZs
- New Cluster YES adds 3 control-plane nodes
- New Cluster NO adds no control-plane nodes
