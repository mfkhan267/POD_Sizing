# IBM Guardium — Vendor Clarification Questionnaire (Infra Architect's Checklist)

Purpose: a structured set of questions to eliminate ambiguity before design sign-off, contract, or PoC. Organized so each category maps to a section of the eventual Statement of Work / Architecture Decision Record — if the vendor can't answer a question crisply with a document reference or a number, treat it as an open risk, not a "we'll figure it out later."

---

## 1. Architecture & Component Model

1. For **our specific target state** (on-prem, VMware, OpenShift Virtualization, cloud-native DBs, hybrid), which exact component topology do you recommend — and why that one over the alternatives?
2. Is **Guardium Data Protection (appliance model)** or **Guardium Data Security Center / Insights (OpenShift/microservices model)** the right fit for us, or a hybrid of both? What's the concrete migration path between them if we start on one and need the other later?
3. What is the **end-of-life/end-of-support roadmap** for the appliance-based (Collector/Aggregator/CM) architecture vs. the direction of GDSC? Are we investing in a model IBM is deprecating?
4. For databases we run that are **not natively supported by S-TAP** (specific NoSQL, cloud-managed, legacy platforms), what is the actual supported monitoring mechanism — agent, agentless, native audit log ingestion — and what's the fidelity/latency trade-off versus S-TAP?
5. Can you provide the **as-built architecture diagrams and BOM** (bill of materials: appliance count, role, spec) for at least two reference customers of comparable scale to ours?
6. What exactly happens to **DB traffic and application behavior** if a Collector becomes unreachable while S-GATE blocking policies are active — fail-open or fail-closed, and is that configurable per policy or global?

## 2. Sizing, Performance & Capacity

7. What is the **current, version-specific Performance & Sizing Guide** (not a generic requirements doc) for the version you're proposing, and can we validate your proposed sizing against our actual TPS/DB-count/data-volume figures line by line?
8. What **assumptions** (policy complexity, logging granularity — full SQL text vs. metadata, masking/redaction load) went into the sizing you've proposed? Show the math, not just the final SKU count.
9. What is the **maximum sustained throughput (events/sec, MB/sec) per Collector** on the exact hardware/VM spec you're proposing, backed by a benchmark or reference deployment — not a marketing figure?
10. At what point does a Collector require **splitting/adding capacity** — is there a documented early-warning metric (CPU, queue depth, buffer usage) we should alarm on, and can it be surfaced to our monitoring stack?
11. What's the **actual Collector:Aggregator ratio** we should plan for given our data volume, versus the generic "1:8" heuristic — walk us through why.
12. How does **sizing change** if we later enable Guardium Insights/GDSC analytics, Outlier Detection, or Quick Search — do these require separate infrastructure or just more headroom on existing units?
13. What is the **actual, tested impact on source database performance** (latency, CPU overhead) from S-TAP at our expected peak TPS, and do you have overhead benchmarks per DB platform we use?
14. Since v12.2 supports **online disk resizing**, does this apply to our proposed configuration, or are there caveats (RAID type, virtualization platform) that still require a rebuild?

## 3. High Availability

15. Walk us through, **step by step**, exactly what happens (automated vs. manual, and how long each step takes) when: (a) a Collector fails, (b) an Aggregator fails, (c) the Central Manager fails. Don't summarize — give us the actual runbook.
16. Is there **any scenario with true active-active automatic failover** in the current version, or is all HA either infrastructure-assisted (hypervisor-level) or manual promotion? Be explicit about which components fall into which bucket.
17. For **CM backup promotion**, what is the actual sync interval, what data is and isn't synchronized, and what is the documented procedure and expected time-to-promote for our environment size?
18. What **patch-level parity requirements** exist between primary/backup CM or paired Collectors, and what breaks if they drift — and how do you prevent/detect that drift operationally?
19. How do **S-TAP failover configurations** behave under partial network partition (S-TAP can reach neither primary nor backup Collector) — does it queue, drop, or fail open/closed, and for how long can it buffer?
20. What's the **supported/tested hypervisor HA and live-migration behavior** for Guardium appliances on our specific platform (VMware DRS/vMotion, OpenShift Virtualization live migration) — any known issues with in-flight sniffer state during migration?

## 4. Disaster Recovery

21. What **RTO and RPO does Guardium itself guarantee or commonly achieve** in reference deployments of our scale — not the infra's RTO/RPO, but Guardium's own audit-continuity RTO/RPO?
22. What is the **fully documented DR runbook** — CM promotion, S-TAP re-pointing, archive-storage cutover, licensing activation at the DR site — and can we review an actual customer's runbook or a template?
23. Is **DR-site infrastructure** required to be always-on (warm standby) for support/licensing purposes, or can it legitimately be cold/pilot-light without breaching license terms? What are the exact standby-licensing terms?
24. What is the **maximum tested/supported network latency** between primary and DR sites for archive replication and CM sync, and what breaks past that threshold?
25. How do you **validate a DR test** without disrupting production monitoring — is there a supported "DR drill" mode, or does testing require actual cutover?
26. What's your **track record / reference architecture** for DR specifically for organizations with our regulatory retention requirements (name the regulation) — has this exact scenario been implemented before?

## 5. Data Redundancy, Retention & Storage

