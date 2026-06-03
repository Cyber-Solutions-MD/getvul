'use client';
/**
 * /dashboard/connectors — category-sectioned connector management page.
 *
 * D-CONN-03: Connectors grouped by CONNECTOR_CATEGORIES into 4 sections:
 *   Vulnerability scanners / Identity / MDM & enrichment / Ticketing
 *
 * D-CONN-07: Reads ?provider= from URL; if present, pre-opens ConnectorForm in
 *   add mode for that provider. T-14-09: provider value is uppercased and matched
 *   against known types — unknown providers open no form.
 *
 * D-X-01: State patterns mandatory:
 *   - isPending  → <SkeletonTable>
 *   - error      → <PartialFailureBanner>
 *   - per-category zero → <EmptyState> with "Add connector" CTA
 *   - mutations  → toasts (handled in hooks)
 *
 * Sunset-tokenized: no raw gray-N or indigo-N utilities.
 */
import { useState, useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
  useConnectorsList,
  useConnectorTypes,
  useUpdateConnector,
  useDeleteConnector,
  useSyncConnector,
} from '@/lib/queries/use-connectors-admin';
import type { ConnectorConfigResponse } from '@/lib/queries/use-connectors-admin';
import { SkeletonTable, EmptyState, PartialFailureBanner } from '@/components/states';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { getFocusable, trapTabKey } from '@/components/ui/focus-trap';
import { ConnectorCard } from '@/components/connectors/connector-card';
import { ConnectorForm } from '@/components/connectors/connector-form';
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  CATEGORY_EMPTY,
  deleteConfirmMessage,
} from '@/components/connectors/microcopy';
import type { ConnectorCategory } from '@/components/connectors/microcopy';
import { queryKeys } from '@/lib/queries/keys';

// CONNECTOR_CATEGORIES maps backend connector_type → category key.
// Sourced from backend/app/connectors/router.py CONNECTOR_CATEGORIES.
const CONNECTOR_CATEGORIES: Record<string, ConnectorCategory> = {
  CROWDSTRIKE: 'vulnerability_scanner',
  NESSUS: 'vulnerability_scanner',
  DEFENDER: 'vulnerability_scanner',
  WIZ: 'vulnerability_scanner',
  QUALYS: 'vulnerability_scanner',
  RAPID7: 'vulnerability_scanner',
  ASANA: 'ticketing',
  JIRA: 'ticketing',
  GITHUB: 'ticketing',
  GOOGLE_WORKSPACE: 'identity_provider',
  AZURE_ENTRA_ID: 'identity_provider',
  OKTA: 'identity_provider',
  HUMAANS: 'enrichment',
  JAMF: 'enrichment',
  INTUNE: 'enrichment',
};

// Skeleton columns mirroring card grid layout
const SKELETON_COLUMNS = [
  { kind: 'text' as const, width: 180 },
  { kind: 'pill' as const, width: 80 },
  { kind: 'mono' as const, width: 120 },
];

type FormState = {
  open: boolean;
  mode: 'add' | 'edit';
  connectorType: string;
  fields: string[];
  existing?: ConnectorConfigResponse;
};

type DeleteState = {
  open: boolean;
  connectorId: string;
  connectorName: string;
};

