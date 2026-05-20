// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useDocumentTitle } from './use-document-title';

describe('useDocumentTitle', () => {
  it('sets document.title to the provided value', () => {
    renderHook(() => useDocumentTitle('Dashboard · GetVul'));
    expect(document.title).toBe('Dashboard · GetVul');
  });

  it('restores the previous title on unmount (Pitfall 9 cleanup)', () => {
    document.title = 'original';
    const { unmount } = renderHook(() => useDocumentTitle('temporary'));
    expect(document.title).toBe('temporary');
    unmount();
    expect(document.title).toBe('original');
  });

  it('updates document.title when the title prop changes', () => {
    const { rerender } = renderHook(({ title }) => useDocumentTitle(title), {
      initialProps: { title: 'first' },
    });
    expect(document.title).toBe('first');
    rerender({ title: 'second' });
    expect(document.title).toBe('second');
  });
});
