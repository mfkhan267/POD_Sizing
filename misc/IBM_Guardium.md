# IBM Guardium — Functional Overview, Capacity Planning & HA/DR Architecture

---

## 1. What Guardium Is and How It Functions

IBM Guardium (Data Protection / GDP, evolving toward **Guardium Data Security Center — GDSC**) is a unified Database Activity Monitoring (DAM), vulnerability assessment, and data-security/compliance-automation platform. It works on a **distributed collector–agent model**:

### Core components

| Component | Role |
|---|---|
| **S-TAP (Software Tap)** | Lightweight agent installed on (or near) the DB server / OS. Captures network traffic, local traffic (bequeath connections, shared memory), and OS-level activity, then streams it to a Collector. Non-agent options exist too: **STAP-less / Universal Connector**, **cloud-native DAM** (RDS/Aurora, Azure SQL, etc. via VPC mirroring or native audit logs), **Guardium External S-TAP (GEST)** for gateway/z/OS. |
| **Collector** | The workhorse appliance. Receives raw traffic from S-TAPs, runs it through the **K-TAP/Inspection Engine and Sniffer** process, parses SQL, applies **policies** in real time (alert, block, redact, mask, log-only), stores parsed data in its internal datamart (MySQL-based), and generates reports. |
| **Aggregator** | Collects/merges data from multiple Collectors (and optionally other Aggregators) via scheduled **aggregation jobs**, purging Collector-local data after successful aggregation. Provides enterprise-wide reporting, larger retention, and lighter query load on Collectors. Does **not** do live traffic inspection. |
| **Central Manager (CM)** | A management-plane role (can be run on an Aggregator or standalone) providing single-pane administration: policy push, patch distribution (via GIM), user/role management, unit groups, and federated reporting when paired with Aggregators. |
| **GIM (Guardium Installation Manager)** | Agent/patch lifecycle manager — pushes S-TAP installs/upgrades and appliance patches centrally. |
| **Guardium Insights / GDSC** | Newer analytics/microservices layer running on **Red Hat OpenShift**, ingesting data from Collectors (via Kafka) at scale for long-term retention, ML-based anomaly detection, and unified dashboards across on-prem and cloud — effectively decoupling "long-term analytics/storage" from the appliance datamart model. |

### Data flow (typical enterprise pattern)
```
DB Servers (S-TAP / STAP-less) 
        │  (encrypted traffic, policy-filtered)
        ▼
   Collector(s)  ── real-time policy engine, alerting, blocking, local datamart (short retention)
        │  (scheduled aggregation)
        ▼
   Aggregator(s) ── merged, longer-retention reporting datamart
        │  (federated queries / patch & policy push)
        ▼
  Central Manager ── single console, enterprise policy & patch distribution
        │  (optional, at scale)
        ▼
Guardium Insights/GDSC (OpenShift, Kafka) ── long-term analytics, ML, cross-environment correlation
```

### Deployment topology patterns
- **Basic standalone**: 1 Collector + several S-TAPs, one data center.
- **Mid-size**: Multiple Collectors per data center → 1 Aggregator (also often the CM).
- **Enterprise/federated**: Many Collectors → regional Aggregators → CM (federated) → optionally Guardium Insights for cross-region analytics and SIEM (QRadar/Splunk) integration.
- IBM's standard sizing rule of thumb: **1 Aggregator for every ~8 Collectors** (adjust based on data volume, not just count).

---

## 2. Capacity Planning

Capacity planning for Guardium spans three lenses — **Compute, Storage, and Datastore (data lifecycle/retention)**. Below is IBM's current published guidance (v12.2) plus the sizing logic an architect applies on top of it.

### A. Compute (CPU / RAM / Network)

