'use client';
/**
 * KanbanCard — compact draggable ticket card (D-CARD-01/02).
 *
 * Top line: provider mark + mono external ID + truncated title.
 * Bottom line: severity glyph + SLA pill + assignee avatar.
 *
 * D-CARD-01: no status-pill affordance on the card — the only status signal
 * is the red `border-l-severity-critical` accent when the ticket is blocked
 * (the column itself already encodes status via position).
 * D-CARD-02: click opens the DrillPanel via `onOpen`. The click is
 * distance-gated by the PointerSensor's activation constraint configured in
 * the DndContext container (18-03) — a small pointer movement (<8px) still
 * fires a click, a real drag (>=8px) does not.
 *
 * `overlay` renders a non-interactive static clone for dnd-kit's
 * `DragOverlay` — no `useDraggable` hook, no onClick, no drag affordance.
 *
 * T-18-06 mitigation: all ticket fields render as React text children (no
 * dangerouslySetInnerHTML); provider is narrowed via a literal guard before
 * ProviderMark (no `as` launder).
 * No inline hex — all colors via Tailwind sunset tokens.
 */
import { useDraggable } from '@dnd-kit/core';
import { Avatar } from '@/components/ui/Avatar';
import { ProviderMark } from './provider-mark';
import { SlaPill } from './sla-pill';
import { SEVERITY_GLYPH, SEVERITY_CLASS } from './severity-glyph';
import { cn } from '@/lib/utils';
import type { TicketSummary } from '@/lib/queries/use-tickets';
import type { TicketProvider } from './types';

function isTicketProvider(value: string | null): value is TicketProvider {
  return value === 'jira' || value === 'asana' || value === 'github';
}

export type KanbanCardProps = {
  ticket: TicketSummary;
  onOpen: (ticket: TicketSummary) => void;
  /** Non-interactive static clone for DragOverlay — no drag hook, no onClick. */
  overlay?: boolean;
};

function CardBody({ ticket }: { ticket: TicketSummary }) {
  const sev = ticket.max_severity?.toLowerCase() ?? '';
  return (
    <>
      {/* Top line: provider + mono ID + truncated title */}
      <div className="flex items-center gap-2">
        {isTicketProvider(ticket.provider) && <ProviderMark provider={ticket.provider} />}
        <span className="font-mono text-xs text-text shrink-0">
          {ticket.external_ticket_id}
        </span>
        <span className="truncate text-sm text-text" title={ticket.title}>
          {ticket.title}
        </span>
      </div>
      {/* Bottom line: severity glyph + SLA pill + assignee avatar */}
      <div className="mt-2 flex items-center justify-between">
        <span
          aria-label={ticket.max_severity ?? 'unknown'}
          className={cn('text-sm', SEVERITY_CLASS[sev] ?? 'text-text-faint')}
        >
          {SEVERITY_GLYPH[sev] ?? '○'}
        </span>
        <SlaPill dueAt={ticket.sla_due_at} />
        {ticket.assignee && <Avatar name={ticket.assignee} email={ticket.assignee} size={20} />}
      </div>
    </>
  );
}

export function KanbanCard({ ticket, onOpen, overlay = false }: KanbanCardProps) {
  if (overlay) {
    return (
      <div
        data-ticket-id={ticket.id}
        className={cn(
          'cursor-grabbing rounded-lg border border-border-subtle bg-surface p-3 shadow-lg',
          ticket.blocked && 'border-l-2 border-l-severity-critical',
        )}
      >
        <CardBody ticket={ticket} />
      </div>
    );
  }

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: ticket.id });

  return (
    <div
      ref={setNodeRef}
      data-ticket-id={ticket.id}
      {...attributes}
      {...listeners}
      onClick={() => onOpen(ticket)}
      className={cn(
        'cursor-grab rounded-lg border border-border-subtle bg-surface p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
        ticket.blocked && 'border-l-2 border-l-severity-critical',
        isDragging && 'opacity-40',
      )}
    >
      <CardBody ticket={ticket} />
    </div>
  );
}
