#!/usr/bin/env node
// check-bundle-all.mjs — D-08 all-routes bundle budget enforcer (Plan 15-06 Task 1)
//
// Parses `next build` output, finds EVERY route line, and asserts each route's
// "First Load JS" is <= 250 KB gzipped (256000 bytes).
//
// Usage:
//   node scripts/check-bundle-all.mjs
//   next build | node scripts/check-bundle-all.mjs
//
// Exit codes:
//   0 — all routes within budget
//   1 — one or more routes exceed 250 KB (or no routes parsed — defensive)
//   2 — build failure (next build exited non-zero) OR stdin was empty/piped
//       with zero bytes (defensive: a parse miss must NOT silently pass)
//
// Reuses parseRouteLine internals from check-bundle.mjs:
//   - stripAnsi(s) = s.replace(/\x1b\[[0-9;]*m/g,'')
//   - size-token regex: /(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(kB|MB|B)\b/g
//   - LAST-token = First Load JS heuristic
//   - 1024 multiplier (kB = 1024 B)
//
// Known routes that next build emits:
//   /, /login, /dashboard, /dashboard/vulnerabilities, /dashboard/assets,
//   /dashboard/assets/[id], /dashboard/tickets, /dashboard/tickets/[id],
//   /dashboard/tickets/rules, /dashboard/cspm, /dashboard/connectors,
//   /dashboard/users, /dashboard/settings, /dev/primitives
//
// The per-route "First Load JS" already includes the shared bundle (~87 kB).
// Budget is applied to the TOTAL (shared + per-route) for each route.

import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import process from 'node:process';

// ─── Constants ────────────────────────────────────────────────────────────────

const MAX_KB = 250;
const MAX_BYTES = MAX_KB * 1024; // 256000 bytes

// ─── Utilities (reused from check-bundle.mjs) ─────────────────────────────────

/** Strip ANSI color/style escape sequences from a string. */
function stripAnsi(s) {
  return s.replace(/\x1b\[[0-9;]*m/g, '');
}

/**
 * Extract all size tokens from a line using the tightened regex from check-bundle.mjs.
 * The negative lookbehind prevents matching the 'B' inside 'kB' as a standalone token.
 *
 * @param {string} line - A single line of (ANSI-stripped) next build output.
 * @returns {RegExpMatchArray[]} Array of match objects [fullMatch, num, unit].
 */
function extractSizeTokens(line) {
  return [...line.matchAll(/(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(kB|MB|B)\b/g)];
}

/**
 * Convert a parsed size token to bytes using the 1024 multiplier.
 * Matches Next.js display convention where kB = 1024 bytes.
 *
 * @param {string} num  - Numeric string (e.g., "180.5").
 * @param {string} unit - Unit string (kB|MB|B, case-insensitive).
 * @returns {number} Size in bytes.
 */
function toBytes(num, unit) {
  const n = Number(num);
  const u = unit.toLowerCase();
  if (u === 'mb') return n * 1024 * 1024;
  if (u === 'kb') return n * 1024;
  return n; // 'b'
}

// ─── Build output reader ───────────────────────────────────────────────────────

/**
 * Read next build output:
 * - If stdin is piped (not a TTY), read it.
 * - Otherwise invoke `npx next build` and capture stdout.
 *
 * Exits with code 2 on build failure.
 *
 * @returns {string} Raw build output text.
 */
function readBuildOutput() {
  if (!process.stdin.isTTY) {
    try {
      const data = readFileSync(0, 'utf-8');
      if (data && data.trim().length > 0) return data;
    } catch {
      // Fall through to invoking next build
    }
  }
  try {
    return execSync('npx next build', {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'inherit'],
    });
  } catch {
    console.error('check-bundle-all: next build failed — exiting 2');
    process.exit(2);
  }
  // Unreachable — keeps type-checker happy
  return '';
}

// ─── Route-line parser ─────────────────────────────────────────────────────────

/**
 * Parse every route line from stripped next build output.
 *
 * Next.js 15 build output shape:
 *   Route (app)                              Size      First Load JS
 *   ┌ ○ /                                    1.2 kB    178 kB
 *   ├ ○ /dashboard                           5.4 kB    178 kB
 *   ├ ƒ /dashboard/assets/[id]               3.1 kB    195 kB
 *   └ ○ /login                               2.1 kB    145 kB
 *   + First Load JS shared by all            87 kB
 *
 * Strategy:
 *   1. Split output into lines.
 *   2. For each line, check if a route token starting with '/' appears as a
 *      standalone word (preceded by whitespace/tree chars, followed by space or EOL).
 *   3. Skip the "+ First Load JS shared by all" footer (starts with '+').
 *   4. Extract ALL size tokens; take the LAST one = First Load JS column.
 *
 * @param {string} strippedOutput - ANSI-stripped next build output.
 * @returns {{ route: string, bytes: number, line: string }[]} Parsed routes.
 */
function parseAllRouteLines(strippedOutput) {
  const lines = strippedOutput.split('\n');
  const results = [];

  // Route lines have a path token starting with '/' that is preceded by whitespace
  // or tree-drawing chars (┌ ├ └ ─ │) and followed by whitespace or end-of-line.
  // We detect the route token and exclude the "shared by all" footer lines.
  const routeLineRegex = /(?:^|[\s│├└─┌○●ƒλ◌])(\/[^\s]*)(?=\s|$)/;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.length === 0) continue;
    // Skip the "First Load JS shared by all" summary footer line.
    // This line contains the literal "shared by all" — it is NOT a route line
    // even though it may start with '+' (a tree/bullet char in some output formats).
    if (trimmed.includes('shared by all')) continue;

    const routeMatch = routeLineRegex.exec(line);
    if (!routeMatch) continue;

    const route = routeMatch[1];

    // Only accept lines where the route looks like a valid path
    if (!route.startsWith('/')) continue;

    const tokens = extractSizeTokens(line);
    if (tokens.length === 0) continue;

    // Warn on unexpected token count (Next.js 15 has exactly 2: route Size + First Load JS)
    if (tokens.length > 2) {
      process.stderr.write(
        `[check-bundle-all] WARN: route line has ${tokens.length} size tokens ` +
          `(expected 2). LAST-token heuristic may misread First Load JS.\n` +
          `  Line: ${line.trim()}\n`
      );
    }

    // LAST token = First Load JS column
    const last = tokens[tokens.length - 1];
    const bytes = toBytes(last[1], last[2]);

    results.push({ route, bytes, line: line.trim() });
  }

  return results;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const raw = readBuildOutput();
