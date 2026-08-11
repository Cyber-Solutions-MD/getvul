'use client';
/**
 * AssetGroupForm — add/edit form for the AssetGroup entity's own name +
 * description (32-05-PLAN Task 2). Mirrors connector-form.tsx's shape
 * (local field state, inline error, Save/Cancel action row) without the
 * credential-sentinel/config-field complexity connectors carry — a group
 * has no secret material.
 */
import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  useCreateAssetGroup,
  useUpdateAssetGroup,
  type AssetGroupResponse,
} from '@/lib/queries/use-asset-groups';
import { cn } from '@/lib/utils';

export type AssetGroupFormProps = {
  mode: 'add' | 'edit';
  existing?: AssetGroupResponse;
  onClose: () => void;
};

const INPUT_CLASSES = cn(
  'w-full rounded-md border border-border-subtle bg-surface-2 px-3 py-2.5 text-sm text-text',
  'placeholder:text-text-faint',
  'focus:border-violet focus:outline-none focus:ring-2 focus:ring-violet/30',
);

export function AssetGroupForm({ mode, existing, onClose }: AssetGroupFormProps) {
  const createMutation = useCreateAssetGroup();
  const updateMutation = useUpdateAssetGroup();

  const [name, setName] = useState(existing?.name ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  const [formError, setFormError] = useState<string | null>(null);

  const isPending = createMutation.isPending || updateMutation.isPending;

  function handleSave() {
    setFormError(null);
    if (name.trim() === '') {
      setFormError('Name is required.');
      return;
    }

    if (mode === 'add') {
      createMutation.mutate(
        { name: name.trim(), description: description.trim() || null },
        {
          onSuccess: () => onClose(),
          onError: (err) => setFormError(err.message),
        },
      );
    } else {
      if (!existing) return;
      updateMutation.mutate(
        { id: existing.id, body: { name: name.trim(), description: description.trim() || null } },
        {
          onSuccess: () => onClose(),
          onError: (err) => setFormError(err.message),
        },
      );
    }
  }

  return (
    <div data-asset-group-form data-mode={mode} className="flex flex-col gap-4">
      <div>
        <label htmlFor="group-name" className="mb-1.5 block text-sm font-medium text-text-muted">
          Name
        </label>
        <input
          id="group-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Prod DB tier"
          className={INPUT_CLASSES}
        />
      </div>
      <div>
        <label htmlFor="group-description" className="mb-1.5 block text-sm font-medium text-text-muted">
          Description <span className="text-text-faint">(optional)</span>
        </label>
        <textarea
          id="group-description"
          value={description ?? ''}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Production Postgres + Redis hosts"
          rows={3}
          className={INPUT_CLASSES}
        />
      </div>

      {formError && (
        <div className="rounded-md border border-severity-critical/30 bg-severity-critical/10 p-3 text-sm text-[var(--color-severity-critical-on-soft)]">
          {formError}
        </div>
      )}

      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md px-4 py-2 text-sm text-text-muted hover:text-text transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={isPending}
          style={{ background: 'var(--gradient-sunset)' }}
          className={cn(
            'inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-[var(--glow-cta)]',
            'hover:-translate-y-px transition-all',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
          data-testid="asset-group-form-save"
        >
          {isPending && <Loader2 size={14} className="animate-spin" />}
          {mode === 'add' ? 'Create group' : 'Save changes'}
        </button>
      </div>
    </div>
  );
}
