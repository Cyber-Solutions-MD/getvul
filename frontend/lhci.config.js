// lhci.config.js — Lighthouse CI mobile gate (Plan 15-06 Task 2)
//
// Asserts >= 90 performance AND >= 90 accessibility on /login + /dashboard.
// Mobile preset: emulates Moto G4, 150ms RTT, 1.6 Mbps, 4x CPU slowdown.
//
// Usage (requires a built + started Next.js server OR let lhci manage it):
//   npm run perf:lh   →  lhci autorun --config=lhci.config.js
//
// Server lifecycle (Pitfall 4 from 15-RESEARCH.md):
//   lhci collect runs startServerCommand ('npm run start') and waits for
//   startServerReadyPattern ('ready') before hitting the URLs. The server
//   must NOT already be running on :3000 when lhci starts — it manages
//   the lifecycle and tears it down after collecting.
//
// Raw JSON results are written to ./lighthouse-results/ (gitignored per Plan 01).
// Only the curated scores go into .planning/.../15-PERF-REPORT.md.
//
// Threat model (T-15-11 / T-15-12): lighthouse-results/ raw output may capture
// page HTML including auth UI — it is gitignored. The committed report records
// only route names, byte sizes, and Lighthouse scores; no credentials.

'use strict';

module.exports = {
  ci: {
    collect: {
      numberOfRuns: 1,
      startServerCommand: 'npm run start',
      startServerReadyPattern: 'ready',
      url: [
        'http://localhost:3000/login',
        'http://localhost:3000/dashboard',
      ],
      settings: {
        preset: 'perf',
        formFactor: 'mobile',
        throttling: {
          rttMs: 150,
          throughputKbps: 1600,
          cpuSlowdownMultiplier: 4,
        },
      },
    },
    assert: {
      assertions: {
        'categories:performance': ['error', { minScore: 0.9 }],
        'categories:accessibility': ['error', { minScore: 0.9 }],
      },
    },
    upload: {
      target: 'filesystem',
      outputDir: './lighthouse-results',
    },
  },
};
