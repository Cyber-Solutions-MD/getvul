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
import { useState, useEffect, useId, useRef, Suspense } from 'react';
import { X, ArrowUpRight } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
  useConnectorsList,
  useConnectorTypes,
  useUpdateConnector,
  useDeleteConnector,
  useSyncConnector,
} from '@/lib/queries/use-connectors-admin';
import type { ConnectorConfigResponse, ConnectorFieldSpec } from '@/lib/queries/use-connectors-admin';
import { SkeletonTable, EmptyState, PartialFailureBanner } from '@/components/states';
import { useDocumentTitle } from '@/hooks/use-document-title';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { ResponsiveDialog } from '@/components/ui/responsive-dialog';
import { ConnectorCard } from '@/components/connectors/connector-card';
import { ConnectorCatalogCard } from '@/components/connectors/connector-catalog-card';
import { ConnectorForm } from '@/components/connectors/connector-form';
import { AddConnectorWizard } from '@/components/connectors/wizard/add-connector-wizard';
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  CATEGORY_EMPTY,
  CATALOG_COPY,
  deleteConfirmMessage,
  WIZARD_COPY,
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
  ANTHROPIC: 'ai_assistant',
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
  /** 24-01: richer per-field metadata (select options, required, config vs
   * credentials routing) — ConnectorForm has no independent useConnectorTypes()
   * call of its own, so this must be threaded through from here. */
  fieldSpecs: Record<string, ConnectorFieldSpec>;
  existing?: ConnectorConfigResponse;
};

type DeleteState = {
  open: boolean;
  connectorId: string;
  connectorName: string;
};

