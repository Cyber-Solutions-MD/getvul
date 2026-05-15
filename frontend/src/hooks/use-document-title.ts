'use client';
import { useEffect } from 'react';

// D-Tab-01 — set the <title>; restore on unmount so unrelated pages aren't
// affected. Effect's cleanup runs synchronously on unmount, before the next
// page's effect (Pitfall 9 — title flicker race).
export function useDocumentTitle(title: string) {
  useEffect(() => {
    const previous = document.title;
    document.title = title;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
