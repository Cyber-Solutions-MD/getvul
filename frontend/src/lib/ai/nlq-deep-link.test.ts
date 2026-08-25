import { describe, it, expect } from 'vitest';
import { buildNlqDeepLink } from './nlq-deep-link';

describe('buildNlqDeepLink (D-17 — the loop-closing read-only deep-link)', () => {
  it('builds the vulnerabilities deep-link with the exact D-17 param names', () => {
    const href = buildNlqDeepLink('vulnerabilities', {
      cisa_kev: true,
      age_days_min: 30,
      asset_internet_facing: true,
    });
    expect(href).toBe(
      '/dashboard/vulnerabilities?cisa_kev=true&age_days_min=30&asset_internet_facing=true'
    );
  });

  it('serializes vulnerabilities severity/status list fields as repeated params', () => {
    const href = buildNlqDeepLink('vulnerabilities', {
      severity: ['critical', 'high'],
      status: ['OPEN'],
    });
    expect(href).toBe('/dashboard/vulnerabilities?severity=critical&severity=high&status=OPEN');
  });

  it('serializes sla_breached and exploit_available booleans as literal true/false', () => {
    const href = buildNlqDeepLink('vulnerabilities', {
      sla_breached: true,
      exploit_available: false,
    });
    expect(href).toBe('/dashboard/vulnerabilities?sla_breached=true&exploit_available=false');
  });

  it('omits null/undefined fields entirely', () => {
    const href = buildNlqDeepLink('vulnerabilities', {
      cisa_kev: true,
      age_days_min: undefined,
      sla_breached: null,
    });
    expect(href).toBe('/dashboard/vulnerabilities?cisa_kev=true');
  });

  it('falls back to the bare route when the filter is empty', () => {
    expect(buildNlqDeepLink('vulnerabilities', {})).toBe('/dashboard/vulnerabilities');
  });

  it('maps assets device_category -> the list page\'s "category" param and internet_facing verbatim', () => {
    const href = buildNlqDeepLink('assets', {
      device_category: 'SERVER',
      internet_facing: true,
    });
    expect(href).toBe('/dashboard/assets?category=SERVER&internet_facing=true');
  });

  it('maps tickets resolved_asset_id -> the list page\'s "asset_id" param', () => {
    const href = buildNlqDeepLink('tickets', {
      status: 'open',
      resolved_asset_id: 'a1b2c3d4-0000-0000-0000-000000000000',
    });
    expect(href).toBe(
      '/dashboard/tickets?status=open&asset_id=a1b2c3d4-0000-0000-0000-000000000000'
    );
  });

  it('drops tickets asset_hostname — it is not a URL param the list page reads (superseded by resolved_asset_id)', () => {
    const href = buildNlqDeepLink('tickets', {
      status: 'open',
      asset_hostname: 'prod-db-01',
    });
    expect(href).toBe('/dashboard/tickets?status=open');
  });

  it('an unresolvable hostname (no resolved_asset_id) still returns a valid tickets deep-link with only status', () => {
    const href = buildNlqDeepLink('tickets', {
      status: null,
      asset_hostname: 'does-not-exist-anywhere',
      resolved_asset_id: null,
    });
    expect(href).toBe('/dashboard/tickets');
  });
});