27. Where does **data legally/physically reside at each stage** (Collector, Aggregator, Archive, Guardium Insights) and can we map that explicitly to our data residency/sovereignty obligations?
28. What is the **archive file format, encryption scheme, and key management model** — who holds the keys, can we bring our own KMS/HSM, and what happens to old archives if the shared secret is lost or rotated?
29. Is archive storage **WORM/immutability-capable**, and if so, on which target storage platforms is that actually validated (not just theoretically compatible)?
30. What is the **guaranteed data integrity mechanism** across the Collector→Aggregator→Archive pipeline — how do we know an aggregation or archive job silently failed, and what alerting exists for that?
31. If we need **7+ year retention** for regulatory reasons, what's the recommended storage tier/architecture, and what are the cost and performance implications of restoring data from that far back?
32. What's the process and time-to-restore for **investigative/forensic access** to archived data — can it happen without disrupting live monitoring capacity, and does it require a dedicated investigation unit?
33. How does **Guardium Insights/Kafka storage** get sized, replicated, and backed up — is this entirely separate from appliance-level storage planning, and who owns that OpenShift storage class decision (us or the vendor)?

## 6. Security & Compliance

34. What is Guardium's own **security posture** — how is the appliance/OS hardened, what's the patch cadence for underlying RHEL/CVEs, and what's our obligation vs. the vendor's for OS-level patching?
35. How is **segregation of duties enforced** — can a DBA see/modify Guardium policies monitoring their own database, and can this be proven to an auditor?
36. What audit trail exists for **actions on Guardium itself** (who changed a policy, who accessed archived data, who promoted a CM) — is that trail itself tamper-evident and exportable?
37. Which **specific compliance frameworks** (PCI-DSS, SOX, HIPAA, GDPR, local regulator) does the proposed architecture map to out-of-the-box vs. requiring custom policy/report work — get this itemized, not a blanket "yes, compliant."
38. What's the **shared responsibility model** in writing — specifically, what does IBM/the SI guarantee versus what remains our operational responsibility for compliance evidence?

## 7. Integration & Interoperability

39. What's the **exact integration method and data fidelity** with our SIEM (name it) — real-time streaming, batch export, API pull — and what's the latency and any field/data loss in that integration?
40. For **cloud-native databases** (name your specific RDS/Aurora/Azure SQL/etc. footprint), is monitoring native-log-based or traffic-mirroring-based, and what are the known gaps versus on-prem S-TAP monitoring (e.g., missed local/privileged access)?
41. How does Guardium integrate with our **existing IAM/SSO, ticketing (ServiceNow), and backup/DR orchestration tooling** — API-based, agent-based, or manual?
42. Can policies, reports, and configuration be **managed as code** (API/Terraform/GitOps) for our DevSecOps pipeline, or is this UI-driven only?

## 8. Operations, Patching & Lifecycle

43. What is the **actual patch cadence** (major/minor/emergency), and what is the tested, documented **downtime/impact window** for patching a Collector, Aggregator, and CM respectively?
44. Can patches be applied **without interrupting active monitoring/blocking**, or is there always a service gap — and if so, how is that gap covered from a compliance-continuity standpoint?
45. What's the **rollback procedure** if a patch causes an issue in production, and what's the tested rollback time?
46. Who is responsible for **capacity monitoring and proactive scale-out triggers** post go-live — is this a managed service, or entirely on our team, and what tooling/dashboards do we get for it?
47. What does the **version upgrade path** look like over a 3–5 year horizon (major version jumps), and what has been the typical customer effort/downtime for past major upgrades (e.g., v10→v11→v12)?

## 9. Licensing & Commercial

48. What is the **exact licensing metric** for our proposed deployment (PVU, RVU, per-data-source, per-instance — confirm which, Guardium's model has varied) and how is it calculated for our specific mixed on-prem/cloud/virtualized estate?
49. Does **DR-standby infrastructure require separate/full licensing**, or is there a documented standby/passive-use licensing term — get this in writing, not verbally.
50. How does licensing change if we **add Guardium Insights/GDSC, additional DB platforms, or expand DB count** mid-term — is there a true-up mechanism, and what triggers an audit?
51. What's included in **standard support vs. requiring a separate Lab Services/Expert Labs engagement** — specifically for sizing validation, DR design review, and upgrade assistance?
52. What are the **support SLAs** (response time by severity) for a Sev-1 (Collector down, audit gap in progress) — and is this materially different for appliance vs. GDSC deployments?

## 10. Migration, Onboarding & Acceptance Criteria

53. If migrating from an existing DAM tool or older Guardium version, what's the **documented migration methodology**, expected effort, and what data/policies are or aren't portable?
54. What **acceptance test plan** do you propose to validate the solution meets our stated RTO/RPO, sizing, and compliance requirements before go-live sign-off — can this be jointly defined and written into the contract?
55. What does a **typical PoC/pilot scope** look like, and can it specifically include a simulated Collector/Aggregator/CM failure and DR failover, not just steady-state monitoring?
56. Who are **three reference customers** of comparable scale and industry we can speak to directly (not vendor-curated case studies) about their real-world HA/DR experience?

---

## How to Use This

- Turn each **"walk us through / show the math / get it in writing"** question into a mandatory RFP response field — a vague answer is itself the answer.
- Anything answered with "**it depends**" should be followed by "**depends on what — give us the decision matrix**."
- Route licensing (#48–52) and support-SLA questions to your procurement/vendor-management team in parallel — architects catch technical ambiguity, procurement catches commercial ambiguity, and Guardium's licensing model specifically has been a recurring source of scope disputes industry-wide, so don't let it be assumed rather than confirmed.
- Treat questions **15–26 (HA/DR)** as the highest-priority category to get in writing before design sign-off — this is where "the demo looked fine" most often diverges from "the runbook actually works at 3 AM."