const output = stripAnsi(raw);
const routes = parseAllRouteLines(output);

// Exit 2 if zero route lines parsed — a parse miss must NOT silently pass.
if (routes.length === 0) {
  console.error(
    'check-bundle-all: no route lines found in build output — ' +
      'check that `next build` produced output and try again.'
  );
  process.exit(2);
}

// Evaluate each route against the budget.
const failures = [];
let maxRoute = routes[0];

for (const r of routes) {
  const kb = (r.bytes / 1024).toFixed(1);
  const status = r.bytes <= MAX_BYTES ? 'PASS' : 'FAIL';

  // Track the largest route for the summary footer.
  if (r.bytes > maxRoute.bytes) maxRoute = r;

  if (r.bytes > MAX_BYTES) {
    failures.push(r);
    console.log(`FAIL  ${r.route}  ${kb} kB  (budget: ${MAX_KB} kB)`);
  } else {
    console.log(`PASS  ${r.route}  ${kb} kB`);
  }
}

// Summary footer
const maxKb = (maxRoute.bytes / 1024).toFixed(1);
console.log('');
console.log(`Routes checked: ${routes.length}`);
console.log(`Largest route:  ${maxRoute.route}  ${maxKb} kB`);
console.log(`Budget:         ${MAX_KB} kB gzipped per route (First Load JS)`);

if (failures.length > 0) {
  console.error('');
  console.error(
    `check-bundle-all: FAIL — ${failures.length} route(s) exceed the ${MAX_KB} kB budget:`
  );
  for (const f of failures) {
    const kb = (f.bytes / 1024).toFixed(1);
    console.error(`  ${f.route}  ${kb} kB`);
  }
  process.exit(1);
}

console.log('');
console.log(`check-bundle-all: OK — all ${routes.length} routes within ${MAX_KB} kB budget.`);
process.exit(0);
