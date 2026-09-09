# ADManager Plus, ADAudit Plus & M365 Manager Plus
## Functional Overview, Capacity Planning, HA Verification & HA/DR Deployment Architecture

*Compiled from ManageEngine official documentation, September 2026*

---

## 1. Executive Summary

| Product | Purpose | Core Engine | Bundled DB | Bundled Search/Index | HA (native) |
|---|---|---|---|---|---|
| **ADManager Plus** | AD/Exchange/M365/Google Workspace **provisioning, management & reporting** | Tomcat + Java app server | PostgreSQL (default) / MS SQL | Elasticsearch (for clustering/reporting at scale) | ✅ Yes — Primary/Standby + Virtual IP |
| **ADAudit Plus** | Real-time **AD, Entra ID, file server & workstation auditing**, UEBA, threat detection, AD backup | Tomcat + Java app server | PostgreSQL (default) / MS SQL | DataEngine (Lucene) + built-in Elasticsearch | ✅ Yes — Hot Standby (Primary/Standby) |
| **M365 Manager Plus** | Microsoft 365 **management, reporting, auditing, alerting** (Exchange Online, Entra ID, Teams, OneDrive, SharePoint Online) | Tomcat + Java app server, PowerShell/Graph API driven | PostgreSQL (default) / MS SQL / Azure SQL | Elasticsearch | ⚠️ **Discontinued** as a standalone feature (builds ≥4324); HA is otherwise only available when bundled inside AD360, and current AD360 documentation is inconsistent on whether it is still covered — treat as **not reliably supported** and mitigate via VM-level HA/DR instead |

All three products are **Windows-only, single-tenant-per-instance, client-server web applications** — there is no cloud-SaaS or multi-node "cluster" mode in the sense of a scale-out application tier. Scaling is handled by increasing the size of a single instance (vertical scaling) and/or running a passive standby node (HA) plus agents/collectors for data gathering.

---

## 2. How Each Product Functions

### 2.1 ADManager Plus — Architecture

