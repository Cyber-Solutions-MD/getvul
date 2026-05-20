# 18 — Glossary

Domain terms, acronyms, and internal jargon used throughout the codebase and docs. If you encounter a term you don't see here, please open a PR — that's a documentation gap.

## Vulnerability domain

| Term | Meaning |
|------|---------|
| **CVE** | Common Vulnerabilities and Exposures — a unique identifier for a publicly known vulnerability (e.g. `CVE-2024-3094`). |
| **CVSS** | Common Vulnerability Scoring System. GetVul tracks `cvss_v3_score` (0.0–10.0) and `cvss_v3_vector`. |
| **EPSS** | Exploit Prediction Scoring System — probability (0.0–1.0) that a vuln will be exploited in the wild within 30 days. |
| **CISA KEV** | CISA's Known Exploited Vulnerabilities catalog. `cisa_kev: true` means the CVE is on the catalog. |
| **Severity** | One of `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`. Drives SLA, alerting, and risk score. |
| **VulnStatus** | Lifecycle: `OPEN` → `IN_PROGRESS` → `REMEDIATED` / `SUPPRESSED` / `FALSE_POSITIVE`. |
| **VulnSource** | The scanner that produced the finding. Currently 4 enum values (`CROWDSTRIKE`, `NESSUS`, `DEFENDER`, `WIZ`); Qualys and Rapid7 connectors exist but the enum extension is pending (PROD-04-03). |
| **Confidence** | For correlations: `HIGH` if 3+ scanners confirm, `MEDIUM` if 2. |
| **Remediation** | A specific fix action (e.g. "Update OpenSSL to 3.1.5"). One remediation can apply to many vulns/hosts. |
| **Suppress** | Hide a remediation from the active remediations view without marking it remediated. |
| **Ignore (CVE / asset)** | Permanently exclude a CVE or an asset from remediations and ticket automation. |
| **SLA** | Per-severity remediation deadline, configurable per tenant. Defaults: CRITICAL=3d, HIGH=14d, MEDIUM=30d, LOW=90d. |
| **SLA breach** | A vulnerability still `OPEN` after `sla_deadline`. |
| **At-risk** | A vulnerability within 72 hours of SLA breach. |
| **MTTR** | Mean Time to Remediate — average time from `first_detected_at` to `remediated_at`. |

## Asset / device

