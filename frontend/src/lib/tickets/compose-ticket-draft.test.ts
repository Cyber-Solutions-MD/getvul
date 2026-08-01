import { describe, it, expect } from 'vitest';
import { composeTicketTitle, composeTicketDescription } from './compose-ticket-draft';
import type { CacheSection } from './compose-ticket-draft';

// Phase 27 (AID-01, Plan 02): pure-function permutation tests for the
// ticket auto-draft composer. Plain Vitest, zero DOM/@testing-library --
// mirrors frontend/src/lib/queries/keys.test.ts's shape (the closest
// no-DOM pure-function precedent in this codebase), not drill-panel.test.tsx's
// DOM-heavy style (27-PATTERNS.md).

describe('composeTicketTitle', () => {
  it('formats as "[{sevLabel}] {cveLabel} on {hostsLine}" (D-01 deterministic, zero AI call)', () => {
    expect(
      composeTicketTitle({
        sevLabel: 'Critical',
        cveLabel: 'CVE-2026-1234',
        hostsLine: 'web-01.internal',
      }),
    ).toBe('[Critical] CVE-2026-1234 on web-01.internal');
  });

  it('mirrors the exact backend service.py:202 convention even with placeholder slots', () => {
    expect(
      composeTicketTitle({ sevLabel: 'Medium', cveLabel: 'CVE-2026-9999', hostsLine: '—' }),
    ).toBe('[Medium] CVE-2026-9999 on —');
  });

  it('joins a multi-host hostsLine verbatim (no truncation) -- the caller already joined it', () => {
    expect(
      composeTicketTitle({
        sevLabel: 'High',
        cveLabel: 'CVE-2026-0001',
        hostsLine: 'web-01.internal, web-02.internal, db-03.internal',
      }),
    ).toBe('[High] CVE-2026-0001 on web-01.internal, web-02.internal, db-03.internal');
  });
});