- **Deployment model:** Installed on a Windows Server/VM joined to (or with line-of-sight to) the target domain(s). On first run it auto-discovers AD domains; more can be added manually.
- **Client-server model:** Built-in Tomcat web server serves the console over HTTP/HTTPS (8080/8443). All configuration, delegation, workflows, and report definitions live in the bundled **PostgreSQL** (or MS SQL) database.
- **Management operations:** User/group/computer provisioning, GPO, password resets, and Exchange mailbox actions are executed **directly against Domain Controllers** using native Windows APIs / LDAP / PowerShell — not queued or brokered.
- **Reporting engine:** Report requests from the web client are translated into directory queries or API calls at run time; results are normalized and written back into the product database (not a permanent data warehouse — it's largely computed on demand, with support for scheduled snapshots).
- **Cloud/SaaS integration:** Microsoft 365 and Google Workspace actions/reports go through **Microsoft Graph API / Entra PowerShell** and **Google Workspace Admin API** respectively, over HTTPS, with results written back for auditability.
- **Backup & Recovery add-on:** Optional module that performs AD/Entra ID/Exchange Online/SharePoint Online backups; ships its own disk-space and RAM profile (see §3).
- **Integrations:** REST APIs for ITSM/help desk (ticket-triggered provisioning with RBAC validation), SIEM export of management/audit events (token or certificate-based), and direct DB connectors to external systems (MS SQL/Oracle) for identity synchronization.

### 2.2 ADAudit Plus — Architecture

- **Purpose-built for continuous change auditing and threat detection**, not transactional management.
- **Data collection — dual mode:**
  - **Agentless** (default): The server pulls Windows Security Event Log data from DCs, member servers, and file servers via **WMI/RPC**, and syncs AD objects via **LDAP/Global Catalog**. Real-time for DCs by default.
  - **Agent-based** (recommended for WAN, multi-forest, or >1,000 endpoints): A lightweight agent installed on DCs/member servers/workstations pushes events to the server over **HTTPS (port 8555)**, using the server's **FQDN** — never an IP — so agents auto-reconnect after any failover/DR event. Agents locally cache ~2GB of events during outages and flush on reconnect.
- **Processing pipeline:** Event Processing Engine → parses/normalizes/enriches raw events → **Analysis Engine** applies correlation rules for threat detection (Kerberoasting, DCSync, pass-the-hash/ticket, LDAP recon) and the **Attack Surface Analyzer** benchmarks configuration against CIS/NIST.
- **Storage layers (three distinct stores — important for capacity planning):**
  1. **Embedded PostgreSQL** (or MS SQL) — configuration, audit records, reporting metadata.
  2. **DataEngine (Lucene-based)** — indexes high-volume audit logs for fast search/reporting.
  3. **Built-in Elasticsearch** — stores AD/Entra ID object *snapshots* for the AD Backup & Recovery / comparison features.
- **UEBA:** Builds per-user/per-entity behavioral baselines and flags anomalies (odd-hour logons, geo-anomalies, etc.).

### 2.3 M365 Manager Plus — Architecture

- **Purely a Microsoft 365 tenant management/reporting/auditing tool** — no on-prem AD dependency (though it typically co-resides with an AD-joined estate).
- **Connectivity:** Uses **Microsoft Graph API**, legacy **Exchange Online PowerShell**, and (for a small number of MFA-related actions not yet exposed via Graph) the **MSOnline PowerShell module** — all over HTTPS/OAuth to Microsoft 365 endpoints.
- **Data flow:** Admin configures the M365 tenant(s) → product polls/collects data on the enabled schedule → normalizes and stores it in the bundled **PostgreSQL** (or external MS SQL/Azure SQL) database → **Elasticsearch** is layered in for fast search across audit and mailbox-content-search data.
- **Backup module:** Optional Exchange Online mailbox backup; compresses to roughly ⅓ of source size, so disk sizing must track total mailbox size, not just event volume.
- **Web tier:** Tomcat-based console on ports 80/443 (HTTP/HTTPS).

---

## 3. Capacity Planning — Compute, Storage & Datastore

### 3.1 ADManager Plus

**Base hardware (installer minimums vs. recommended):**

| Hardware | Minimum (Physical) | Minimum (VM) | Recommended (Physical) | Recommended (VM) |
|---|---|---|---|---|
| RAM | 4 GB | 6 GB | 6 GB | 8 GB |
| Disk | 5 GB | 5 GB | 50 GB | 50 GB |
| CPU speed | 2.1 GHz+ | 2.1 GHz+ | 2.4 GHz+ | 2.4 GHz+ |
| Cores | 2 | 4 vCPU | 4 | 6 vCPU |

**Scale by AD-object volume (drives RAM/disk/bandwidth — use whichever of the two tables below is larger for your environment):**

*Management workload (objects created/modified per hour):*

| Objects/hr | RAM | HDD | Bandwidth |
|---|---|---|---|
| 1,000 | 256 MB | 4 GB | 10 Mbps |
| 5,000 | 512 MB | 8 GB | 10 Mbps |
| 10,000 | 1,024 MB | 30 GB | 10 Mbps |
| 20,000 | 2,048 MB | 50 GB | 50 Mbps |
| 50,000 | 4,096 MB | 50 GB | 50 Mbps |
| 100,000 | 8,192 MB | 50 GB | 50 Mbps |

*Reporting workload (objects in domain — same scaling curve applies to on-demand + scheduled + automation-driven reports):* identical table shape to above.

**Backup & Recovery add-on (adds on top of base):**

| Domain objects | RAM (add-on only) | Disk (1 yr retention) | Bandwidth |
|---|---|---|---|
| 0–100,000 | 3 GB | 50 GB | 50 Mbps |
| 200,000 | 4 GB | 100 GB | 50 Mbps |
| 500,000 | 6 GB | 150 GB | 100 Mbps |
| 1,000,000 | 8 GB | 250 GB | 100 Mbps |

Google Workspace backup disk = 1:1 with total mailbox+drive size (plan for full backup size + incrementals + retention headroom).

**Datastore:** Bundled **PostgreSQL** (default) or **MS SQL 2014–2022**. DB listens on local TCP 33306. Elasticsearch is used internally for large-scale reporting/clustering (ports 9280 HTTP, 9380 inter-node TCP) — factor in extra RAM/disk headroom if you enable the load-balancing/clustering feature (contact ManageEngine support to size this — it isn't in the public calculator).

### 3.2 ADAudit Plus

**Base hardware:**

| Hardware | Minimum | Recommended | With AD Backup & Recovery (100k users) |
|---|---|---|---|
| CPU | 2.4 GHz | 3 GHz | 3 GHz |
| Cores | 4 | 8 | 8 |
| RAM | 8 GB | 16 GB | 16 GB |
| Disk | 50 GB | 100 GB | 200 GB |

ManageEngine's own "best performance" guidance and DR-planning documentation recommend going well beyond the published minimums for real production estates:

| Environment size | CPU | RAM |
|---|---|---|
| ≤ 1,000 audited devices | 16 cores/32 threads @ ≥3.0 GHz | 32 GB |
| > 1,000 audited devices | 32 cores/64 threads @ ≥3.0 GHz | 64 GB |

**Storage/datastore sizing methodology (evidence-based, not a fixed table):**
1. Run for ~30 days at normal workload.
2. Check **Admin → Disk Space Analysis** for the daily/monthly growth graph.
3. `Required storage = (avg. daily DB growth × retention days) × 1.3–1.4` (30–40% headroom for indexing/maintenance/spikes).
   *Example: 12 GB/day × 90-day retention = 1,080 GB → ~1.5 TB recommended with headroom.*

**Three separate datastores to size independently:**

| Store | Technology | Contents | Grows with |
|---|---|---|---|
| Embedded PostgreSQL (or MS SQL) | PostgreSQL / SQL Server | Config, audit records, reporting metadata | Object/event volume, retention |
| DataEngine | Lucene index | Indexed audit logs (fast search) | Event volume, retention |
| Built-in Elasticsearch | Elasticsearch | AD/Entra ID snapshots (backup/compare) | # of objects backed up, snapshot frequency |

**Operational rules:** install on a non-OS drive (D:/E:), and do **not** co-host other ManageEngine products on the same server — it's explicitly documented as resource-intensive and sensitive to contention.

### 3.3 M365 Manager Plus

| Hardware | Minimum | Recommended |
|---|---|---|
| CPU | 2.4 GHz | 3 GHz |
| Cores | 4 | 6+ |
| RAM | 8 GB | 16 GB |
| Disk | 200 GB (SSD preferred) | 500 GB (SSD preferred) |
| Disk throughput | 5 MB/s | 20 MB/s |

- Sizing is workload-driven (tenant size, number of scheduled reports/audits running in parallel) — treat the table as a floor, not a ceiling; large tenants (10k+ mailboxes, heavy audit retention) should be validated with ManageEngine support.
- **Exchange Online mailbox backup add-on:** plan 1:1 disk space against total source mailbox size before compression (product compresses to ~⅓, but size for the uncompressed working set plus retention).
- **Datastore:** PostgreSQL 15.7 (build ≥4800) or MS SQL 2012–2022 (build ≥4800) / Azure SQL; older PostgreSQL versions apply only to legacy builds. Elasticsearch is bundled for fast audit/content search.

### 3.4 Cross-Product Datastore Notes

- All three products default to an **embedded PostgreSQL** instance and can be pointed at an **external MS SQL Server** instead — this is the single most important lever for both HA and DR, since VM-level replication alone does not guarantee transaction-level consistency for an external SQL tier (it needs its own DR story — AlwaysOn AGs, log shipping, etc.).
- Elasticsearch/DataEngine indices are **not relocatable to a separate host** in the documented configurations — they run as in-process components on the same server, so they scale with, and must be backed up with, the application VM.

---

## 4. High-Availability Support — Verified

| Product | Native HA? | Mechanism | Verified Source |
|---|---|---|---|
| **ADManager Plus** | ✅ **Yes** | Primary + Standby instance (same build/arch/context path, same domain/IP range), sharing one external database, fronted by a **Virtual IP** (+ optional Virtual Host Name via DNS). Failover is automatic; PostgreSQL is treated as an external DB service during HA setup. | ManageEngine KB: *"Configure high availability in ADManager Plus"* |
| **ADAudit Plus** | ✅ **Yes** | **Hot standby model** — two redundant servers, one primary/one standby, sharing state; standby takes over automatically on primary failure. | ManageEngine Help: *"Overview \| High availability guide \| ADAudit Plus"* |
| **M365 Manager Plus** | ⚠️ **Not currently supported (standalone)** | A standby-server HA feature existed but was **explicitly discontinued in product builds 4324 and above** ("Only builds below 4324 will support this feature"). Current shipping builds are far beyond 4800, so this feature is not present in supported versions today. | ManageEngine KB: *"Configure standby server in M365 Manager Plus for high availability"* |

**Important nuance on AD360-bundled HA:** AD360 (the suite that bundles all of these products) has its own HA framework, configured centrally from the AD360 console. However, ManageEngine's own documentation is **inconsistent**:
- An older AD360 HA configuration guide lists **three** supported components: *ADManager Plus, ADSelfService Plus, and O365 Manager Plus* (M365 Manager Plus's former name).
- The current version of the same guide hosted on manageengine.com lists **only two**: *ADManager Plus and ADSelfService Plus* — M365 Manager Plus has been dropped from the list.
- AD360's September-2026 release notes do confirm active HA investment ("Introduced support for High Availability deployments across different subnets"), but don't clarify M365 Manager Plus's inclusion.

**Recommendation:** Do not assume M365 Manager Plus has application-level HA, even under AD360. Verify directly with ManageEngine support against your specific AD360/M365 Manager Plus build before designing around it, and default to **VM-level HA/replication** (see §5.3) as the safe baseline for this component.

---

## 5. Deployment Architecture — HA and DR

### 5.1 Design Principles Used

1. **ADManager Plus & ADAudit Plus** get **application-native HA** (Primary/Standby + Virtual IP) within the primary site, layered under **VM-level replication** to a DR site for site-loss protection.
2. **M365 Manager Plus** gets **VM-level HA/replication only** (no reliable app-native HA), since its cloud-only data source (M365 tenant) makes VM-replication-based recovery straightforward — there's no local AD/DC dependency to keep in sync.
3. **Database tier:** if you move any product to **external MS SQL**, that SQL tier needs its own independent DR mechanism (Always On Availability Groups / log shipping) — VM replication of the *application* VM does not give you transactional consistency for a *remote* SQL Server.
4. **DNS/FQDN discipline is the crux of failover for all three products.** Every client (browser, ADAudit Plus agents) and every reverse dependency must reference the products by **FQDN**, never a static IP — this is what makes both intra-site HA (Virtual IP/hostname) and inter-site DR (DNS repoint) transparent to end users and agents.

### 5.2 Primary-Site HA Layer (ADManager Plus & ADAudit Plus)

```
                              ┌─────────────────────────────┐
                              │   Virtual IP / Virtual Host   │
                              │   admp-ha.corp.local          │
                              │   adap-ha.corp.local          │
                              └──────────────┬────────────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     │                                                │
          ┌──────────▼──────────┐                          ┌─────────▼──────────┐
          │  ADMP / ADAP        │   heartbeat / same DB     │  ADMP / ADAP       │
          │  PRIMARY node       │◄──────────────────────────►  STANDBY node     │
          │  (Active)           │                            │  (Passive)         │
          │  Windows Server VM  │                            │  Windows Server VM │
          └──────────┬──────────┘                          └─────────┬──────────┘
                     │                                                │
                     └───────────────────┬────────────────────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │  External MS SQL Server │
                              │  (shared DB — required   │
                              │   for HA; avoid embedded │
                              │   PostgreSQL for HA)     │
                              └─────────────────────────┘

Agents / Domain Controllers / File Servers / Workstations
  → always address the product via FQDN/Virtual Host Name
  → automatic reconnect regardless of which node is Active
```

- Both nodes must run identical build/architecture, share the same context path, and sit in the **same domain and IP subnet** as the Virtual IP (ADManager Plus requirement).
- **Use an external database (MS SQL) for HA**, not the bundled PostgreSQL — ManageEngine explicitly warns that the embedded database undermines HA because it isn't independently reachable/failover-aware from a standby node.
- Failover is automatic on primary downtime; failback/HA-disable is only possible from the standby node.

### 5.3 Cross-Site DR Layer (all three products)

Modeled on ManageEngine's own documented pattern for ADAudit Plus (Hyper-V + Veeam Backup & Replication), extended uniformly to all three products since they share the same Tomcat/PostgreSQL/MSSQL + Elasticsearch application shape:

```
 PRIMARY SITE (Site A)                                DR SITE (Site B)
┌─────────────────────────────┐                    ┌─────────────────────────────┐
│  Hyper-V / VMware Host       │                    │  Hyper-V / VMware Host       │
│                              │                    │                              │
│  ┌────────────────────────┐ │   Async replication │  ┌────────────────────────┐ │
│  │ ADManager Plus VM (HA   │ │   every 5–15 min    │  │ ADManager Plus VM       │ │
│  │ pair or single) — ACTIVE│ ├─────────────────────►  │ (replica) — STANDBY     │ │
│  └────────────────────────┘ │   (Veeam / Hyper-V   │  └────────────────────────┘ │
│                              │    Replica / SRM)    │                              │
│  ┌────────────────────────┐ │                      │  ┌────────────────────────┐ │
│  │ ADAudit Plus VM — ACTIVE│ ├─────────────────────►  │ ADAudit Plus VM         │ │
│  │ (PostgreSQL+DataEngine  │ │                      │  │ (replica) — STANDBY     │ │
│  │  +Elasticsearch)        │ │                      │  │                          │ │
│  └────────────────────────┘ │                      │  └────────────────────────┘ │
│                              │                      │                              │
│  ┌────────────────────────┐ │                      │  ┌────────────────────────┐ │
│  │ M365 Manager Plus VM    │ ├─────────────────────►  │ M365 Manager Plus VM    │ │
│  │ — ACTIVE                │ │                      │  │ (replica) — STANDBY     │ │
│  └────────────────────────┘ │                      │  └────────────────────────┘ │
│                              │                      │                              │
│  (Optional) External MS SQL │  SQL Always-On AG /   │  (Optional) External MS SQL │
│  for ADMP/ADAP HA pair      │  log-shipping (indep. │  secondary replica          │
│                              │  of VM replication)   │                              │
└─────────────────────────────┘                      └─────────────────────────────┘
        │                                                        │
        └───────────────── DNS (FQDN) ──────────────────────────┘
        admp.corp.local / adap.corp.local / m365mp.corp.local
        Failover = repoint DNS A-record (or NAT mapping) to DR-site IP
```

**Why this works per product:**

| Layer | ADManager Plus | ADAudit Plus | M365 Manager Plus |
|---|---|---|---|
| App config, license | Included in VM disk → replicated | Included in VM disk (`conf` folder) → replicated automatically, no re-activation needed | Included in VM disk → replicated |
| Embedded PostgreSQL | Included in VM backup (app-aware/VSS) | Included in VM backup (app-aware/VSS) | Included in VM backup (app-aware/VSS) |
| External MS SQL (if used) | **Independent DR required** (AlwaysOn/log-shipping) | **Independent DR required** | **Independent DR required** |
| DataEngine / Elasticsearch | N/A (only used for optional clustering) | Included in VM backup | Included in VM backup |
| Agents (ADAudit Plus only) | — | Reconnect automatically post-failover **only if installed with FQDN**, never IP | — |
| Remote archive/report shares | — | **Not** covered by VM backup — needs independent replication of the NAS/share target | Not covered — same caveat applies if scheduled reports write to a remote share |
| Web console access | Repoint DNS/NAT to DR VM IP | Repoint DNS/NAT to DR VM IP | Repoint DNS/NAT to DR VM IP |

### 5.4 Consolidated Failover Runbook Checklist (applies to all three)

1. Confirm DR-site VM(s) meet or exceed primary-site sizing (§3) — under-provisioned DR VMs are the most common cause of missed RTOs.
2. Confirm replication cadence (Veeam/Hyper-V Replica or equivalent) meets your RPO — ADAudit Plus supports 30 sec / 5 min / 15 min intervals; align ADManager Plus and M365 Manager Plus VM replication to the same or tighter interval.
3. Verify all product FQDNs are used consistently — for endpoints (ADAudit Plus agents), for browser access, and for any NAT/reverse-proxy mapping.
4. Pre-stage DR-site firewall rules to mirror primary (LDAP/RPC/SMB/Kerberos/Global Catalog for ADMP & ADAP; HTTPS to Microsoft 365 endpoints for M365 Manager Plus and the M365 modules of ADMP).
5. If using external MS SQL, validate the SQL-side DR/failover independently (this is **not** covered by VM replication) — test actual SQL failover, not just VM boot.
6. Document and rehearse the DNS/NAT repoint step — this is the *only* manual action required in most failover scenarios once services are configured with FQDNs and set to automatic startup.
7. For ADManager Plus / ADAudit Plus HA pairs specifically: post-failback, remember HA can only be *disabled* from the standby node — build this into your runbook if you need to return to a single-node state.
8. Re-verify remote archive/report shares and NAS-based data sources are reachable and independently protected — these are explicitly **outside** VM-level backup scope for ADAudit Plus and likely M365 Manager Plus.

---

## 6. Key Risks / Caveats to Flag to Stakeholders

- **M365 Manager Plus has no dependable native HA today.** Any HA requirement for M365 Manager Plus should be met at the infrastructure layer (VM-level clustering/replication), not the application layer — confirm this against your exact AD360 build with ManageEngine support before committing to a design that assumes app-native HA.
- **HA for ADManager Plus/ADAudit Plus requires an external database.** Using the bundled PostgreSQL in an HA pair is explicitly discouraged by ManageEngine, since the standby node can't independently reach an embedded DB running only on the primary.
- **Elasticsearch/DataEngine are in-process, not separately scalable services** in the documented deployment model — plan compute/RAM headroom on the single VM rather than assuming a distributed search tier.
- **Disk sizing for ADAudit Plus is empirical, not table-driven** — the only ManageEngine-endorsed method is running 30 days of production load and reading the Disk Space Analysis graph. Don't rely solely on the static minimum/recommended table for real environments.
- **Do not co-host multiple ManageEngine products on one VM** — explicitly discouraged for ADAudit Plus due to resource contention; treat as best practice for ADManager Plus and M365 Manager Plus as well given they share the same Tomcat/DB/Elasticsearch footprint.

---

### Sources
- ManageEngine ADManager Plus — System Requirements, Solution Architecture, HA Configuration KB
- ManageEngine ADAudit Plus — System Requirements, HA Overview, DR/Veeam Architecture Guide
- ManageEngine M365 Manager Plus — System Requirements, HA Standby-Server KB (deprecation notice), Architecture Overview
- ManageEngine AD360 — HA Configuration Guide (legacy and current versions), Release Notes
