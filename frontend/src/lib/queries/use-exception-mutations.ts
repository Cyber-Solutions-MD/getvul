'use client';
/**
 * useExceptionMutations — Phase 39 Plan 07 (EXC-01/EXC-02) grant/revoke
 * mutations backing the exception-grant dialog and the exceptions-list
 * Revoke button. Mirrors use-campaign-mutations.ts's shape exactly
 * (useMutation + useToast, retry: 0 — BL-06 inheritance: mutations are
 * never silently retried, audit attribution > convenience).
 *
 * useGrantException — POST /api/v1/exceptions (EXC-01 D-06/D-07/D-08).
 * Mirrors useStartCampaign: invalidates + fires a success toast on success.
 * Deliberately has NO onError toast override beyond... actually it DOES
 * mirror useStartCampaign's onError toast too (see below) — but the CALLER
 * (exception-grant-dialog.tsx) is still responsible for reading
 * `mutation.error` itself and rendering the four UI-SPEC-scoped error
 * strings (dialog banner / field-level Expires text) since a single toast
 * can't carry that field-scoped detail. The hook does NOT close the dialog
 * on success — the caller does that via a per-call onSuccess passed to
 * `.mutate()`.
 *
 * useRevokeException(id) — POST /{id}/revoke (D-17). Mirrors useCloseCampaign
 * exactly: no success toast (the list re-render already reflects the
 * revoked row), generic error toast only. Callers MUST route this through a
 * ConfirmModal (variant="warning") — never invoke `.mutate()` from a bare
 * click handler, per useCloseCampaign's own established contract.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';
import type { ExceptionResponse, ExceptionType } from './use-exceptions';

export type GrantExceptionBody =
  | {
      type: ExceptionType;
      scope_type: 'FINDING';
      vulnerability_id: string;
      justification: string;
      approver_user_id: string;
      expires_at: string;
    }
  | {
      type: ExceptionType;
      scope_type: 'ASSET';
      asset_id: string;
      cve_id: string;
      justification: string;
      approver_user_id: string;
      expires_at: string;
    }
  | {
      type: ExceptionType;
      scope_type: 'ASSET_GROUP';
      asset_group_id: string;
      cve_id: string;
      justification: string;
      approver_user_id: string;
      expires_at: string;
    };

export function useGrantException() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<ExceptionResponse, Error, GrantExceptionBody>({
    mutationFn: (body) =>
      api<ExceptionResponse>('/api/v1/exceptions', {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: queryKeys.exceptions.all });
      toast({ variant: 'success', message: `Exception granted for ${data.cve_id}.` });
    },
    onError: () => {
      toast({ variant: 'error', message: "Couldn't save the exception — try again." });
    },
    retry: 0,
  });
}

export function useRevokeException(id: string) {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<ExceptionResponse, Error, void>({
    mutationFn: () => api<ExceptionResponse>(`/api/v1/exceptions/${id}/revoke`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.exceptions.all });
    },
    onError: () => {
      toast({ variant: 'error', message: "Couldn't revoke exception — try again." });
    },
    retry: 0,
  });
}
