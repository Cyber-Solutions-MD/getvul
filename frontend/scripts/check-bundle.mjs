#!/usr/bin/env node
// check-bundle.mjs — D-Perf-01 enforcer (Plan 10-04 Task 3)
//
// Parses `next build` output, finds the row for --route (e.g., /dashboard),
// reads the "First Load JS" column value, compares against --max-kb * 1024.
//
// Usage:
//   node scripts/check-bundle.mjs --route /dashboard --max-kb 180
//   next build | node scripts/check-bundle.mjs --route /dashboard --max-kb 180
//
// Exit codes:
//   0 — within budget
//   1 — over budget
//   2 — route not found in build output (or invalid args / build failure)
//
// Pitfall 4: the "First Load JS" column on the per-route row is the value
// we want, NOT the "First Load JS shared by all" footer at the bottom of
// the build output. The parser anchors on the route token and reads the
// last `<num> <unit>B` token on the same line.

import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import process from 'node:process';

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--route') args.route = argv[++i];
    else if (argv[i] === '--max-kb') args.maxKb = Number(argv[++i]);
  }
  if (!args.route) {
    console.error('check-bundle: --route is required (e.g., --route /dashboard)');
    process.exit(2);
  }
  if (!args.maxKb || Number.isNaN(args.maxKb)) {
    console.error('check-bundle: --max-kb is required (integer kilobytes)');
    process.exit(2);
  }
  return args;
}

function readBuildOutput() {
  // If stdin is piped (not a TTY), read it. Otherwise run `next build` directly.
  if (!process.stdin.isTTY) {
    try {
      const data = readFileSync(0, 'utf-8');
      if (data && data.trim().length > 0) return data;
    } catch {
      // fall through to invoking next build
    }
  }
  try {
    return execSync('npx next build', {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'inherit'],
    });
  } catch {
    console.error('check-bundle: next build failed');
    process.exit(2);
  }
  // unreachable but keeps the type-checker happy
  return '';
}

function parseRouteLine(output, route) {
  // Next.js 15 build output (per Pitfall 4):
  //   Route (app)                              Size      First Load JS
  //   ┌ ○ /                                    1.2 kB    178 kB
  //   ├ ○ /dashboard                           5.4 kB    178 kB
  //   └ ○ /login                               2.1 kB    145 kB
  //   + First Load JS shared by all            87 kB
  //
  // The route token may be preceded by a tree-drawing char (┌ ├ └) and ○/●/λ.
  // Strategy:
  //   1. Strip ANSI escape codes.
  //   2. For each line: check if a route token "<route>" appears with a
  //      word/whitespace boundary on the trailing side.
  //   3. Extract all "<num> kB|MB|B" tokens; take the LAST one (= First Load JS).
  const stripAnsi = (s) => s.replace(/\x1b\[[0-9;]*m/g, '');
  const lines = stripAnsi(output).split('\n');
  // Escape regex specials in the route (mainly '/').
  const routeEscaped = route.replace(/[.*+?^${}()|[\]\\\/]/g, '\\$&');
  // Match the route as a standalone token: preceded by whitespace or
  // line-start (post tree-char/icon stripping is implicit via \s), followed
  // by whitespace or end. Allow tree chars (│├└─┌) to count as whitespace.
  const routeRegex = new RegExp(`(?:^|[\\s│├└─┌])${routeEscaped}(?=\\s|$)`);
  for (const line of lines) {
    if (routeRegex.test(line)) {
      const tokens = [...line.matchAll(/(\d+(?:\.\d+)?)\s*(kB|MB|B)\b/gi)];
      if (tokens.length >= 1) {
        // Use the LAST token on the row — that's the First Load JS column.
        const last = tokens[tokens.length - 1];
        const num = Number(last[1]);
        const unit = last[2].toLowerCase();
        // 1024 multiplier — match Next.js's display convention (kB = 1024 B).
        const bytes =
          unit === 'mb' ? num * 1024 * 1024 : unit === 'kb' ? num * 1024 : num;
        return { line: line.trim(), bytes };
      }
    }
  }
  return null;
}

const args = parseArgs(process.argv.slice(2));
const output = readBuildOutput();
const match = parseRouteLine(output, args.route);

if (!match) {
  console.error(
    `check-bundle: could not find route ${args.route} in build output.`,
  );
  process.exit(2);
}

const budgetBytes = args.maxKb * 1024;
const kb = (match.bytes / 1024).toFixed(1);
const budgetKb = args.maxKb.toFixed(1);

if (match.bytes > budgetBytes) {
  console.error(
    `check-bundle: FAIL — ${args.route} First-Load JS is ${kb} kB (> ${budgetKb} kB budget)`,
  );
  console.error(`  parsed line: ${match.line}`);
  process.exit(1);
}

console.log(
  `check-bundle: OK — ${args.route} First-Load JS is ${kb} kB (<= ${budgetKb} kB budget)`,
);
process.exit(0);