| Term | Meaning |
|------|---------|
| **Asset** | A device or cloud resource — physical, virtual, or cloud. Identified primarily by hostname within a tenant. |
| **Device category** | `WORKSTATION`, `SERVER`, `NETWORK`, `MOBILE`, or `OTHER`. Auto-classified from CrowdStrike product type, hostname patterns, OS, or platform hints. |
| **Risk score** | 0–100 score derived from severity weights × exploit/KEV multipliers and a piecewise log curve. See [02-architecture.md](02-architecture.md#risk-scoring). |
| **`seen_by_sources`** | JSONB list of scanner names that have ever observed this asset. Used for filtering. |
| **MDM** | Mobile Device Management. GetVul integrates Jamf Pro (Apple) and Microsoft Intune. |
| **HRIS** | Human Resources Information System. GetVul reads from Humaans. |
| **IdP** | Identity Provider. Google Workspace, Azure Entra ID, Okta. |
| **Containment status** | CrowdStrike host containment state — `normal` (free), `contained` (network-isolated), `lift_pending`, etc. Surfaced in asset detail. |

## Auth / RBAC

| Term | Meaning |
|------|---------|
| **OIDC** | OpenID Connect — the auth-on-OAuth-2.0 protocol GetVul uses for SSO with Google and Azure. |
| **OIDC state** | A short-lived (10 min) token issued during `/auth/login/{provider}` that the callback must echo back. Used to defend against CSRF. Stored in Redis (`oidc:state:{token}`) post-Phase 1. |
| **JWT** | JSON Web Token. GetVul issues HS256 access (15 min) + refresh (7 days) tokens. |
| **`jti`** | JWT ID — unique per-token identifier. Optional revocation key. |
| **RBAC** | Role-Based Access Control. Roles: Owner > Admin > Analyst > Viewer. See [16-security.md](16-security.md). |
| **Tenant** | A customer organization. All domain rows carry `tenant_id`. Today's deployment model is one tenant per VM. |
| **SSO enforcement** | Per-tenant flag that disables password login. Per-user `allow_password_login` overrides it (for break-glass admins). |
| **Password policy** | Per-tenant JSONB with min length, require_upper/lower/digit/symbol, history length. Enforced on registration and change. |

## Tickets and automation

| Term | Meaning |
|------|---------|
| **Per-host ticket** | One external task containing all remediations for a single host. |
| **Per-remediation ticket** | One external task per remediation action, listing all affected hosts. |
| **Saved filter** | A reusable set of vulnerability filter conditions. Can be referenced by ticket rules. |
| **Ticket rule** | Schedule-driven automation that creates tickets from a saved filter. Schedules: 1h, 6h, 12h, 1d, 7d. |
| **Daily ticket sync** | Scheduled job that polls Asana/Jira for status changes and posts progress comments / auto-closes when GetVul vulns are resolved. |

## CSPM and compliance

| Term | Meaning |
|------|---------|
| **CSPM** | Cloud Security Posture Management — finding misconfigurations in cloud accounts (AWS, Azure, GCP). |
| **Misconfiguration** | A specific rule violation against a specific cloud resource (e.g. "S3 bucket has public read"). |
| **Compliance framework** | Industry standard like CIS, SOC 2, PCI-DSS, HIPAA. Misconfigurations map to one or more frameworks. |
| **Cloud resource** | The thing being checked — EC2 instance, S3 bucket, VPC, IAM role, etc. |

## Infrastructure

| Term | Meaning |
|------|---------|
| **COS** | Container-Optimized OS — Google Cloud's minimal Linux image used by the GCP VM ([infra/gcp/main.tf](../infra/gcp/main.tf)). |
| **IMDSv2** | EC2 Instance Metadata Service v2 (token-bound). Required by [infra/aws/main.tf](../infra/aws/main.tf) for the GetVul EC2 instance. |
| **NSG** | Network Security Group (Azure firewall). |
| **Static IP / Elastic IP** | A fixed public IP attached to the VM so DNS doesn't drift on reboot. |
| **ACME** | Automatic Certificate Management Environment — the Let's Encrypt protocol. nginx exposes `/.well-known/acme-challenge/` but no certbot service is wired into compose yet. |
| **HSTS** | HTTP Strict Transport Security. Emitted by nginx as `Strict-Transport-Security: max-age=31536000; includeSubDomains` on the HTTPS server only. |
| **CSP / COOP** | Content-Security-Policy / Cross-Origin-Opener-Policy. Documented but not yet emitted by the backend (PROD-04-01). The Next.js side does emit a CSP for frontend routes. |

## CI / CD

| Term | Meaning |
|------|---------|
| **SAST** | Static Application Security Testing. GetVul runs Semgrep in CI. |
| **DAST** | Dynamic Application Security Testing. GetVul runs OWASP ZAP against a stood-up CI stack — three scans, all currently `continue-on-error`. |
| **CD** | Continuous Deployment. `cd.yml` runs on GitHub release publish. |
| **Soft-fail** | A CI step that uses `\|\| true` or `continue-on-error: true` so a failure doesn't fail the workflow. PROD-02 removes them. |

## Observability

| Term | Meaning |
|------|---------|
| **structlog** | The structured-logging library. Logs are key=value pairs, not free-text. |
| **CEF** | Common Event Format. Audit-log line format for SIEM forwarding (Splunk, QRadar, Sentinel, Elastic). |
| **Audit log** | Persistent record of every mutating user action, in `audit_logs`. Optionally forwarded over syslog (UDP/TCP) in CEF. |
| **Daily snapshot** | A row in `daily_snapshots` capturing per-tenant aggregate metrics for trend charts. |

## Scanner-specific terms

| Term | Meaning |
|------|---------|
| **CrowdStrike AID** | Agent ID — CrowdStrike's per-host identifier. Stored in `assets.crowdstrike_aid`. |
| **Defender Device ID** | Microsoft Defender's per-host identifier. Stored in `assets.defender_device_id`. |
| **Wiz Asset ID** | Wiz's resource identifier. Stored in `assets.wiz_asset_id`. |
| **Nessus Host ID** | Tenable's per-host identifier. Stored in `assets.nessus_host_id`. |
| **Jamf ID** | Jamf Pro's computer ID. Stored in `assets.jamf_id`. |
| **QID** | Qualys ID — Qualys's per-vulnerability identifier (mapped to CVE). |

## Internal jargon

| Term | Meaning |
|------|---------|
| **GSD** | "Get Shit Done" — the planning/execution workflow under [.claude/get-shit-done/](../.claude/get-shit-done/). Slash commands like `/gsd-execute-phase` orchestrate it. |
| **Phase** | A discrete unit of milestone work. Phase 1 = multi-replica state, Phase 2 = CI gating, etc. Each phase has its own folder under `.planning/phases/<N>/`. |
| **Plan** | A sub-unit of a phase. Plan 01-02 = "Redis-backed rate limiter" within Phase 1. Each plan has a `PLAN.md` and a post-execution `SUMMARY.md`. |
| **Wave** | A group of plans that can execute in parallel. Within Phase 1, plans 01-00, 01-01, 01-02 were Wave 1; plan 01-03 was Wave 2. |
| **Multi-replica** | Running two or more backend replicas behind a load balancer. Phase 1 made GetVul safe under this topology even though the deployment model today is single-replica. |
| **Pitfall N** | Numbered traps documented in `.planning/phases/<N>/<N>-RESEARCH.md`. Phase 1 had ~6 pitfalls (e.g. Pitfall 1: ZADD coalescing under sub-ms timestamps; Pitfall 4: don't FLUSHDB the wrong db). |
| **Decision D-XX** | A user decision recorded in a phase's `<N>-CONTEXT.md`. E.g. D-05 = "rate limiter is a safety valve, fail-OPEN"; D-06 = "OIDC state is a CSRF defense, fail-CLOSED". |
| **GETDEL** | Redis 6.2+ command that atomically reads and deletes a key. The key primitive for OIDC-state replay protection. |
| **MULTI/EXEC pipeline** | Redis transactional pipeline. The rate-limiter sliding window runs four ops (`ZREMRANGEBYSCORE`, `ZADD`, `ZCARD`, `EXPIRE`) inside one. |

## Acronym quick-reference

| Acronym | Expansion |
|---------|-----------|
| API | Application Programming Interface |
| ASGI | Asynchronous Server Gateway Interface |
| CD | Continuous Deployment |
| CEF | Common Event Format |
| CI | Continuous Integration |
| COS | Container-Optimized OS |
| CSPM | Cloud Security Posture Management |
| CSP | Content Security Policy |
| COOP | Cross-Origin-Opener-Policy |
| CSRF | Cross-Site Request Forgery |
| DAST | Dynamic Application Security Testing |
| EPSS | Exploit Prediction Scoring System |
| GCE | Google Compute Engine |
| GSD | Get Shit Done (planning workflow) |
| HSTS | HTTP Strict Transport Security |
| IdP | Identity Provider |
| IMDS | Instance Metadata Service |
| JSONB | JSON Binary (Postgres column type) |
| JWT | JSON Web Token |
| KEV | Known Exploited Vulnerabilities (CISA) |
| MDM | Mobile Device Management |
| MTTR | Mean Time to Remediate |
| NSG | Network Security Group (Azure) |
| OIDC | OpenID Connect |
| ORM | Object-Relational Mapper |
| RBAC | Role-Based Access Control |
| SAST | Static Application Security Testing |
| SIEM | Security Information and Event Management |
| SLA | Service-Level Agreement |
| SMTP | Simple Mail Transfer Protocol |
| SSO | Single Sign-On |
| TLS | Transport Layer Security |
| TTL | Time To Live |
| UAT | User Acceptance Testing |
| UI | User Interface |
| VMDR | Vulnerability Management, Detection, and Response (Qualys product) |
| ZAP | Zed Attack Proxy (OWASP) |
