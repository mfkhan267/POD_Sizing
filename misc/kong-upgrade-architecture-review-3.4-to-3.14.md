# Kong Gateway Upgrade Architecture Review
## Path: 3.4 (LTS) → 3.10 (LTS) → 3.14 (LTS)

Kong publishes dedicated, tested migration paths only **between consecutive LTS releases** (2.8→3.4, 3.4→3.10, 3.10→3.14). Applying migration steps across any other interval can leave the database schema in a broken state, so this review treats the upgrade as **two sequential projects**, not one jump.

---

## 1. Information to Request / Gather (Discovery)

| Category | Details Needed |
|---|---|
| Topology | Traditional (DB-backed Postgres), DB-less/declarative, or Konnect hybrid; number of control planes / data planes |
| Deployment platform | VM, Docker, Kubernetes (Ingress Controller / Kong Operator version), bare metal |
| Current versions | Exact patch version (e.g., 3.4.3.x), Postgres version, OS/distro, decK version, KIC/Operator version |
| Plugin inventory | All installed plugins (core + custom/Lua), custom plugin source code, third-party plugins |
| Config management | decK-managed (declarative) vs. Admin API/Kong Manager-managed vs. Konnect-managed |
| Traffic profile | RPS/peak RPS, connection counts, payload sizes, latency SLAs |
| Integrations | OIDC/SAML/IdP config, Vault/secrets manager, Redis (rate-limiting/session), OpenTelemetry/observability stack, WAF |
| Enterprise features in use | Dev Portal, Vitals, Workspaces, RBAC, Konnect vs. self-hosted licensing |
| Environments | List of all environments (dev/staging/prod), and whether lower environments mirror prod config |
| Change history | Any deferred upgrades, known workarounds, custom Nginx/OpenResty templates |

---

## 2. Initial Assessment

- **Version delta mapping**: Confirm current version is on the latest 3.4.x patch before starting (Kong recommends patching to the latest point release of the source LTS first — smoothest path and unlocks preflight tooling).
- **Support policy check**: Confirm OS/platform EOL dates against Kong's version support matrix for 3.10 and 3.14 (3.14 is the current LTS as of its April 2026 release; each LTS has a defined support window tied to release date).
- **Custom code audit**: Any custom Lua plugins, serverless functions plugins, or Nginx template overrides need compatibility testing (Lua sandboxing behavior changes are a known 3.14 breaking change).
- **License/entitlement check**: Confirm Enterprise license validity spans the target version, and Konnect vs. self-hosted control plane status.
- **Read the changelogs**: Full review of breaking changes/deprecations for the 3.4→3.10 range and separately the 3.10→3.14 range (they are documented as two distinct guides).

---

## 3. Upgrade Options (Strategies)

Kong supports three strategies for LTS-to-LTS upgrades — choice depends on topology and downtime tolerance:

1. **In-place upgrade** — Upgrade binaries/nodes on existing cluster, run `kong migrations` in sequence. Simplest, but higher risk and some downtime/version-skew window.
2. **Dual-cluster (blue-green)** — Stand up a parallel cluster on the target version, migrate/sync config (via `deck file convert` + sync), cut traffic over, monitor, then decommission the old cluster. Lowest risk, near-zero downtime, but needs double infrastructure temporarily.
3. **Rolling upgrade** — Node-by-node upgrade within a cluster (common in Kubernetes with the Ingress Controller/Operator), relying on backward-compatible data planes during transition. Best for large multi-node clusters wanting continuous availability.

**Recommendation pattern**: Dual-cluster for production/critical tiers; in-place or rolling acceptable for dev/staging or smaller footprints.

---

## 4. Capacity Assessment (Required — Yes)

Required for both legs, especially if moving to dual-cluster/blue-green:

- **Parallel infrastructure sizing** if blue-green: temporary 2x compute/memory footprint for data planes during cutover window.
- **Database sizing**: Postgres migration adds schema/index changes; assess DB CPU/IO headroom during `kong migrations up`/`finish`, and connection pool limits (PgBouncer, if used).
- **OpenResty/Nginx behavior changes**: Newer OpenResty base (picked up across 3.x releases) enforces stricter RFC 9112 header validation — assess if any upstream services send duplicate/malformed `Content-Length` or `Transfer-Encoding` headers, which will now be rejected (502s) instead of tolerated.
- **Plugin performance re-baseline**: Re-test latency/throughput for rate-limiting, AI plugins, and auth plugins post-upgrade — new defaults (e.g., stricter TLS verification, sandboxing) can add overhead.
- **Rollback capacity**: Ensure old cluster/DB backups remain resourced and available until the new version is signed off (migrations are **not reversible** via `kong migrations` — restoration must come from backups).

