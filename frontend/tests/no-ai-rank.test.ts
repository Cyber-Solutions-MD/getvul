/**
 * no-ai-rank.test.ts -- the literal, grep-provable "no AI rank anywhere in
 * the UI" CI check (ROADMAP SC2 / Pitfall #7, T-26-02). 26-UI-SPEC.md's
 * No-Rank UI Contract requires that no new sort control, list/table column,
 * or standalone numeric badge referencing an AI-derived priority/rank is
 * EVER introduced -- the deterministic ASSET-02 score stays the one
 * sortable/authoritative number everywhere. This is the artifact Phase 28's
 * audit re-checks.
 *
 * Mechanism (26-PATTERNS.md "No Analog Found": no file-shaped analog exists
 * for a repo-wide static rule, so this plan wires it as a Vitest fs-based
 * test rather than a documented manual pre-merge check). Recursively scans
 * every `frontend/src/components/**\/*.tsx` and `frontend/src/lib/queries/
 * **\/*.ts` file. For each line, after skipping comment-only lines:
 *
 *   1. `ai_score` / `aiPriority` / `aiRank` (and their snake_case/camelCase
 *      siblings, e.g. `ai_priority`, `aiScore`) are ALWAYS forbidden, in
 *      ANY context -- code or string -- because there is no legitimate
 *      reason a UI-layer file should ever name an AI-derived rank/score
 *      identifier at all (the response schema this phase ships carries no
 *      such field, per D-03; if one ever showed up here, that alone is the
 *      violation, regardless of whether it's a variable name or a label).
 *   2. The bare words `priority` / `rank` are forbidden only as CODE-LEVEL
 *      constructs (identifiers, object keys, JSX tag/attribute structure)
 *      -- never inside a quoted string literal's CONTENTS, which is where
 *      this very phase's own locked prose lives ("Explain the priority",
 *      "Not enough signal to explain priority reliably" -- human-readable
 *      copy inside a card, not a column/sort-key). Quoted-string contents
 *      are stripped before this half of the scan runs.
 *
 * The ONE known pre-existing exception this baseline allowlists (scoped by
 * file + exact identifier, not a blanket per-file exemption, so a genuinely
 * NEW violation added anywhere else in the same file would still be
 * caught): `watcher-stack.tsx`'s `ROLE_PRIORITY` role-strength dedupe map
 * (UX-05-05) -- a ticket-watcher role tiebreaker (assignee/reporter/
 * watcher), not an AI-generated number.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'fs';
import { join, relative } from 'path';

const FRONTEND_SRC = join(__dirname, '..', 'src');

const SCAN_ROOTS: Array<{ dir: string; exts: string[] }> = [
  { dir: join(FRONTEND_SRC, 'components'), exts: ['.tsx'] },
  { dir: join(FRONTEND_SRC, 'lib', 'queries'), exts: ['.ts'] },
];

// {file, pattern} -- the pre-existing, reviewed-benign exception. Scoped to
// the exact identifier inside the exact file, never the whole file, per
// 26-UI-SPEC.md's "Executor-facing check" (the known-allowed exception is
// watcher-stack.tsx's role-priority comment/identifier).
const ALLOWLIST: ReadonlyArray<{ file: string; pattern: RegExp }> = [
  { file: 'components/tickets/watcher-stack.tsx', pattern: /ROLE_PRIORITY/ },
];

// Group 1: always forbidden, any context (code or string). Matches both
// snake_case (ai_score, ai_priority, ai_rank) and camelCase (aiScore,
// aiPriority, aiRank) -- the plan's literal list is ai_score/aiPriority/
// aiRank; the sibling casings are included defensively since they carry the
// identical meaning and no current file uses any of them (verified empty).
const FORBIDDEN_AI_IDENTIFIER = /\bai_?(score|priority|rank)\b/i;

// Group 2: forbidden only as bare code (never inside a string literal's
// contents) -- checked against the STRING-STRIPPED line.
const FORBIDDEN_BARE_WORD = /priority|rank/i;

// `entry` below is a directory-entry name returned by readdirSync() over
// this repo's own fixed, local src/ tree at test time (never `.`/`..`,
// never external/user input) -- there is no attacker-controlled string
// reaching join() here, so the generic path-traversal rule is a false
// positive on this specific static, non-request-scoped walk.
function walk(dir: string, exts: string[], out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    // nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      walk(full, exts, out);
    } else if (exts.some((ext) => entry.endsWith(ext))) {
      out.push(full);
    }
  }
  return out;
}

// Heuristic, not a full TS/JSX parser -- deliberately simple, sufficient
// for a static CI gate over a known, reviewed codebase. Blanks out the
// CONTENTS of single/double/template-quoted strings (keeping the quotes
// themselves as placeholders) so human-readable copy never reaches the
// bare-word scan below.
function stripStringLiteralContents(line: string): string {
  return line
    .replace(/'(?:[^'\\]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""')
    .replace(/`(?:[^`\\]|\\.)*`/g, '``');
}

function isCommentOnlyLine(trimmed: string): boolean {
  return (
    trimmed.length === 0 ||
    trimmed.startsWith('//') ||
    trimmed.startsWith('/*') ||
    trimmed.startsWith('*') ||
    trimmed.startsWith('{/*') ||
    trimmed === '*/'
  );
}

