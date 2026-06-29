/**
 * Breadcrumb — UX-04-02 page header crumb trail.
 *
 * Reusable by Phase 13 /tickets/[id]. Semantics:
 *   <nav aria-label="Breadcrumb"> > <ol> > [<li>linked or current-page</li>, ...]
 *
 * Tokens used:
 *   - text-text-muted for linked crumbs (substitutes plan's text-text-subtle —
 *     not a configured tailwind token; documented in 12-03-SUMMARY.md)
 *   - text-text-faint/60 for the chevron separator (aria-hidden)
 *
 * T-12-12 (Breadcrumb href prop): accept — href is passed straight to Next
 * <Link>, which serializes through the router. Caller-supplied URLs are
 * expected to be application-relative.
 */
import Link from 'next/link';
import { Children, Fragment, isValidElement, type ReactElement, type ReactNode } from 'react';

export type CrumbProps = {
  href?: string;
  children: ReactNode;
};

export function Crumb({ href, children }: CrumbProps) {
  if (href) {
    return (
      <li className="inline-flex items-center text-sm text-text-muted">
        <Link
          href={href}
          className="hover:text-text focus-visible:underline focus-visible:outline-none"
        >
          {children}
        </Link>
      </li>
    );
  }
  return (
    <li
      className="inline-flex items-center text-sm font-medium text-text"
      aria-current="page"
    >
      {children}
    </li>
  );
}

export type BreadcrumbProps = {
  children: ReactNode;
};

export function Breadcrumb({ children }: BreadcrumbProps) {
  const items = Children.toArray(children).filter(isValidElement) as ReactElement<CrumbProps>[];
  return (
    <nav aria-label="Breadcrumb">
      {/* Only <li> may be a direct child of <ol> (WCAG list / listitem). The
          chevron separator is therefore its own aria-hidden <li>, not a wrapping
          <span> around each crumb. */}
      <ol className="flex items-center gap-2">
        {items.map((item, idx) => {
          // WR-11: stable key prefers the crumb's href, else the text label.
          // Array-index keys cause React to reconcile the wrong nodes if a
          // parent ever conditionally inserts a crumb mid-trail.
          const key = item.props.href ?? String(item.props.children) ?? `crumb-${idx}`;
          return (
            <Fragment key={key}>
              {item}
              {idx < items.length - 1 && (
                <li className="inline-flex items-center text-text-faint/60" aria-hidden="true">
                  ›
                </li>
              )}
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