---

## 5. Gap Analysis (Breaking Changes to Map)

### Leg 1: 3.4 → 3.10
> **No preflight compatibility tool exists for this leg.** Unlike the 3.10→3.14 leg (which has `kong check --lts-314-compatibility`), Kong provides no equivalent `--lts-310-compatibility` CLI check. Mitigation is upgrading to the latest 3.4.x patch first, manual review of the changelog tables below, and — for DB-less/declarative deployments — validating config with `deck gateway validate` or `kong config parse` against the target version (schema/syntax validation only, not a full compatibility sweep).

- Enterprise **Dev Portal and Vitals** were removed from the bundled Enterprise package starting 3.5 — if either is in use, plan a separate support/migration track (legacy customers are supported via a dedicated mechanism).
- **PCRE upgraded from libpcre 8.45 → libpcre2 10.43** — regex syntax changed; any incompatible regular expressions in routes/plugins will prevent Kong from applying configuration. Audit and rewrite against the [PCRE2 syntax reference](https://www.pcre.org/current/doc/html/pcre2syntax.html).
- **OpenResty bumped 1.21.4.2 → 1.25.3.1**, picking up stricter Nginx RFC 9112 header enforcement — upstream responses with duplicate `Content-Length` headers, duplicate `Transfer-Encoding` headers, or both, are now rejected with a `502 Bad Gateway` instead of tolerated.
- **OpenSSL 3.2 default TLS/SSL security level raised from 1 to 2** (112 bits) — RSA/DSA/DH keys shorter than 2048 bits, ECC keys shorter than 224 bits, RC4 cipher suites, SSLv3, and compression are now prohibited. TLS 1.1 and earlier are disabled by default (set `ssl_cipher_suite: old` if still required).
- **OS/package support dropped**: Debian 10, CentOS, and RHEL 7 are no longer built (all EOL). Must migrate to Debian 11/12 or RHEL 8/9 before upgrading.
- **Standardized Redis config** across plugins (AI Rate Limiting Advanced, GraphQL Proxy/Rate Limiting Advanced, Proxy Caching Advanced, Rate Limiting Advanced, ACME, Rate Limiting, Response Rate Limiting) — `cluster_addresses`/`sentinel_addresses` renamed to `cluster_nodes`/`sentinel_nodes`. Bundled plugins auto-migrate on `kong migrations up`; **forked/custom plugins using the shared Redis config do not** and need manual migration.
- **SAML plugin priority changed to 1010** — can reorder execution relative to other Consumer-based custom plugins; review custom plugin priority chains.
- **Azure Functions plugin** now requires `config.routeprefix`; the old upstream/request URI construction is removed.
- **OAS Validation plugin** now bypasses schema validation for non-`application/json` content types.
- **Kong Manager + OIDC session config** moved from `admin_gui_session_conf` to `admin_gui_auth_conf` — default values differ, review before upgrading.
- **Consumer/Consumer Groups list endpoints** are now paginated and the JSON key changed to `data` — update any CI/scripts parsing these.
- **Granular Tracing removed** — remove `tracing*` settings from `kong.conf`; migrate to the OpenTelemetry plugin.
- **Dynamic plugin ordering now requires an Enterprise license** — remove from free-mode installs or engage Kong Support; free mode itself is deprecated and slated for removal.
- Entity configuration format changes — use `deck file convert` (3.4→3.10 profile) rather than hand-editing.

### Leg 2: 3.10 → 3.14
- **`untrusted_lua`** default changes from `sandbox` to **`strict`** (new `strict`/`lax` modes introduced) — custom/serverless-function Lua plugins may break; test explicitly.
- **`tls_certificate_verify`** default change affects several plugins' TLS/SSL verification behavior — audit which plugins/upstreams rely on the old default; revert per-plugin via `tls_certificate_verify: off` only if truly required.
- **OpenTelemetry plugin**: `config.access_logs_endpoint` renamed to `config.access_logs.endpoint` (old field deprecated, still works but flagged for removal).
- Use the **`kong check --lts-314-compatibility`** preflight CLI tool (available once on the latest 3.10 patch) to validate `kong.conf` against 3.14 before migrating.
- Use `deck file convert` (3.10→3.14 profile) for declarative config conversion.

---

## 6. Teams to Involve & Action Items

| Team | Action Items |
|---|---|
| **DevOps / Platform Engineering** | Own infrastructure provisioning (blue-green or rolling), DB backup/restore rehearsal, CI/CD pipeline updates for new version, monitoring/alerting updates, execute `kong migrations`, run preflight compatibility checks |
| **API / Gateway team (Kong owners)** | Own plugin inventory & compatibility testing, decK config conversion (`deck file convert`), breaking-change/deprecation remediation, Admin API/Kong Manager or Konnect config validation, RBAC/Workspace review |
| **Security team** | Review TLS verification default changes, `untrusted_lua` sandboxing implications, secrets/Vault integration compatibility, audit logging (OpenTelemetry field rename) |
| **App/service owning teams (API consumers)** | Validate upstream services tolerate stricter HTTP header enforcement (no duplicate Content-Length/Transfer-Encoding), regression test consumer-facing routes/plugins (auth, rate-limiting) |
| **SRE / Observability** | Re-baseline dashboards/alerts post-upgrade, validate OTel exporter config after field rename, load-test post-migration |
| **QA / Release Management** | Own smoke-test suite for dev → staging → prod promotion gates, sign-off criteria, rollback trigger criteria |
| **Enterprise licensing/procurement (if applicable)** | Confirm license terms cover Dev Portal/Vitals continuation if still used, confirm 3.14 entitlement |

---

## 7. Prerequisites (Both Legs)

- Latest patch version of the **source** LTS installed first (3.4.x latest → before touching 3.10; 3.10.x latest → before touching 3.14).
- Full **database backup** (native Postgres export/import) and/or **declarative config backup**, taken immediately before migration — mandatory, as migrations are irreversible.
- decK installed at a version compatible with the target Kong version, for `deck file convert` and sync operations.
- Pre-production environment that mirrors production topology for full migration rehearsal.
- Reviewed and remediated breaking-changes/deprecations list for the relevant leg.
- Rollback plan documented (cluster-swap or DB restore procedure) and rehearsed.
- Confirmed OS/platform support window covers the target version.

---

## 8. Phases & Stages

### Project 1: 3.4 → 3.10
1. **Preparation** — Patch to latest 3.4.x; review 3.4→3.10 breaking changes; back up DB/config; choose strategy (in-place / dual-cluster / rolling).
2. **Pre-production migration test** — Full dry run in staging, including `deck file convert` (3.4→3.10 profile) and `kong migrations` sequence.
3. **Execution — Dev** — Run chosen strategy on dev, smoke test.
4. **Execution — Staging** — Repeat with production-like data volume/traffic shadowing if possible.
5. **Execution — Production** — Cutover (blue-green) or in-place/rolling migration; run `kong migrations up` → `kong migrations finish`.
6. **Validation & monitoring** — Smoke tests, proxy metrics, error-rate/latency comparison.
7. **Finish or rollback** — Decommission old cluster once stable, or restore from backup if issues arise.

### Project 2: 3.10 → 3.14
1. **Preparation** — Patch to latest 3.10.x (unlocks `kong check --lts-314-compatibility`); review 3.10→3.14 breaking changes (`untrusted_lua`, `tls_certificate_verify`, OTel field rename); back up.
2. **Compatibility preflight** — Run `kong check --lts-314-compatibility` against `kong.conf`; remediate flagged items.
3. **Pre-production migration test** — Dry run with `deck file convert` (3.10→3.14 profile); test custom Lua plugins under `strict` sandboxing; validate TLS verification changes against real upstreams.
4. **Execution — Dev → Staging → Production**, mirroring the same promotion gates as Project 1.
5. **Post-upgrade validation** — Confirm OTel access-log exporter, TLS handshakes to upstreams, custom plugin behavior, header-validation edge cases.
6. **Finish or rollback**, then close out with a lessons-learned/retro.

---

### Summary Gate Criteria (apply at each promotion step)
- All automated smoke tests pass
- No unexpected 4xx/5xx increase vs. baseline
- Plugin-specific functional tests (auth, rate-limiting, AI, OTel) pass
- Rollback procedure confirmed available (backup verified restorable) before proceeding to next stage
