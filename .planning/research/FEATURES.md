# Feature Research

**Domain:** Enriched risk-exposure scoring + scanner-source-aware triage (vulnerability management)
**Researched:** 2026-08-04
**Confidence:** MEDIUM-HIGH (methodology descriptions from official vendor docs = HIGH; exact numeric weights inside proprietary ML models = LOW/undisclosed, GetVul's existing deterministic-formula pattern is used instead)

## Context Recap

GetVul already has: 6-scanner aggregation, cross-source CVE-on-host correlation (`vulnerability_correlations`), a deterministic asset risk score (`backend/app/assets/risk_score.py` — piecewise power/log curve over `SEVERITY_WEIGHTS × exploit_available(×2) × cisa_kev(×3)`), an `epss_score` column already on `Vulnerability` (populated inconsistently per connector), `seen_by_sources` JSONB on `Asset`, a `source` chip-bar filter already on `/vulnerabilities` (array-based, OR semantics implicit in existing IN-clause filtering), IdP/MDM/HR enrichment, per-severity SLA tracking, and a generalized DrillPanel. v4.0 adds: (1) deeper connector enrichment preserving scanner-native signals, (2) auto-inferred asset exposure context with admin override, (3) a clean-slate risk-exposure model, (4) scanner-source filtering with AND toggle across 4 screens, (5) source-provenance badges.

## Feature Landscape

### Table Stakes (Users Expect These)

Features every serious risk-based-vulnerability-management (RBVM) tool has today. A v4.0 that lacks these will read as "still doing CVSS-only triage" to any analyst who has used Tenable/Qualys/Rapid7/Kenna.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| EPSS score + percentile surfaced per finding | Industry-standard exploit-likelihood signal (FIRST.org), used by CrowdStrike, Rapid7 Active Risk, Kenna/Cisco, Qualys TruRisk alike. Distinguishes "CVSS 9.8 nobody exploits" from "CVSS 7.0 actively weaponized." | LOW | GetVul already has `epss_score` column — the gap is ingestion consistency + surfacing the percentile (not just raw probability) in UI, and using it in the *new* score. |
| CISA KEV flag as an override/escalation signal | CISA and every major vendor treat "known-exploited-in-the-wild" as the single highest-priority binary signal, independent of CVSS. Federal guidance (BOD 26-04) formalizes remediation-priority-regardless-of-CVSS for KEV. | LOW | GetVul already has `cisa_kev` boolean + a 3x multiplier — carry forward into new model, likely as a floor/escalation rule rather than just a multiplier (see Architecture note below). |
| Vendor-native exploitability/priority signal captured per finding (VPR, ExPRT.AI rating, QDS) | Tenable VPR, CrowdStrike ExPRT.AI, and Qualys QDS are each dynamic (change daily/on new threat intel) and are the reason analysts trust one scanner's number over raw CVSS. Normalizing these away (as GetVul does today) throws away the scanner's own risk logic. | MEDIUM | Requires per-connector parser changes (crowdstrike.py, nessus.py, qualys.py, etc.) to persist a raw vendor-score field + label, likely a `source_risk_signals: JSONB` column on `Vulnerability` (mirrors existing `seen_by_sources` JSONB pattern on Asset) rather than N new typed columns per vendor. |
| Asset criticality / business-value tag, at minimum a manual override | Every mature tool (Qualys ACS 1-5, Kenna's asset "priority" 1-10, Tenable Lumin's Asset Criticality Rating, Cisco VM asset priority) multiplies vuln risk by asset value. Without this, "risk exposure" degenerates back into "raw severity." | MEDIUM | New `assets` columns: `business_criticality` (enum/1-5), `data_sensitivity` (enum), `internet_facing` (bool), each with an `_source` (auto/override) + `_overridden_by`/`_overridden_at` audit pair. |
| Internet-facing / externally-reachable flag | Universal signal across Wiz (attack-path reachability), Qualys EASM, CTEM frameworks — externally-reachable assets get materially shorter SLA and higher priority. GetVul already stores `external_ip` on Asset; today nothing derives a boolean from it. | LOW-MEDIUM | Auto-infer from existing `external_ip` non-null + device_category != MOBILE, or Wiz/cloud connector "publicly exposed" flags already ingested; admin override for edge cases (internal proxy with public IP, etc.) |
| A single authoritative risk-exposure number per finding AND per asset (not just per-asset) | Tenable VPR is per-vulnerability; Qualys TruRisk has both QDS (per-vuln) and asset-level TruRisk; Kenna scores both vuln and asset. Triage analysts sort/filter at the finding level, not only the asset level. | MEDIUM-HIGH | GetVul's current model is asset-only (`Asset.risk_score`). v4.0's "clean slate" model should very likely add a per-finding exposure score column too, since sorting the vuln list (chip-bar) by "most urgent finding" is a core current UX and a per-asset-only score can't drive it. |
| Deterministic, explainable score (not an opaque ML black box) | GetVul's existing score is already a documented formula; the whole v3.0 AI layer explicitly "augments never replaces" it. Every RBVM vendor also publishes a documented (if not fully open) formula for their headline score even when ML components exist underneath (Tenable, Kenna). Analysts need to explain "why is this a 92" to auditors/management. | LOW (design constraint, not new code) | Carries forward the existing architectural decision; a rebuilt model must still be a formula, not a trained model, to match GetVul's "AI augments the deterministic score" invariant from v3.0. |
| Source-provenance badge per finding row | Rapid7/Tenable/Qualys/CrowdStrike are each single-scanner tools and don't need this — but any *aggregator* (GetVul's actual category) must show which scanner(s) reported a finding, or users can't tell if "confirmed everywhere" vs. "only one scanner's opinion." This is GetVul's own differentiator turned table-stakes at v4.0 scale. | LOW-MEDIUM | `vulnerability_correlations` already links same-CVE-per-asset across sources — badge is largely a read-side rendering of that existing join, not new data. |
| Scanner-source filter with OR semantics ("show me findings from Tenable OR Qualys") | Baseline faceted filtering; GetVul's `/vulnerabilities` chip-bar already has a `source` array filter — this is confirming/extending an existing pattern, not new ground. | LOW | Already exists on Vulnerabilities; extend the same chip-bar component to Assets/CSPM/Tickets. |
| Filter persists in URL / is shareable | Existing GetVul chip-bar pattern (querystring-driven) already does this on `/vulnerabilities`; users expect consistency across the 3 new screens. | LOW | Reuse pattern, not a new design problem. |