describe('composeTicketDescription', () => {
  const baseAsset = {
    hostsLine: 'web-01.internal',
    affectedProduct: 'nginx 1.24',
    sevLabel: 'Critical',
    cisaKev: false,
    exploitAvailable: false,
  };

  it('all three caches null -> ONLY the "Asset context:" section renders (D-04: no AI dependency)', () => {
    const result = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
    });
    expect(result).toBe(
      'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical',
    );
    expect(result).not.toContain('Description:');
    expect(result).not.toContain('Remediation:');
    expect(result).not.toContain('Prioritization:');
  });

  it('explain grounded -> "Description:" section present, separated from Asset context by exactly one blank line', () => {
    const explain: CacheSection = { grounded: true, summary: 'Plain-English explanation of the CVE.' };
    const result = composeTicketDescription({
      explain,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
    });
    expect(result).toBe(
      'Description:\nPlain-English explanation of the CVE.\n\n' +
        'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical',
    );
  });

  it('remediationGuidance grounded -> "Remediation:" section present', () => {
    const remediationGuidance: CacheSection = { grounded: true, summary: 'Upgrade nginx to 1.25.3.' };
    const result = composeTicketDescription({
      explain: null,
      remediationGuidance,
      prioritization: null,
      ...baseAsset,
    });
    expect(result).toBe(
      'Remediation:\nUpgrade nginx to 1.25.3.\n\n' +
        'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical',
    );
  });

  it('explain + remediationGuidance both grounded -> Description, then Remediation, then Asset context (canonical order)', () => {
    const explain: CacheSection = { grounded: true, summary: 'Summary text.' };
    const remediationGuidance: CacheSection = { grounded: true, summary: 'Remediation text.' };
    const result = composeTicketDescription({
      explain,
      remediationGuidance,
      prioritization: null,
      ...baseAsset,
    });
    expect(result).toBe(
      'Description:\nSummary text.\n\n' +
        'Remediation:\nRemediation text.\n\n' +
        'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical',
    );
  });

  it('a cached-but-NOT-grounded ({grounded:false}) section is OMITTED ENTIRELY -- never a labeled-but-empty stub', () => {
    const explain: CacheSection = { grounded: false, summary: 'Should never appear anywhere in the output.' };
    const remediationGuidance: CacheSection = { grounded: false, summary: 'Also should never appear.' };
    const result = composeTicketDescription({
      explain,
      remediationGuidance,
      prioritization: null,
      ...baseAsset,
    });
    expect(result).not.toContain('Description:');
    expect(result).not.toContain('Remediation:');
    expect(result).not.toContain('Should never appear');
    expect(result).not.toContain('Also should never appear');
    expect(result).toBe(
      'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical',
    );
  });

  it('prioritization grounded -> appended LAST, after Asset context', () => {
    const prioritization: CacheSection = {
      grounded: true,
      summary: 'Fix this first -- internet-facing + CISA KEV.',
    };
    const result = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization,
      ...baseAsset,
    });
    expect(result).toBe(
      'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical\n\n' +
        'Prioritization:\nFix this first -- internet-facing + CISA KEV.',
    );
  });

  it('prioritization null or ungrounded -> OMITTED ENTIRELY (this phase never gap-fills prioritization)', () => {
    const ungrounded: CacheSection = { grounded: false, summary: 'n/a' };
    const withNull = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
    });
    const withUngrounded = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: ungrounded,
      ...baseAsset,
    });
    expect(withNull).not.toContain('Prioritization:');
    expect(withUngrounded).not.toContain('Prioritization:');
  });

  it('all four sections present at once, in canonical order, separated by exactly one blank line each (no triple-newline)', () => {
    const explain: CacheSection = { grounded: true, summary: 'S1' };
    const remediationGuidance: CacheSection = { grounded: true, summary: 'S2' };
    const prioritization: CacheSection = { grounded: true, summary: 'S3' };
    const result = composeTicketDescription({ explain, remediationGuidance, prioritization, ...baseAsset });
    expect(result).toBe(
      'Description:\nS1\n\n' +
        'Remediation:\nS2\n\n' +
        'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical\n\n' +
        'Prioritization:\nS3',
    );
    expect(result).not.toContain('\n\n\n');
  });

  it('cisaKev true adds a "CISA KEV: yes" line inside Asset context; false omits it entirely', () => {
    const withKev = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
      cisaKev: true,
    });
    expect(withKev).toContain('CISA KEV: yes');

    const withoutKev = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
      cisaKev: false,
    });
    expect(withoutKev).not.toContain('CISA KEV');
  });

  it('exploitAvailable true adds an "Exploit available: yes" line; false omits it entirely', () => {
    const withExploit = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
      exploitAvailable: true,
    });
    expect(withExploit).toContain('Exploit available: yes');

    const withoutExploit = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
      exploitAvailable: false,
    });
    expect(withoutExploit).not.toContain('Exploit available');
  });

  it('both cisaKev and exploitAvailable true -> both lines present, in order, beneath Severity', () => {
    const result = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
      cisaKev: true,
      exploitAvailable: true,
    });
    expect(result).toBe(
      'Asset context:\nHost: web-01.internal\nProduct: nginx 1.24\nSeverity: Critical\n' +
        'CISA KEV: yes\nExploit available: yes',
    );
  });

  it('affectedProduct null renders "Product: —" (never omits the line, never crashes)', () => {
    const result = composeTicketDescription({
      explain: null,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
      affectedProduct: null,
    });
    expect(result).toContain('Product: —');
  });

  it('never reads business_risk -- only summary feeds any section (T-27-05 -- source file also has zero references)', () => {
    // CacheSection only ever carries {grounded, summary}; even if a caller
    // (incorrectly) constructed a shape resembling ExplainResponseBase, this
    // function still never reads a business_risk field, and the acceptance
    // grep (`grep -c 'business_risk' compose-ticket-draft.ts` == 0) proves
    // the source itself has zero occurrences.
    const explain = { grounded: true, summary: 'Only this should appear.' } as CacheSection;
    const result = composeTicketDescription({
      explain,
      remediationGuidance: null,
      prioritization: null,
      ...baseAsset,
    });
    expect(result).toContain('Only this should appear.');
    expect(result).not.toContain('business_risk');
  });
});