export default function ConnectorsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';
  const searchParams = useSearchParams();
  const sectionRefs = useRef<Record<ConnectorCategory, HTMLElement | null>>({
    vulnerability_scanner: null,
    identity_provider: null,
    enrichment: null,
    ticketing: null,
  });

  const connectorsQuery = useConnectorsList();
  const typesQuery = useConnectorTypes();
  const updateMutation = useUpdateConnector();
  const deleteMutation = useDeleteConnector();
  const syncMutation = useSyncConnector();

  const [formState, setFormState] = useState<FormState>({
    open: false,
    mode: 'add',
    connectorType: '',
    fields: [],
  });
  const [deleteState, setDeleteState] = useState<DeleteState>({
    open: false,
    connectorId: '',
    connectorName: '',
  });
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  // D-CONN-07: ?provider= deep-link handling (T-14-09: uppercased + whitelist check).
  useEffect(() => {
    const rawProvider = searchParams.get('provider');
    if (!rawProvider || !typesQuery.data) return;
    const providerType = rawProvider.toUpperCase();
    const typeInfo = typesQuery.data.find((t) => t.type === providerType);
    if (!typeInfo) return; // unknown provider — no form opened (T-14-09)

    setFormState({
      open: true,
      mode: 'add',
      connectorType: providerType,
      fields: typeInfo.fields,
    });

    // Scroll the matching category section into view (guard for jsdom/test environments).
    const cat = CONNECTOR_CATEGORIES[providerType];
    if (cat && sectionRefs.current[cat] && typeof sectionRefs.current[cat]!.scrollIntoView === 'function') {
      sectionRefs.current[cat]!.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [searchParams, typesQuery.data]);

  function openEditForm(connector: ConnectorConfigResponse) {
    const typeInfo = typesQuery.data?.find((t) => t.type === connector.connector_type);
    setFormState({
      open: true,
      mode: 'edit',
      connectorType: connector.connector_type,
      fields: typeInfo?.fields ?? [],
      existing: connector,
    });
  }

  function openAddForm(connectorType: string) {
    const typeInfo = typesQuery.data?.find((t) => t.type === connectorType);
    setFormState({
      open: true,
      mode: 'add',
      connectorType,
      fields: typeInfo?.fields ?? [],
    });
  }

  function closeForm() {
    setFormState({ open: false, mode: 'add', connectorType: '', fields: [] });
  }

  // WR-04: dialog a11y — Escape closes, Tab is trapped, initial focus lands in
  // the dialog. Backdrop click no longer dismisses (would discard typed
  // credentials); the user closes via the X button or the form's Cancel.
  const formDialogRef = useRef<HTMLDivElement>(null);
  const formTitleId = useId();

  useEffect(() => {
    if (!formState.open) return;
    // Move focus into the dialog on open.
    const focusable = formDialogRef.current ? getFocusable(formDialogRef.current) : [];
    focusable[0]?.focus();

    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        closeForm();
        return;
      }
      if (e.key === 'Tab' && formDialogRef.current) {
        trapTabKey(e, getFocusable(formDialogRef.current));
      }
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [formState.open]);

  function handleDelete(connectorId: string) {
    const conn = connectorsQuery.data?.find((c) => c.id === connectorId);
    setDeleteState({
      open: true,
      connectorId,
      connectorName: conn?.connector_name ?? connectorId,
    });
  }

  function handleConfirmDelete() {
    deleteMutation.mutate(deleteState.connectorId, {
      onSettled: () => setDeleteState({ open: false, connectorId: '', connectorName: '' }),
    });
  }

  function handleSync(connectorId: string) {
    setSyncingIds((prev) => new Set(prev).add(connectorId));
    syncMutation.mutate(connectorId, {
      onSettled: () =>
        setSyncingIds((prev) => {
          const next = new Set(prev);
          next.delete(connectorId);
          return next;
        }),
    });
  }

  function handleToggleEnabled(connector: ConnectorConfigResponse, enabled: boolean) {
    updateMutation.mutate({ id: connector.id, body: { is_enabled: enabled } });
  }

  // ——— Render states ———

  // Loading
  if (connectorsQuery.isPending) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-text">Connectors</h1>
          <p className="mt-1 text-sm text-text-muted">
            Connect your security tools, ticketing systems, and enrichment sources.
          </p>
        </div>
        <SkeletonTable rows={6} columns={SKELETON_COLUMNS} />
      </div>
    );
  }

  // Error
  if (connectorsQuery.error) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-text">Connectors</h1>
        </div>
        <PartialFailureBanner
          errors={[
            {
              code: 'unknown',
              requestId: 'unknown',
              message: (connectorsQuery.error as Error).message,
            },
          ]}
          onRetry={() => connectorsQuery.refetch()}
        />
      </div>
    );
  }

  // Group connectors by category
  const connectorsByCategory: Record<ConnectorCategory, ConnectorConfigResponse[]> = {
    vulnerability_scanner: [],
    identity_provider: [],
    enrichment: [],
    ticketing: [],
  };

  for (const conn of connectorsQuery.data ?? []) {
    const cat = CONNECTOR_CATEGORIES[conn.connector_type];
    if (cat) {
      connectorsByCategory[cat].push(conn);
    }
  }

  // Build a set of configured types for deep-link button availability
  const configuredTypes = new Set(
    (connectorsQuery.data ?? []).map((c) => c.connector_type),
  );

  return (
    <div className="space-y-10">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-text">Connectors</h1>
        <p className="mt-1 text-sm text-text-muted">
          Connect your security tools, ticketing systems, and enrichment sources.
        </p>
      </div>

      {/* Category sections */}
      {CATEGORY_ORDER.map((cat) => {
        const catConnectors = connectorsByCategory[cat];
        const catLabel = CATEGORY_LABELS[cat];
        const emptyCopy = CATEGORY_EMPTY[cat];

        // Connector types in this category (from /types endpoint)
        const catTypes =
          typesQuery.data?.filter(
            (t) => CONNECTOR_CATEGORIES[t.type] === cat,
          ) ?? [];

        return (
          <section
            key={cat}
            ref={(el) => { sectionRefs.current[cat] = el; }}
            aria-labelledby={`section-${cat}`}
          >
            <h2
              id={`section-${cat}`}
              className="mb-4 text-base font-semibold text-text"
            >
              {catLabel}
            </h2>

            {catConnectors.length === 0 ? (
              /* Empty state */
              <EmptyState>
                <EmptyState.Title>{emptyCopy.heading}</EmptyState.Title>
                <EmptyState.Body>{emptyCopy.body}</EmptyState.Body>
                <EmptyState.Actions>
                  {/* "Add connector" CTA — opens add flow for first type in this category */}
                  {catTypes.length > 0 && (
                    <button
                      type="button"
                      onClick={() => openAddForm(catTypes[0].type)}
                      style={{ background: 'var(--gradient-sunset)' }}
                      className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-[var(--glow-cta)] hover:-translate-y-px transition-all"
                    >
                      {emptyCopy.cta}
                    </button>
                  )}
                </EmptyState.Actions>
                <EmptyState.Suggestion>
                  {emptyCopy.suggestion}
                </EmptyState.Suggestion>
              </EmptyState>
            ) : (
              /* Connector card grid */
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {catConnectors.map((connector) => (
                  <ConnectorCard
                    key={connector.id}
                    connector={connector}
                    isAdmin={isAdmin}
                    onEdit={openEditForm}
                    onDelete={handleDelete}
                    onSync={handleSync}
                    onToggleEnabled={(enabled) => handleToggleEnabled(connector, enabled)}
                    isSyncing={syncingIds.has(connector.id)}
                  />
                ))}
                {/* "Add another" card for configured categories */}
                {catTypes
                  .filter((t) => !configuredTypes.has(t.type))
                  .map((t) => (
                    <button
                      key={t.type}
                      type="button"
                      onClick={() => openAddForm(t.type)}
                      className="flex min-h-[100px] items-center justify-center rounded-lg border border-dashed border-border-subtle bg-surface p-4 text-sm text-text-muted transition-colors hover:border-border hover:text-text"
                    >
                      + {t.name}
                    </button>
                  ))}
              </div>
            )}
          </section>
        );
      })}

      {/* Add/Edit form modal (WR-04: dialog a11y; no backdrop-click dismissal
          so in-progress credential entry is never silently discarded) */}
      {formState.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface/80 backdrop-blur-sm">
          <div
            ref={formDialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={formTitleId}
            className="mx-4 w-full max-w-lg overflow-y-auto rounded-xl border border-border-subtle bg-surface-2 p-6 shadow-2xl max-h-[90vh]"
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 id={formTitleId} className="text-lg font-semibold text-text">
                {formState.mode === 'add' ? 'Add connector' : 'Edit connector'}
              </h2>
              <button
                type="button"
                onClick={closeForm}
                aria-label="Close"
                className="rounded-md p-1 text-text-faint transition-colors hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
              >
                <X size={18} />
              </button>
            </div>
            <ConnectorForm
              mode={formState.mode}
              connectorType={formState.connectorType}
              existing={formState.existing}
              fields={formState.fields}
              onClose={closeForm}
            />
          </div>
        </div>
      )}

      {/* Delete confirm modal */}
      <ConfirmModal
        open={deleteState.open}
        title="Delete connector"
        message={deleteConfirmMessage(deleteState.connectorName)}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteState({ open: false, connectorId: '', connectorName: '' })}
      />
    </div>
  );
}