function ConnectorsPageInner() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';
  const searchParams = useSearchParams();
  const sectionRefs = useRef<Record<ConnectorCategory, HTMLElement | null>>({
    vulnerability_scanner: null,
    identity_provider: null,
    enrichment: null,
    ticketing: null,
    ai_assistant: null,
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
    fieldSpecs: {},
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
      fieldSpecs: typeInfo.field_specs ?? {},
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
      fieldSpecs: typeInfo?.field_specs ?? {},
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
      fieldSpecs: typeInfo?.field_specs ?? {},
    });
  }

  function closeForm() {
    setFormState({ open: false, mode: 'add', connectorType: '', fields: [], fieldSpecs: {} });
  }

  // D-07 (Phase 15-03): The credential form dialog chrome is handled by
  // ResponsiveDialog which provides:
  //   - Mobile: vaul Drawer (Esc + focus trap via vaul)
  //   - Desktop: backdrop click to close; Esc via onOpenChange
  // The X button inside the form still calls closeForm() for explicit dismissal.
  const formTitleId = useId();

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
    ai_assistant: [],
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

        // Connector types in this category (from /types endpoint), split into
        // already-configured vs. available-to-add (the catalog).
        const catTypes =
          typesQuery.data?.filter(
            (t) => CONNECTOR_CATEGORIES[t.type] === cat,
          ) ?? [];
        const availableTypes = catTypes.filter((t) => !configuredTypes.has(t.type));

        // A category renders as a marketplace: browse the available apps (each with
        // its description + setup link) and Configure the one you want. When nothing
        // is configured yet, an explained-empty intro sits above the catalog grid;
        // when some are configured, the catalog follows under an "Available …" head.
        const catalogGrid = availableTypes.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {availableTypes.map((t) => (
              <ConnectorCatalogCard
                key={t.type}
                type={t.type}
                name={t.name}
                description={t.description}
                setupUrl={t.setup_url}
                onConfigure={openAddForm}
              />
            ))}
          </div>
        );

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
              /* Explained-empty intro + browsable catalog of available apps.
                 No single-type CTA — the user picks from the catalog below. */
              <div className="space-y-6">
                <EmptyState>
                  <EmptyState.Title>{emptyCopy.heading}</EmptyState.Title>
                  <EmptyState.Body>{emptyCopy.body}</EmptyState.Body>
                  <EmptyState.Suggestion>
                    {emptyCopy.suggestion}
                  </EmptyState.Suggestion>
                </EmptyState>
                {catalogGrid}
              </div>
            ) : (
              /* Configured connectors, then the remaining available apps as a catalog. */
              <div className="space-y-6">
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
                </div>
                {availableTypes.length > 0 && (
                  <div>
                    <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-text-faint">
                      {CATALOG_COPY.availableHeading(catLabel)}
                    </h3>
                    {catalogGrid}
                  </div>
                )}
              </div>
            )}
          </section>
        );
      })}

      {/* Add/Edit form — D-07 (Phase 15-03): ResponsiveDialog renders as a vaul
          bottom sheet on mobile and a centered dialog on desktop. The form title
          h2 carries id={formTitleId} inside children so aria-labelledby resolves.
          D-13: dismissOnBackdropClick={false} makes backdrop-click a true no-op
          for this dialog — X and Esc route through onOpenChange → closeForm and
          close immediately. Wizard/form state is dialog-scoped and intentionally
          resets on close/reopen (D-02) — there is no discard-warning modal. */}
      <ResponsiveDialog
        open={formState.open}
        onOpenChange={(o) => { if (!o) closeForm(); }}
        ariaLabelledBy={formTitleId}
        dismissOnBackdropClick={false}
      >
        <div className="p-6">
          {(() => {
            const providerTypeInfo = typesQuery.data?.find(
              (t) => t.type === formState.connectorType,
            );
            const providerName = providerTypeInfo?.name ?? formState.connectorType;
            return (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <h2 id={formTitleId} className="text-lg font-semibold text-text">
                    {formState.mode === 'add'
                      ? WIZARD_COPY.dialogHeading(providerName)
                      : 'Edit connector'}
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
                {formState.mode === 'add' ? (
                  <>
                    {/* Configuration guidelines — the provider's own setup notes +
                        docs link, so the user knows how to obtain keys/permissions
                        before filling the credentials step. Hidden when the type
                        carries neither notes nor a setup_url. */}
                    {(providerTypeInfo?.notes || providerTypeInfo?.setup_url) && (
                      <div className="mb-5 rounded-lg border border-border-subtle bg-surface-2 p-3">
                        <p className="text-xs font-medium uppercase tracking-wide text-text-faint">
                          {CATALOG_COPY.guidanceHeading}
                        </p>
                        {providerTypeInfo?.notes && (
                          <p className="mt-1.5 text-sm text-text-muted">
                            {providerTypeInfo.notes}
                          </p>
                        )}
                        {providerTypeInfo?.setup_url && (
                          <a
                            href={providerTypeInfo.setup_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-2 inline-flex items-center gap-1 text-xs text-violet transition-colors hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
                          >
                            {CATALOG_COPY.setupGuideLabel}
                            <ArrowUpRight size={12} aria-hidden />
                          </a>
                        )}
                      </div>
                    )}
                    <AddConnectorWizard
                      connectorType={formState.connectorType}
                      providerName={providerName}
                      fields={formState.fields}
                      permissions={providerTypeInfo?.permissions ?? []}
                      onClose={closeForm}
                    />
                  </>
                ) : (
                  <ConnectorForm
                    mode="edit"
                    connectorType={formState.connectorType}
                    existing={formState.existing}
                    fields={formState.fields}
                    fieldSpecs={formState.fieldSpecs}
                    onClose={closeForm}
                  />
                )}
              </>
            );
          })()}
        </div>
      </ResponsiveDialog>

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

// useSearchParams() (D-CONN-07 deep-link read) requires a Suspense boundary so the
// page shell can statically prerender (Next.js missing-suspense-with-csr-bailout).
export default function ConnectorsPage() {
  useDocumentTitle('Connectors');
  return (
    <Suspense
      fallback={
        <div className="space-y-8">
          <div>
            <h1 className="text-2xl font-semibold text-text">Connectors</h1>
            <p className="mt-1 text-sm text-text-muted">
              Connect your security tools, ticketing systems, and enrichment sources.
            </p>
          </div>
          <SkeletonTable rows={6} columns={SKELETON_COLUMNS} />
        </div>
      }
    >
      <ConnectorsPageInner />
    </Suspense>
  );
}