| Resource | Minimum | Recommended | High-load (Exadata/Teradata/SuperCluster/Kafka nodes) |
|---|---|---|---|
| CPU (physical or vCPU) | 4 cores | 8 cores | 24 cores (Kafka brokers: 8 vCPU, 4 core × 2 socket) |
| RAM | 24 GB | 32 GB | 64 GB (Analytics/Quick Search, large federated CM); Kafka broker: 64 GB RAM + 32 GB swap. **Diminishing returns above ~96 GB — don't over-allocate.** |
| NICs | 1 port | 1–4 ports, 1/10 Gbit | 10 Gbit for high-throughput inspection or SPAN/TAP-based capture |

**Compute sizing drivers an architect should model:**
1. **Sustained transactions/sec (TPS) and peak concurrency** per monitored DB — not just DB count. A collector sized for 10 low-traffic DBs may choke on 2 high-TPS OLTP systems.
2. **Number of S-TAPs / Inspection Engines per Collector** — IBM's own sizing tables (per DB platform/PVU) should be pulled from the current *Guardium Performance & Sizing Guide* for the target version; disk speed materially changes this ratio (7,200 RPM disks → cut S-TAP-to-Collector ratio by ~70%).
3. **Policy complexity** (number of rules, regex-heavy rules, real-time masking/blocking vs. log-only) — CPU-bound, scales non-linearly with rule count.
4. **Analytics workloads** (Outlier Detection, Quick Search, Guardium Insights ML) — memory- and I/O-intensive; budget extra headroom.
5. **Central Manager span-of-control** — a CM managing 50+ units in a federated environment needs the 64 GB tier regardless of its own traffic load.

### B. Storage (Disk/IOPS)

| Resource | Minimum | Recommended | Notes |
|---|---|---|---|
| Disk size | 300 GB | Collector: 300–600 GB; Aggregator: 600–1000 GB (larger via >2 TB EFI/GPT support since 10.1.2) | RAID-10 recommended (also 0, 1, 0+1, 1+0 supported); ≥25 GB free on `/var` mandatory |
| Disk speed | 7,200–15,000 RPM | 10K–15K RPM / NVMe for high-load | NVMe standard on newer appliance SKUs (x3364n) |
| Reference hardware (v12.2 shipped SKU) | — | Collector: 2.4 TB (4×1.2TB SAS RAID10) or 3.84 TB NVMe RAID1; Aggregator: 4.8 TB (8×1.2TB SAS) or 7.68 TB NVMe RAID10 | — |

**Storage sizing drivers:**
1. **Average daily audit-record volume** (bytes/day, driven by TPS × avg SQL size × logging granularity — full SQL text + values vs. metadata-only).
2. **Local retention window on Collector** before purge (short — days, since aggregation offloads it) vs. **retention on Aggregator** (weeks–months per compliance mandate, e.g., PCI-DSS 12 months, SOX 7 years — usually pushed further out to archive, not kept live on the Aggregator disk).
3. **IOPS headroom** for concurrent report generation + real-time sniffer writes — undersized IOPS is the most common root cause of Guardium performance complaints, not raw capacity.
4. **Growth curve**: plan for 12–18 months of DB estate growth, not just current state; disk resize was historically disruptive (rebuild required) — **Guardium 12.2 added online disk-resizing support for Collectors/Aggregators**, which materially reduces this risk for new builds.

### C. Datastore / Data Lifecycle perspective

This is the "logical" capacity dimension — how data moves and where it lives long-term, independent of any one appliance's disk:

1. **Collector datamart**: short-lived, operational (real-time alerting, near-term investigation). Purge policy tied to aggregation schedule.
2. **Aggregation**: scheduled job merges N Collectors → 1 Aggregator; **1:8 ratio** is the IBM starting heuristic, refined by actual daily GB/collector.
3. **Archive**: encrypted archive files (system-shared-secret protected) pushed to external storage (SAN/NFS/object storage) for long-term compliance retention — this is where multi-year retention actually lives, not on live appliance disk.
4. **Restore**: on-demand rehydration of archived data into a Collector, Aggregator, or a dedicated **investigation unit** (a Collector outside the aggregation cluster, so restore/investigation doesn't compete with live monitoring capacity).
5. **Datamart export / Guardium Insights (Kafka)**: for enterprises needing SIEM correlation, BI, or ML-driven analytics at scale, data is streamed via Kafka into Guardium Insights/GDSC (OpenShift-hosted), which has its **own separate storage sizing model** (persistent volumes on OpenShift storage classes — plan this as a distinct capacity track, not an extension of appliance disk).

**Practical capacity-planning workflow:**
```
1. Inventory DBs → TPS, criticality, platform, regulatory scope
2. Estimate daily audit volume (GB/day) per DB → sum per Collector
3. Size Collector CPU/RAM/disk against volume + policy complexity
4. Derive Collector:Aggregator ratio from actual GB/day, not just count
5. Define retention tiers: Collector (days) → Aggregator (months) → Archive (years)
6. If SIEM/ML/cross-cloud correlation is required → size Guardium Insights/GDSC separately
7. Add 30–40% headroom for growth + burst (audits, incident investigations spike volume)
```

---

## 3. Architect's Approach: From Business Requirements to HA/DR Architecture

### Step 1 — Brainstorming the Business Requirements

As an architect, before touching sizing tables, extract requirements across these dimensions (a structured discovery, typically via workshops with Security, DBA, Infra, and Compliance stakeholders):

- **Regulatory/compliance drivers**: PCI-DSS, SOX, GDPR, HIPAA, RBI/local regulator mandates — these dictate *minimum retention*, *audit immutability*, *segregation of duties* (Guardium admin ≠ DBA), and often *DR obligations* explicitly.
- **Data estate scope**: which DB platforms (Oracle, SQL Server, DB2, Teradata, Mongo, cloud-native RDS/Aurora/Azure SQL, Hadoop/big data), on-prem vs. multi-cloud, number of instances, criticality tiers (Tier-0 core banking vs. Tier-2 reporting DB).
- **Availability expectations**: what RTO/RPO does the *business* (not just Guardium) tolerate for audit visibility? Note — Guardium being briefly unavailable typically does **not** stop the monitored DB (fail-open by design in most deployments), but it does create an audit gap that itself may be a compliance violation — this reframes "HA for Guardium" as a **compliance-continuity requirement**, not just an uptime SLA.
- **Blocking vs. monitor-only policies**: if any policies are configured to actively block/quarantine traffic (S-GATE), Guardium becomes inline and its own availability directly impacts DB availability — a materially different HA bar than passive monitoring.
- **Geographic footprint**: single DC, multi-DC active/active, multi-region, cloud/hybrid — drives whether DR is same-region failover or cross-region.
- **Growth & change velocity**: M&A activity, cloud migration roadmap, planned DB estate growth — sizing must not be a snapshot.
- **Integration requirements**: SIEM (QRadar/Splunk), ticketing (ServiceNow), IAM, existing backup/DR tooling, existing HA orchestration (VMware HA/DRS, OpenShift, Kubernetes) the org already operates — reuse over reinvention.
- **Operational model**: centralized security team vs. federated per-BU ownership → drives CM topology (single global CM vs. regional CMs).

### Step 2 — Translating Requirements into Architecture Principles

From the above, derive explicit design principles, e.g.:
- "Audit-data loss is unacceptable beyond X hours" → drives **aggregation frequency + archive frequency**, not just appliance HA.
- "Zero single point of failure for blocking policies" → drives **Collector-pair HA with S-TAP failover configuration** (S-TAPs can be configured with primary/backup Collector IPs).
- "7-year retention, immutable" → drives **WORM/object-storage-backed archive**, not reliance on Aggregator local disk.
- "DR site must resume monitoring within 4 hours" → drives **standby Collector/Aggregator/CM at DR site, pre-provisioned and patch-synced**, plus **archive replication to DR storage**.

### Step 3 — Architecting for HA, Data Redundancy, and DR

Guardium's own HA/DR model is different from typical clustered apps — there's **no native active-active clustering or automatic failover at the appliance level** for Collectors/Aggregators/CM. HA/DR is achieved by combining Guardium-native mechanisms with infrastructure-level redundancy:

#### (a) High Availability (component-level, same-site)

| Layer | Mechanism |
|---|---|
| **S-TAP → Collector** | Configure each S-TAP with a **primary and failover Collector IP**; on primary loss, S-TAP redirects traffic to the failover Collector (manual or scripted promotion required on the Guardium side to make the failover collector authoritative). |
| **Collector redundancy** | Deploy **Collector pairs** per monitored zone/segment (N+1 or N+N) so a single appliance failure doesn't blind that segment; balance DB estate across pairs so no single Collector is a capacity SPOF. |
| **Central Manager HA** | Configure a **CM Backup unit**: CM state (policies, users, patches, unit groups) syncs to the backup CM on a schedule (commonly ~30 min). **This is not automatic failover** — an admin must manually promote the backup CM (`grdapi backup_cm_set` / UI promote) if the primary CM fails. Both CM primary and backup must be kept on **identical patch levels** for promotion to succeed cleanly. |
| **Aggregator resilience** | Multiple Aggregators per region so no single Aggregator loss blocks enterprise reporting; pair with archive-based recovery for data (see below). |
| **Infrastructure-level HA** | Since Guardium supports virtualization (VMware, OpenShift Virtualization, Hyper-V, Nutanix AHV), layer standard **VM-level HA** (vSphere HA/DRS, live migration, anti-affinity rules across hosts/racks) under the appliances for infra-level fault tolerance — this covers host/hypervisor failures that Guardium's own app-layer mechanisms don't. |
| **Network path redundancy** | Dual NICs/teamed interfaces (as supported: 1–4 ports with optional failover IP teaming) to avoid a network-card SPOF, especially where S-GATE blocking is in use. |

#### (b) Data Redundancy

- **Aggregation as redundancy**: once data aggregates from Collector → Aggregator, it exists in two places until the Collector purges it — design purge timing with a safety buffer so a Collector failure right after a missed aggregation cycle doesn't lose data.
- **Archive replication**: archive files (encrypted, shared-secret protected) should land on **resilient external storage** — SAN/NAS with its own RAID/replication, or object storage with versioning/immutability (WORM) for compliance-grade durability — not solely on appliance local disk.
- **Cross-site archive copy**: replicate archive storage to the DR site/region (storage-array replication, object storage cross-region replication, or scheduled secure copy) so archived audit history survives a site loss.
- **System backups**: schedule Guardium's built-in **monthly (or more frequent) system configuration backups** (policies, users, reports, unit config) separately from data archive — needed to rebuild an appliance's *configuration*, not just its data.
- **Guardium Insights/Kafka tier**: if in use, apply standard Kafka replication factor (≥3) and OpenShift persistent-volume replication/backup for the analytics tier, as this is architecturally decoupled from appliance-level redundancy.

#### (c) Disaster Recovery (site/region-level)

1. **DR topology choice**, driven by RTO/RPO derived in Step 1:
   - **Warm standby**: pre-built, patched (identical patch level) Collectors/Aggregators/CM at the DR site, powered on but not actively ingesting, with archive replication feeding them; on invocation, redirect S-TAPs (update primary/failover Collector config) and promote DR CM.
   - **Cold/pilot-light**: DR-site appliances exist as VM templates/images ready to deploy, storage replication keeps archive current; longer RTO but lower standing cost — suitable where audit-gap tolerance is a few hours to a day.
   - **Active/active across regions** (larger enterprises): independent regional Collector/Aggregator stacks per region reporting to a common or federated CM/Guardium Insights layer — DR here is more about the *analytics/CM plane* than duplicating every regional collector, since regional collectors are already distributed.
2. **S-TAP re-pointing**: DR runbook must include how S-TAPs at the affected site are redirected to DR Collectors (config push via GIM once DR CM is promoted, or pre-configured failover IPs if DR collectors are already known endpoints).
3. **CM promotion runbook**: since CM failover is **manual**, DR plans must explicitly script/document: verify patch parity, promote CM backup, validate unit group membership, re-establish trust (shared secrets/certificates) with Collectors/Aggregators at or reachable from the DR site.
4. **Data continuity validation**: post-failover, confirm aggregation jobs resume, archive jobs point to replicated storage, and no audit gap exists beyond the agreed RPO — treat this as a compliance control, not just an IT recovery check.
5. **Regular DR testing**: because CM/aggregator promotion is manual and version-sensitive (patch mismatches are a common failure mode), schedule periodic failover drills — this is the single highest-risk area in Guardium DR based on real-world incident patterns.
6. **Licensing/PVU consideration**: confirm DR-site appliances are licensed appropriately (standby licensing terms vary — validate with IBM account team) so DR capacity isn't discovered to be a licensing gap during an actual failover.

### Step 4 — Reference Architecture Summary (Enterprise, Multi-Site)

```
                 ┌─────────────────────────┐        ┌─────────────────────────┐
                 │   Primary Data Center    │        │        DR Site         │
                 │                          │        │                        │
DB Servers ──►   │  Collector Pairs (N+1)   │  ────► │  Standby Collector Pairs│
 (S-TAP,         │  per DB segment          │ archive│  (warm/pilot-light,     │
 primary +       │        │                 │ repl.  │   patch-synced)        │
 failover IP)    │        ▼                 │───────►│        │               │
                 │  Regional Aggregator(s)  │        │  Standby Aggregator     │
                 │        │                 │        │        │               │
                 │        ▼                 │        │        ▼               │
                 │  Central Manager (Primary)│◄──sync─┤  CM Backup (manual     │
                 │        │                 │ (~30min)│   promotion on DR)    │
                 │        ▼                 │        └─────────────────────────┘
                 │  Guardium Insights/GDSC   │
                 │  (OpenShift, Kafka repl.  │
                 │   factor ≥3, SIEM feed)   │
                 └─────────────────────────┘
                          │
                          ▼
              Encrypted Archive → Resilient/WORM storage
              → Cross-site/cross-region replicated copy
```

---

## Key Takeaways for the Architect

- **Compute/Storage sizing is not just "per collector" — it's per Collector *and* per Aggregator, weighted by actual GB/day, not raw DB count.**
- **Guardium 12.2's online disk-resize capability removes a historically painful rebuild-to-resize constraint** — factor this into whether you provision generously up front or plan for iterative growth.
- **HA is mostly infrastructure-assisted (VM/hypervisor HA) plus Guardium's own failover-IP and CM-backup mechanisms — not native active-active clustering.** Design accordingly and don't assume "HA" means "automatic."
- **CM/backup CM promotion is a manual, patch-sensitive operation** — this is the most common real-world DR failure point; invest in runbook discipline and regular drills.
- **Data redundancy and long-term retention live in the archive tier, not on live appliance disks** — architect the archive storage (replication, immutability) as seriously as the appliances themselves, since it's what actually satisfies multi-year compliance retention.
- **If blocking policies (S-GATE) are used, Guardium becomes inline infrastructure** — its HA bar rises to match the protected database's own availability requirements.

*Sources: IBM Guardium Appliance Technical Requirements (v12.2, Oct 2025), IBM Guardium Data Protection documentation (components/topology, data management), IBM community discussions on CM HA behavior, and IBM Guardium 12.2 architecture write-ups. For definitive, deployment-specific sizing, validate against the current IBM Guardium Performance & Sizing Guide for your target version and engage IBM Lab Services/your IBM account team for the licensing and DR-standby terms.*
