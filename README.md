# Kubernetes Cluster Capacity Planner — Zero Dependency Edition

## Run

No Python package, Node.js, npm, build step, or internet connection is required.

1. Put `server.py` and `index.html` in the same directory.
2. Run:

```bash
python3 server.py
```

3. Open `http://127.0.0.1:8000` in a browser.

The application performs all calculations in the browser. The Python file is only a standard-library static HTTP server.

## Sizing methodology

The planner intentionally follows Kubernetes' scheduling/resource-accounting model rather than treating VM CPU/RAM as fully consumable application capacity.

### 1. Workload capacity is request based

Kubernetes uses CPU and memory **requests** for scheduling. For each resource, the scheduler checks that the sum of requests on a node fits within the node's allocatable capacity. CPU/memory limits are enforced at runtime and are therefore retained for audit but are not used to calculate worker count.

### 2. Node Allocatable model

The worker-node model is:

`Node Capacity − systemReserved − kubeReserved − eviction reserve = Node Allocatable`

Then explicit node-level DaemonSet overhead is removed:

`Application Capacity/node = Node Allocatable − DaemonSet CPU/Memory overhead`

The planner applies the configured buffer to workload requests before dividing by per-node application capacity.

### 3. Pod density

Kubernetes also has a Pod-count ceiling. The planner evaluates:

- `maxPods` (default 110, matching the kubelet documentation default)
- optional `podsPerCore`
- DaemonSet Pods already occupying Pod slots
- optional Pod-density safety factor

The worker count for each environment is the maximum of CPU-based nodes, memory-based nodes, and Pod-density-based nodes.

### 4. Topology / production minimum

For Prod, the planner enforces:

`minimum worker nodes = Availability Zones × minimum Prod nodes per AZ`

This is a planning constraint, not a Kubernetes requirement by itself. Actual distribution depends on topology spread constraints, affinity/anti-affinity, node labels, taints and workload configuration.

### 5. Control plane

If `New Cluster = YES`, the planner adds the configured number of control-plane nodes. The default is 3 for an HA-oriented cluster. Control-plane node sizing is entered independently because application workload CSV requests do not describe API server/etcd/control-plane resource requirements.

## Kubernetes primary sources reviewed

- Resource Management for Pods and Containers:
  https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
- Reserve Compute Resources for System Daemons / Node Allocatable:
  https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/
- Node-pressure Eviction:
  https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/
- Kubelet configuration / maxPods and podsPerCore:
  https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/
- DaemonSet:
  https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/
- Local ephemeral storage:
  https://kubernetes.io/docs/concepts/storage/ephemeral-storage/
- Pod topology spread constraints:
  https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/
- Assigning Pods to Nodes:
  https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/
- Kubernetes kubeadm HA control-plane guidance:
  https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/

## Important limitation

No static calculator can produce a literally "perfect" node count from workload CSV alone. The target cluster's actual `Node.status.allocatable`, kube/system reservations, CNI/runtime overhead, DaemonSets, ephemeral-storage requirements, taints/tolerations, node selectors, affinity/anti-affinity, topology spread constraints, PodDisruptionBudgets, autoscaler policy and cloud-provider-specific node behavior can materially change the result.

For production accuracy, populate the reservation/DaemonSet fields from the target platform and validate the result against a representative `kubectl describe node` / `kubectl get nodes -o json` snapshot.

## CSV behavior

The expected columns are exactly:

`Microsevice Name, Namespace, Environment, CPU Request, Mem Request, CPU Limits, Mem Limits, Istio sidecar CPU, Istio sidecar Mem, Replicas`

The attached source CSV is accepted. The parser is deliberately tolerant of Kubernetes-style units. It also tolerates the source template's `8192Mim`-style typo in CPU limits by extracting the numeric CPU quantity. For the workload calculation, CPU request/sidecar CPU are interpreted as **millicores**, and memory request/sidecar memory as **Mi**.

The calculator uses the **Replica count** when multiplying each row's per-Pod resources.