### Differentiators (Competitive Advantage)

Not required for MVP credibility, but where GetVul earns "we're better than opening 4 scanner consoles."

| Feature | Value Proposition | Complexity | Notes |
|---------|--------------------|------------|-------|
| AND-toggle for true multi-scanner corroboration ("confirmed by BOTH Tenable AND Qualys") | This is the single most differentiated ask in the milestone brief and has no direct off-the-shelf equivalent in single-scanner tools (Tenable/Qualys/Rapid7 don't need it — they only see their own data). It converts "noisy possible-duplicate" into "high-confidence, cross-validated finding" — directly matching the industry concept that convergence across independently-operating detection layers is a strong confidence signal. | MEDIUM | Needs `vulnerability_correlations` (or a materialized per-CVE-per-asset source-set) queried with an actual set-intersection semantics, not just an `IN` filter — different SQL shape than the existing OR chip. Toggle state must also persist in the URL alongside the OR list. |
| Corroboration as an explicit *scoring* input (not just a filter) — e.g., a finding independently confirmed by 2+ scanners gets a confidence/urgency bump | No major vendor scores this way today (each vendor only sees itself) — this would be a genuine GetVul-specific innovation enabled uniquely by being a 6-scanner aggregator. | MEDIUM-HIGH | Requires the new model to take "distinct corroborating source count" as an input signal (see Risk-Exposure Model Inputs below) — cheap to compute (already have `vulnerability_correlations`), high analyst trust payoff. |
| Auto-inferred exposure context from *existing* enrichment (no new connector needed) | Kenna/Qualys/Tenable all *require* the customer to manually tag assets in a CMDB integration or asset-group UI as a separate onboarding step. GetVul already has MDM/HR/IdP enrichment (owner department, device type) it can mine for a first-pass inference (e.g., "owned by Finance + tagged PCI scope in Jamf" → higher data-sensitivity) before any human touches it. | MEDIUM-HIGH | This is the hardest-to-get-right feature in the milestone — see Pitfalls doc for the "confident-sounding wrong inference" risk. Needs a documented, inspectable rule set (not ML) per the deterministic-model constraint, and every inferred value must show its provenance ("inferred from: Jamf scope tag `pci-cde`") so an analyst can sanity-check before overriding. |
| Admin override with audit trail on exposure context, at asset or asset-group scope | Qualys ACS supports override via asset tags; Kenna via asset groups + custom "asset priority." Doing overrides at group scope (not just per-asset) avoids re-tagging every host in "all of prod-payments" one at a time. | MEDIUM | Must emit an audit event per CLAUDE.md constraint ("New features must register audit events"); group-scope override needs a clear precedence rule vs. per-asset override (per-asset should win). |
| Per-finding AND per-asset risk-exposure trend history, migrated in one recompute | Qualys/Kenna/Tenable all show trend-over-time dashboards; GetVul already has trend charts (recharts) wired to the old score. A "rip the model out and recompute history" is a real, nontrivial migration risk unique to a "clean slate, not additive" replacement — worth flagging as a differentiator-adjacent risk area, not a pure differentiator. | HIGH | See Pitfalls: historical trend lines will show a discontinuity at the cutover unless a backfill recompute against historical vuln-state snapshots is done, which may not be possible if GetVul doesn't retain historical open/closed state at fine enough grain. |
| Toxic-combination style compound signals (internet-facing AND critical-data AND actively-exploited) surfaced as an explicit call-out, not just as three separate filter chips | Wiz's core differentiator ("toxic combinations") — chaining multiple individually-modest signals into "this one is actually dangerous." GetVul's chip-bar + drill panel could show a one-line badge like "Internet-facing · PCI data · KEV" summarizing why a score is high, echoing the AI layer's "cite-or-refuse" transparency ethos. | MEDIUM | This is presentation/UX on top of the new score's already-computed inputs — cheap once the exposure-context fields exist; mostly a DrillPanel content addition. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Full ML-trained exploit-prediction model built in-house (a GetVul "ExPRT.AI clone") | "Tenable/CrowdStrike use ML, shouldn't we?" | Training data (CrowdStrike's global endpoint telemetry, Tenable's 150+ features across their entire customer base) simply doesn't exist inside a single-tenant, single-VM deployment; a home-grown model trained on one org's data would be statistically meaningless and unauditable — directly conflicting with GetVul's existing "deterministic, explainable" architecture decision and the v3.0 "AI augments, never replaces the score" invariant. | Consume the vendor's *already-computed* ML output (VPR, ExPRT.AI rating, QDS) as an input signal to GetVul's own deterministic formula — get the ML benefit without owning the ML risk. |
| Auto-override exposure context silently overwriting a prior human override on every re-sync | "Keep exposure context always fresh from the latest scan/MDM data" | Silently clobbering an analyst's considered judgment ("this dev box is actually a decommissioned honeypot, not critical") erodes trust in the whole exposure-context feature the moment it happens once; this is the generic "auto-sync stomps human edit" anti-pattern. | Auto-infer only fills a field that has never been human-overridden; once overridden, subsequent auto-infer runs skip that field and instead surface a "signals suggest this changed — re-review?" notification, mirroring GetVul's existing ignore/suppress-with-audit-trail pattern (VULN-03). |
| AND-toggle becomes the default for source filtering | "Corroboration is more rigorous, make it the default" | The milestone spec explicitly calls for OR-default; defaulting to AND would silently hide every single-scanner-only finding from list views the moment 2+ sources are selected — a correctness-destroying default for a triage tool whose entire value prop is "see everything." | OR default (already decided in scope), AND as an explicit opt-in toggle with a chip-bar-level explanit (small helper text: "showing findings seen by ANY selected source" vs "ALL selected sources"). |
| Replacing CVSS/severity entirely with the new exposure score in every view | "Exposure is the better number, hide the noisy CVSS" | Analysts, auditors, and compliance frameworks (PCI, SOC2) still need to answer "what's the CVSS severity" as a distinct, externally-recognized number — Qualys/Tenable/Rapid7 all keep raw CVSS visible *alongside* their proprietary score for exactly this reason, never as a replacement. | Show both: raw CVSS/severity (existing chip-bar facet, compliance-legible) and the new risk-exposure score (sort key, SLA driver) side by side — same pattern GetVul already uses to keep CVSS visible even though risk_score already exists today. |
| One giant opaque "risk exposure" number with no per-input breakdown in the UI | "Simpler for analysts — just show the number" | Every asked-about vendor (Tenable's "CVSS vs VPR" doc, Qualys's documented TruRisk formula, Kenna's public risk-meter breakdown) explicitly publishes the *inputs* alongside the score because analysts distrust and ignore black-box numbers — this is the same lesson GetVul already learned by documenting its formula in risk_score.py's own docstring. | The DrillPanel must show the score's contributing inputs (severity weight, EPSS, KEV, vendor signal, corroboration count, asset exposure context) as a breakdown, not just the final number — reuses the existing DrillPanel real estate. |
| Real-time/streaming re-score on every single scan delta, per finding, as it lands | "Feels more responsive/live" | GetVul's stated architecture explicitly rejects real-time websockets as unnecessary at current scale (Out of Scope: "Real-time websocket dashboards — polling is sufficient"); per-event re-scoring at ingestion time for every one of 6 scanners' deltas risks recompute storms and lock contention on a single-VM Postgres, especially since `compute_risk_scores` today does a full tenant-wide recompute pass. | Recompute risk-exposure in the same batch/scheduled cadence the current `recompute_risk_scores` endpoint/scheduler job already uses (or on ingestion-batch-complete, not per-row), consistent with the existing polling-is-fine architecture decision. |

## Part (a): What Enriched Signals Feed a Modern Risk-Exposure Score

Concretely, mature tools combine four categories of input. GetVul's rebuilt model should draw from the same four categories, using vendor-native fields where the connector supplies them and a documented fallback where it doesn't:

**1. Technical severity/impact** (largely already in GetVul)
- CVSS base/impact score (`cvss_v3_score` — already present)
- Severity bucket (`severity` — already present)

**2. Exploitability / threat intelligence** (partially in GetVul, needs enrichment)
- EPSS probability + percentile (FIRST.org) — column exists, percentile surfacing + consistent ingestion is the gap
- CISA KEV membership — exists, should act as a near-automatic escalation/floor rather than only a multiplier (BOD 26-04 treats KEV-on-internet-facing as "prioritize regardless of CVSS")
- Vendor-native dynamic exploit signal: Tenable VPR (0.1–10, ML over 150+ features incl. exploit code maturity + age), CrowdStrike ExPRT.AI rating (adversary-telemetry-trained, changes as intel changes), Qualys QDS (1–100, folds in CVSS + KEV + exploit maturity) — new capture required per connector
- Exploit-code-maturity / "has a public PoC" flag (`exploit_available` — already present)

**3. Asset exposure context** (net-new for GetVul)
- Business criticality (Qualys ACS 1–5 tag-derived; Kenna asset "priority" 1–10; Tenable Lumin Asset Criticality Rating) — auto-inferred + admin-overridable
- Data sensitivity (does the asset hold PII/PCI/PHI/regulated data — commonly modeled as a tag/classification, e.g., Qualys business-impact tags, CMDB `data_class` field)
- Internet-facing / externally reachable (Qualys EASM, Wiz attack-surface scanning, CTEM "reachability") — derivable today from `external_ip` + cloud connector "publicly exposed" flags
- (Optional, higher complexity, Wiz-style) reachability/attack-path context — explicitly NOT in this milestone's scope per PROJECT.md, noted as a future direction only

**4. Corroboration / provenance** (GetVul-unique, not in single-scanner vendor models)
- Distinct-source count for the same CVE-on-asset from `vulnerability_correlations` — no vendor tool has this input because none of them see another vendor's data; this is the one signal category GetVul can do that Tenable/Qualys/Rapid7 individually cannot.

**Typical combination pattern across vendors** (Qualys TruRisk is the clearest documented example): `asset_criticality_multiplier × f(severity, exploitability/threat-intel signals)`, summed/aggregated per asset, then bucketed into named risk tiers (e.g., Qualys: Low/Medium/High/Severe at 0–499/500–699/700–849/850–1000). GetVul's existing `risk_score.py` already follows this shape (severity weight × exploit × KEV multipliers → piecewise curve to 0–100); the v4.0 rebuild's most defensible path is extending that same shape with two more multiplicative/additive inputs (asset-exposure-context multiplier, corroboration bonus) and a KEV-driven floor/escalation rule, rather than inventing an unrelated formula shape.

## Part (b): "Risk Exposure" vs Raw CVSS Severity

CVSS/severity answers "how bad could this vulnerability theoretically be, in the abstract, on any asset, ignoring whether anyone is actually exploiting it." Risk exposure answers "given what's actually true about *my* environment right now, how urgently should I fix *this specific* instance." The CTEM framing (Gartner) is a widely-cited shorthand for this: **exposure ≈ weakness × reachability/exploitability × business impact**, evaluated per-instance rather than per-CVE-in-the-abstract. Concretely the same CVE-on-two-different-assets should score very differently once asset exposure context and real-world exploitation data are folded in — the *identical* finding on an air-gapped test VM vs. an internet-facing PCI-scope production host must not carry the same priority, even though CVSS is byte-identical on both. This is precisely why GetVul's existing risk_score.py already diverges from raw severity (it aggregates per-asset with multipliers) — v4.0 extends that divergence with exposure context and better exploit signals rather than introducing the concept fresh.

## Part (c): Multi-Scanner Provenance & Source Filter/Pivot UX

- **Provenance badge, not just a filter**: every mature aggregator concept (though none of Tenable/Qualys/Rapid7 are aggregators themselves — this pattern is closer to SOAR/ASOC "application vulnerability correlation" tooling and GetVul's own existing `PerSourceStatusStrip` primitive) shows a small per-scanner mark on each row so an analyst can see *at a glance* who reported it without opening the drill panel. GetVul already has the visual language for this (ConnectorMark/provider gradient tokens from Phase 14, `PerSourceStatusStrip` from Phase 11) — the provenance badge is a natural extension of an existing primitive, not a new visual system.
- **OR-default multi-select is standard faceted-filter behavior** — matches GetVul's existing chip-bar semantics for severity/status already.
- **AND-toggle for corroboration is the genuinely novel ask** here — the research found no vendor UI precedent for this exact toggle (because single-scanner vendors structurally can't need it), but the underlying concept — "convergent evidence across independent detection layers increases confidence" — is well established in the broader security-tooling literature (cross-tool correlation reduces false positives, corroborated findings carry near-certain confidence). The UX pattern that generalizes best: default chip multi-select = OR (union), a small inline toggle switch next to the source chip group = "Require ALL selected" (intersection), with the result count updating live so the analyst feels the semantic shift immediately.
- **Pivot from a finding to "show me everything else this scanner reported on this asset"** is a common expectation once provenance is visible — worth a "filter by this source" affordance directly on the badge/DrillPanel (click badge → chip-bar auto-populates that source), reusing the existing DrillPanel → chip-bar navigation pattern GetVul already has for CVE/asset drill-through.

## Part (d): Expected Analyst Behaviors — What "Good" Looks Like

- **Sort by risk-exposure, not by raw CVSS, as the default list order** — this is the entire premise of "risk-based vulnerability management" (RBVM) vs legacy CVSS-only triage; GetVul's vuln list already defaults to a risk-oriented sort (`sort_by: risk_score` default on Assets today) — v4.0 should carry that default-sort convention onto the finding-level list too once a per-finding score exists.
- **KEV / actively-exploited findings get worked first regardless of severity bucket** — matches CISA BOD 26-04 guidance and every vendor's messaging; the new model should make KEV a hard-to-ignore visual + sort escalation, not just a quiet multiplier buried in the math.
- **SLA timers driven by the new score's tier, not a static severity-only clock** — the milestone explicitly requires SLA to migrate onto the new model; "good" is an SLA that tightens automatically when a KEV/EPSS-spike/corroboration event occurs post-ingestion, not just at initial triage.
- **Analysts use source filters to build trust, not just to reduce noise** — e.g., "show me only what 2+ scanners agree on" before opening a change window, or "show me only Wiz cloud findings" when doing a cloud-specific sprint. Both are legitimate, opposite-direction uses of the same filter — reinforces why OR-default + AND-toggle (not AND-only or OR-only) is correct.
- **Overriding an auto-inferred exposure-context value is a deliberate, auditable, occasional action** — not a bulk daily chore. If analysts feel compelled to override constantly, the auto-inference is wrong and should be tuned, not that overriding is the "normal" workflow — this should be a signal GetVul's own team watches post-launch (override rate as a data-quality metric), not a designed-for-heavy-use feature.

## Feature Dependencies

```
Deeper connector enrichment (vendor-native signals persisted)
    └──requires──> per-connector parser changes (crowdstrike/nessus/wiz/qualys/rapid7/defender)
                       └──enables──> Rebuilt risk-exposure model (needs these as inputs)

Asset exposure context (auto-infer + override)
    └──requires──> existing MDM/HR/IdP enrichment fields (already shipped, ASSET-03)
    └──requires──> existing external_ip / cloud connector public-exposure flags (already shipped)
    └──enables──> Rebuilt risk-exposure model (asset-value multiplier input)
    └──enables──> Scanner-source AND-corroboration bump (optional differentiator, same model)

Rebuilt risk-exposure model (clean slate)
    └──requires──> Deeper connector enrichment (signals to consume)
    └──requires──> Asset exposure context (multiplier to consume)
    └──requires──> existing vulnerability_correlations table (corroboration-count input)
    └──enables──> SLA migration (SLA-01 recompute against new tiers)
    └──enables──> Sort-by-exposure on Vulnerabilities/Assets lists
    └──enables──> Trend-history migration (one-time recompute — HIGH complexity/risk)

Scanner-source filtering (OR default + AND toggle)
    └──requires──> existing chip-bar component pattern (Vulnerabilities already has it)
    └──requires──> existing vulnerability_correlations table (AND/intersection semantics)
    └──extends──> Assets / CSPM / Tickets screens (net-new chip-bar wiring on 3 screens)

Source-provenance badges
    └──requires──> vulnerability_correlations (source-set per finding)
    └──requires──> existing ConnectorMark / provider-gradient token system (Phase 14)
    └──enhances──> Scanner-source filtering (click-to-filter from badge)
    └──enhances──> DrillPanel (badge + "why this score" breakdown live together)

Rebuilt risk-exposure model ──conflicts with──> preserving old Asset.risk_score formula
    (explicit "clean slate, not additive" per PROJECT.md — old formula is replaced, requiring
     a one-time historical recompute so SLA/sort/trend consumers don't silently diverge)
```

### Dependency Notes

- **Rebuilt model requires deeper connector enrichment + exposure context first:** the model is only as good as its inputs; sequencing connector-signal capture and exposure-context fields *before* the model rebuild phase avoids building the formula twice.
- **Scanner-source filtering (AND toggle) requires `vulnerability_correlations`:** this table already exists and already links same-CVE-per-asset across sources — it is the single most reused piece of existing infrastructure across nearly every new v4.0 feature (AND filter, provenance badge, corroboration-as-score-input).
- **Rebuilt model conflicts with (replaces) the old formula:** this is a deliberate, explicit milestone decision (PROJECT.md: "being replaced, not augmented"). The dependency risk is entirely downstream — SLA breach detection, list sort defaults, and trend charts must all be migrated in the same phase/recompute, or GetVul will temporarily have two disagreeing "risk" numbers live at once, which is worse than either number alone.
- **Provenance badges enhance but do not require the AND toggle:** badges can ship reading straight off `vulnerability_correlations` before the AND-filter semantics exist; sequencing badges first (lower complexity, high visible payoff) ahead of the AND toggle (higher complexity) is a reasonable phase-ordering choice.

## MVP Definition

### Launch With (v1 of this milestone)

- [ ] Persist vendor-native risk/exploit signal per finding (VPR/ExPRT.AI/QDS-equivalent + EPSS percentile) in a `source_risk_signals` JSONB column, ingestion updated per connector — the model rebuild is meaningless without real inputs
- [ ] Asset exposure context fields (criticality, data sensitivity, internet-facing) with auto-infer rules + admin override + audit trail — core differentiator, explicitly scoped
- [ ] Rebuilt deterministic risk-exposure model (per-asset AND per-finding score) consuming the above + existing correlation-count — the stated milestone centerpiece
- [ ] One-time historical recompute + SLA/sort migration onto the new score — required because the old model is being replaced, not kept alongside
- [ ] Source-provenance badge on every finding row (Vulnerabilities, Assets, CSPM, Tickets) — cheap, high-trust payoff, reuses existing correlation data + visual tokens
- [ ] Scanner-source filter with OR default across all 4 screens — extends an already-proven pattern from Vulnerabilities

### Add After Validation (v1.x within this milestone)

- [ ] AND toggle for true multi-scanner corroboration — genuinely novel UX, worth shipping once the OR-filter extension across 4 screens is proven stable
- [ ] Corroboration count as an explicit scoring input (confidence/urgency bump for cross-validated findings) — depends on the model already being live; safest as a follow-on tuning pass once analysts have used the base model
- [ ] DrillPanel score breakdown ("why is this an 82") showing each contributing input — high value, but sequenced after the model itself is stable so the breakdown reflects the final formula, not a moving target

### Future Consideration (beyond this milestone)

- [ ] Wiz-style toxic-combination / attack-path reachability signals — explicitly out of current scope per PROJECT.md (no self-scanning capability, no new reachability graph); revisit only if a future milestone adds a graph/attack-path capability
- [ ] Group-scope exposure-context override UI (bulk override across an asset group, not one at a time) — real analyst-workflow value but adds precedence-rule complexity; ship per-asset override first, evaluate demand
- [ ] Compound "why exposed" call-out badges beyond the DrillPanel (e.g., a `⚠ Internet-facing · PCI · KEV` summary chip visible in list view without opening the panel) — presentation polish, defer until the underlying fields are stable

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Vendor-native signal capture (VPR/ExPRT.AI/QDS/EPSS%) | HIGH | MEDIUM | P1 |
| Asset exposure context (auto-infer + override) | HIGH | MEDIUM-HIGH | P1 |
| Rebuilt risk-exposure model (per-asset + per-finding) | HIGH | HIGH | P1 |
| SLA/sort/trend migration + historical recompute | HIGH (correctness) | HIGH | P1 |
| Source-provenance badges | MEDIUM-HIGH | LOW-MEDIUM | P1 |
| Scanner-source OR filter (Assets/CSPM/Tickets) | MEDIUM | LOW | P1 |
| Scanner-source AND toggle (corroboration) | HIGH (differentiator) | MEDIUM | P2 |
| Corroboration count as scoring input | MEDIUM-HIGH | MEDIUM | P2 |
| DrillPanel score breakdown | MEDIUM | LOW-MEDIUM | P2 |
| Group-scope exposure override | MEDIUM | MEDIUM | P3 |
| Toxic-combination / attack-path signals | LOW (out of scope) | HIGH | P3 (future milestone) |

**Priority key:**
- P1: Must have for this milestone's launch
- P2: Should have, add once P1 is proven stable
- P3: Nice to have / explicitly deferred

## Competitor Feature Analysis

| Feature | Tenable (VPR/Lumin) | Qualys (TruRisk) | Rapid7 (Active Risk) | Kenna/Cisco VM | CrowdStrike (ExPRT.AI) | Wiz | GetVul v4.0 Approach |
|---------|----------------------|-------------------|------------------------|------------------|--------------------------|-----|------------------------|
| Exploit/threat-intel signal | VPR 0.1–10, ML over 150+ features, updated daily | QDS 1–100 folds CVSS+KEV+exploit maturity | CVSSv3.1 + AttackerKB/Metasploit/ExploitDB/CISA KEV feeds | EPSS + 19 threat/exploit feeds + own SVM/random-forest model | ExPRT.AI, trained on CrowdStrike's own adversary telemetry | N/A (cloud config/identity focus, not endpoint CVE scoring) | Persist each connector's native signal (JSONB) + EPSS; feed into own deterministic formula — no in-house ML |
| Asset value input | Asset Criticality Rating (Lumin) | ACS 1–5, tag-derived, ServiceNow CMDB import | Asset "priority" via risk strategy config | Asset priority 1–10, asset groups | Not asset-scoring-focused (endpoint-agent product) | Business-impact scoring via cloud resource graph | Auto-infer criticality/sensitivity/internet-facing from existing MDM/HR/IdP + admin override |
| Score scale/range | 0.1–10 (finding-level) | 0–1000 (asset-level TruRisk), 1–100 (QDS finding-level) | 0–1000 | 0–1000 | Qualitative rating tied to CVSS-like scale | N/A | Likely keep existing 0–100 asset scale, add a comparable per-finding scale |
| Multi-scanner corroboration | N/A (single scanner) | N/A (single scanner) | N/A (single scanner) | N/A (aggregates connectors but scores per-vuln, not per-corroboration-count as far as documented) | N/A (single agent) | N/A (single platform) | Genuinely novel — GetVul's unique aggregator position; OR default + AND toggle + correlation-count scoring input |
| KEV handling | Input to VPR calc | Input to QDS/TruRisk | Direct feed input | Direct feed input | Feeds ExPRT.AI training/inference | N/A | Escalation/floor rule (not just multiplier), matching BOD 26-04 guidance |
| Exposure beyond CVE (attack path/reachability) | Limited (Lumin adds some) | EASM add-on | Not a focus | Not a focus | Not a focus | Core differentiator (toxic combinations, attack graph) | Explicitly out of scope this milestone |

## Sources

- [CVSS vs. VPR — Tenable docs](https://docs.tenable.com/vulnerability-management/Content/Explore/Findings/RiskMetrics.htm)
- [What Is VPR and How Is It Different from CVSS? — Tenable blog](https://www.tenable.com/blog/what-is-vpr-and-how-is-it-different-from-cvss)
- [Vulnerability Priority Rating — Tenable best practices](https://docs.tenable.com/vulnerability-management/best-practices/security/Content/VulnerabilityPriorityRating.htm)
- [Understanding Your TruRisk Score — Qualys docs](https://docs.qualys.com/en/vm/latest/mergedProjects/risk_score/risk_score/understanding_your_trurisk_score.htm)
- [Qualys TruRisk: QDS vs CVSS & EPSS — Qualys blog](https://blog.qualys.com/qualys-insights/2022/10/10/in-depth-look-into-data-driven-science-behind-qualys-trurisk)
- [Calculating Asset Risk Score — Qualys docs](https://docs.qualys.com/en/vmdr/latest/threat/calculating_asset_risk_score.htm)
- [Asset Criticality Score (ACS) — Qualys docs](https://docs.qualys.com/en/cs/latest/container_assets/asset_criticality_score.htm)
- [Meet the Cisco Security Risk Score (formerly Kenna Risk Score) — Cisco Blogs](https://blogs.cisco.com/security/meet-the-cisco-security-risk-score-formerly-kenna-risk-score)
- [Understanding Vulnerability, Asset and Risk Meter Scoring — Kenna FAQ](https://help.kennasecurity.com/hc/en-us/articles/4402070116116-Understanding-Vulnerability-Asset-and-Risk-Meter-Scoring)
- [What Is Kenna Security? How It Works — Kenna](https://kenna-gatsby.netlify.app/the-science-behind-kenna/)
- [How ExPRT.AI Predicts the Next Exploited Vulnerability — CrowdStrike blog](https://www.crowdstrike.com/en-us/blog/how-exprt-ai-predicts-next-exploited-vulnerability/)
- [ExPRT.AI — CrowdStrike Falcon Exposure Management product page](https://www.crowdstrike.com/en-us/platform/exposure-management/risk-prioritization/)
- [Adopting Active Risk for Vulnerability Prioritization — Rapid7 whitepaper](https://cdn.prod.website-files.com/65c5e3d44ef118c71a4ff552/66703c3c6a9692664647df8b_Rapid7%20Partner_Whitepaper_Adopting%20Active%20Risk%20for%20Vulnerability%20Prioritization_EN%20Sep%202023.pdf)
- [Working with risk strategies to analyze threats — Rapid7 docs](https://help.rapid7.com/insightvm/en-us/Files/Working_with_risk_strategies_to_analyze_threats.html)
- [What is Attack Path Analysis? — Wiz Academy](https://www.wiz.io/academy/detection-and-response/attack-path-analysis)
- [Uncover Toxic Combination of Risks in Cloud Security — Wiz blog](https://www.wiz.io/blog/the-anatomy-of-a-toxic-combination-of-risk)
- [Exposure Management in Cybersecurity Explained — Wiz Academy](https://www.wiz.io/academy/cloud-security/exposure-management-in-cybersecurity)
- [Exploit Prediction Scoring System (EPSS) — FIRST.org](https://www.first.org/epss/)
- [Exploit Prediction Scoring System (EPSS) — CrowdStrike explainer](https://www.crowdstrike.com/en-us/cybersecurity-101/exposure-management/exploit-prediction-scoring-system-epss/)
- [Reducing the Significant Risk of Known Exploited Vulnerabilities — CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities)
- [Continuous Threat Exposure Management (CTEM) — AppSecure](https://www.appsecure.security/blog/ctem-continuous-threat-exposure-management-framework)
- [Automating SLAs in Risk-Based Vulnerability Management — Nucleus Security blog](https://nucleussec.com/blog/automating-slas-rbvm/)
- [Best Practices for Asset Tagging in Vulnerability Scanner — Device42](https://www.device42.com/vulnerability-management-best-practices/asset-tagging-in-vulnerability-scanner/)
- [The Critical Role of the CMDB in Security and Vulnerability Management — Ivanti](https://www.ivanti.com/blog/the-critical-role-of-the-cmdb-in-security-and-vulnerability-management)
- GetVul codebase (read directly): `backend/app/assets/risk_score.py`, `backend/app/vulnerabilities/models.py`, `backend/app/assets/models.py`, `backend/app/vulnerabilities/correlation_service.py`, `frontend/src/components/vulnerabilities/chip-bar.tsx`

---
*Feature research for: Enriched risk-exposure model + scanner-source-aware triage (GetVul v4.0)*
*Researched: 2026-08-04*
