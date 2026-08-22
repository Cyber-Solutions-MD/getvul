# Phase 43: Executive & Compliance Reporting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-22
**Phase:** 43-executive-compliance-reporting
**Areas discussed:** Board PDF composition, Role-scoped dashboards, Compliance mapping model, Compliance view surfacing

---

## Board PDF composition

### PDF generation approach
| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing PDF | Add new sections to `generate_executive_summary_pdf` (fpdf2); reuse branding + section-toggle + exclusion | ✓ |
| New board-report generator | Dedicated separate board report with its own layout/cover | |

### Charts in PDF
| Option | Description | Selected |
|--------|-------------|----------|
| Server-rendered chart images | Render trend/burndown/MTTR to PNG server-side and embed | ✓ |
| Tables + headline numbers | Compact tables + big deltas, no new dependency | |
| You decide | Let planning weigh dependency vs value | |

### Period selector
| Option | Description | Selected |
|--------|-------------|----------|
| Presets + custom range | Quarter/30d/90d/1y presets + custom start/end (Phase 42 D-03 idiom) | ✓ |
| Presets only | Fixed presets | |

### Delivery
| Option | Description | Selected |
|--------|-------------|----------|
| Reuse scheduled delivery | Board report as a format/section-set in `ScheduledReport`, auto-email + on-demand | ✓ |
| On-demand export only | Download-only, no scheduling | |

**Notes:** New chart-image path implies a new backend charting dep (matplotlib/Pillow); flagged for research since only `fpdf2>=2.8` is present today.

---

## Role-scoped dashboards

### Persona model
| Option | Description | Selected |
|--------|-------------|----------|
| Switchable view-lens | Any user picks a persona lens; not tied to RBAC | ✓ |
| Saved default + switchable | Same, plus a persisted default-view user attribute | |
| Bound to RBAC role | Auto-render by owner/admin/analyst/viewer | |

### Surface
| Option | Description | Selected |
|--------|-------------|----------|
| Reconfigure /dashboard | One page, widget set swaps per lens | ✓ |
| Net-new dashboard pages | Separate route per persona | |
| You decide | | |

### Content distinction
| Option | Description | Selected |
|--------|-------------|----------|
| Trend & posture, not lists | Leadership/compliance = trend/MTTR/SLA%/framework/PDF; analyst/IT-ops = triage | ✓ |
| Same widgets, filtered scope | Same widget types, scoped differently | |
| You decide | | |

**Notes:** "Role" = job function, deliberately decoupled from RBAC-01 permission tier. Lens persisted client-side (URL/localStorage), no backend column.

---

## Compliance mapping model

### Mapping model
| Option | Description | Selected |
|--------|-------------|----------|
| Program-level control evidence | Vuln-mgmt program → curated controls, evidenced by posture metrics | ✓ |
| Per-finding control tagging | Tag each finding with violated controls | |
| Hybrid | Program-level + drill into findings behind each control | |

### Catalog source
| Option | Description | Selected |
|--------|-------------|----------|
| Built-in curated catalog | Fixed version-controlled mapping, no tenant config | ✓ |
| Built-in + tenant overrides | Curated + tenant toggle/threshold config | |
| You decide | | |

### Scope vs CSPM
| Option | Description | Selected |
|--------|-------------|----------|
| Vuln-only this phase | Keep separate from CSPM `get_compliance_dashboard` | ✓ |
| Unify vuln + CSPM | One blended per-framework rollup | |
| You decide | | |

**Notes:** Program-level evidence chosen because most CVEs map to the same handful of vuln-mgmt controls; per-finding tagging is low-value.

---

## Compliance view surfacing

### Surface
| Option | Description | Selected |
|--------|-------------|----------|
| New 'Compliance' nav page | /dashboard/compliance, mirrors Coverage/Analytics precedent | ✓ |
| Section on the compliance lens | No new nav item; section inside the lens | |
| You decide | | |

### Frameworks day one
| Option | Description | Selected |
|--------|-------------|----------|
| All four | SOC 2 + ISO 27001 + PCI DSS + NIST CSF | ✓ |
| Two, extensible | SOC 2 + PCI DSS first, catalog additive | |
| You decide | | |

### Control status derivation
| Option | Description | Selected |
|--------|-------------|----------|
| Threshold on posture metrics | Metric + pass/partial/fail thresholds in catalog | ✓ |
| Status + drill to findings | Same + drill into findings behind each control | |
| You decide | | |

**Notes:** Drill-to-findings evidence deliberately deferred (threshold status only this phase).

---

## Claude's Discretion

- Default PDF reporting period; exact new PDF section layout/order.
- Charting library choice + image generation/embedding mechanics.
- Exact per-lens widget composition per persona; lens-switcher rendering + placement.
- Catalog contents: which controls per framework, evidencing metric per control, and thresholds.
- `/dashboard/compliance` route naming/layout; whether framework posture also renders as a compact section in the compliance lens.

## Deferred Ideas

- **Redo filtering / ChipBar UI/UX** — raised mid-discussion; new capability, its own phase (not in current v5.0 roadmap). Promote via `/gsd-phase` or `/gsd-capture`.
- Per-finding framework-control tagging.
- Tenant-configurable compliance catalog / control overrides.
- Unified vuln + CSPM compliance view.
- Control → drill-into-specific-findings evidence view.
- Saved "default dashboard view" as a backend user preference.
