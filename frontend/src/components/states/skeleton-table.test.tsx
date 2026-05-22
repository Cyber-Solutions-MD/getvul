// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { axe } from 'vitest-axe';

// Wave 1 (Plan 11-04) will create this file. Import is the RED signal.
import {
  SkeletonTable,
  type SkeletonColumn,
} from './skeleton-table';

const fourColumns: SkeletonColumn[] = [
  { kind: 'pill', width: 80 },
  { kind: 'mono', width: 130 },
  { kind: 'text', width: 200 },
  { kind: 'badge', width: 60 },
];

describe('<SkeletonTable> (D-S-01 — column-aware shimmer loader)', () => {
  it('renders default 8 rows when rows prop omitted', () => {
    const { container } = render(<SkeletonTable columns={fourColumns} />);
    // Each row is a flex container with N column cells; assert via row count
    const rows = container.querySelectorAll('[data-skeleton-row]');
    expect(rows.length).toBe(8);
  });

  it('honors explicit rows={5}', () => {
    const { container } = render(
      <SkeletonTable rows={5} columns={fourColumns} />
    );
    const rows = container.querySelectorAll('[data-skeleton-row]');
    expect(rows.length).toBe(5);
  });

  it('renders one cell per column descriptor with width matching columns[i].width', () => {
    const { container } = render(
      <SkeletonTable rows={1} columns={fourColumns} />
    );
    const cells = container.querySelectorAll('[data-skeleton-cell]');
    expect(cells.length).toBe(fourColumns.length);
    fourColumns.forEach((col, i) => {
      const cell = cells[i] as HTMLElement;
      // Width can land as inline style or class — assert the value is reachable
      expect(cell.style.width || '').toContain(String(col.width));
    });
  });

  it("kind='pill' renders rounded-full chrome; kind='mono'/'text'/'badge' render rounded rect", () => {
    const { container } = render(
      <SkeletonTable rows={1} columns={fourColumns} />
    );
    const cells = container.querySelectorAll('[data-skeleton-cell]');
    expect((cells[0] as HTMLElement).className).toMatch(/rounded-full/);
    // mono / text / badge do NOT carry rounded-full
    expect((cells[1] as HTMLElement).className).not.toMatch(/rounded-full/);
    expect((cells[2] as HTMLElement).className).not.toMatch(/rounded-full/);
    expect((cells[3] as HTMLElement).className).not.toMatch(/rounded-full/);
    // mono / text / badge still carry a rounded class (md/sm)
    expect((cells[1] as HTMLElement).className).toMatch(/rounded/);
    expect((cells[2] as HTMLElement).className).toMatch(/rounded/);
    expect((cells[3] as HTMLElement).className).toMatch(/rounded/);
  });

  it('shimmer is gated by motion-safe:animate-shimmer (className literal — CSS gate is global)', () => {
    const { container } = render(
      <SkeletonTable rows={1} columns={fourColumns} />
    );
    const cells = container.querySelectorAll('[data-skeleton-cell]');
    // At least one cell has the gated class — pattern enforced per-cell
    const someHasShimmer = Array.from(cells).some((c) =>
      (c as HTMLElement).className.includes('motion-safe:animate-shimmer')
    );
    expect(someHasShimmer).toBe(true);
  });

  it('aria-busy="true" present on the wrapping element (loading-state ARIA)', () => {
    const { container } = render(
      <SkeletonTable rows={2} columns={fourColumns} />
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root.getAttribute('aria-busy')).toBe('true');
  });

  it('aria-label includes Loading verbiage (screen-reader announces it is loading)', () => {
    const { container } = render(
      <SkeletonTable rows={2} columns={fourColumns} />
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root.getAttribute('aria-label') || '').toMatch(/[Ll]oading/);
  });

  it('axe — no violations on a 4-column 5-row example', async () => {
    const { container } = render(
      <SkeletonTable rows={5} columns={fourColumns} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