type Flag = { file: string; line: number; text: string };

function scanFile(absPath: string): Flag[] {
  const relPath = relative(FRONTEND_SRC, absPath).split('\\').join('/');
  const lines = readFileSync(absPath, 'utf-8').split('\n');
  const flags: Flag[] = [];

  lines.forEach((raw, idx) => {
    const trimmed = raw.trim();
    if (isCommentOnlyLine(trimmed)) return;

    const isAllowlisted = ALLOWLIST.some((a) => relPath === a.file && a.pattern.test(raw));
    if (isAllowlisted) return;

    const bareCode = stripStringLiteralContents(raw);
    if (FORBIDDEN_AI_IDENTIFIER.test(raw) || FORBIDDEN_BARE_WORD.test(bareCode)) {
      flags.push({ file: relPath, line: idx + 1, text: trimmed });
    }
  });

  return flags;
}

describe('No-Rank UI Contract (ROADMAP SC2 / Pitfall #7, T-26-02)', () => {
  it('the scan actually finds files (sanity -- a misconfigured glob must not silently pass vacuously)', () => {
    const files = SCAN_ROOTS.flatMap((root) => walk(root.dir, root.exts));
    expect(files.length).toBeGreaterThan(50);
  });

  it('zero NEW ai_score/aiPriority/aiRank/priority/rank identifiers exist across components/** and lib/queries/** beyond the allowlisted baseline', () => {
    const files = SCAN_ROOTS.flatMap((root) => walk(root.dir, root.exts));
    const flags = files.flatMap(scanFile);
    expect(flags).toEqual([]);
  });

  it('the allowlisted exception (watcher-stack.tsx ROLE_PRIORITY) is real and still present -- proves the allowlist is scoped, not vacuous', () => {
    const watcherStackPath = join(FRONTEND_SRC, 'components', 'tickets', 'watcher-stack.tsx');
    const contents = readFileSync(watcherStackPath, 'utf-8');
    expect(contents).toMatch(/ROLE_PRIORITY/);
  });

  it('the AI response schema surface this phase ships (ExplainVulnResponse/AiExplanationCitations) carries no rank/priority/score field of its own', () => {
    // Defense-in-depth companion to the backend's own schema-level
    // enforcement (ExplainResponseBase has no numeric field at all,
    // 26-PATTERNS.md "No-Rank enforcement is structural") -- this proves
    // the FRONTEND type mirror never re-introduces one either.
    const streamHookPath = join(FRONTEND_SRC, 'lib', 'ai', 'use-explain-stream.ts');
    const contents = readFileSync(streamHookPath, 'utf-8');
    expect(contents).not.toMatch(FORBIDDEN_AI_IDENTIFIER);
  });
});
