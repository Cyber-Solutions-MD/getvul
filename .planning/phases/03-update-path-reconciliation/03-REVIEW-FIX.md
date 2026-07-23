---
phase: 03-update-path-reconciliation
fixed_at: 2026-07-23T00:00:00Z
review_path: .planning/phases/03-update-path-reconciliation/03-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 0
skipped: 1
status: none_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-07-23T00:00:00Z
**Source review:** .planning/phases/03-update-path-reconciliation/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1 (WR-01)
- Fixed: 0
- Skipped: 1

Nothing was committed. This is expected and correct — see the skip rationale below.

## Fixed Issues

None — the sole in-scope finding was skipped for safety (requires out-of-band secret provisioning that cannot be done from within the repo).

## Skipped Issues

### WR-01: SSH host-key trust is decorative — `ssh-keyscan` failure ignored and `StrictHostKeyChecking=no` on deploy

**File:** `.github/workflows/cd.yml:55`, `:62`
**Status:** skipped — requires human verification
**Reason:** The finding is CONFIRMED against current code (verified 2026-07-23):
- Line 55: `ssh-keyscan -H ${{ env.VM_HOST }} >> ~/.ssh/known_hosts 2>/dev/null || true`
- Line 62: `ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no ...`

This is a SHIPPED production CD pipeline. The correct fix — pre-seed a trusted host key
from a GitHub Actions secret and set `StrictHostKeyChecking=yes` — depends on a secret
(`GCE_KNOWN_HOSTS` / `VM_SSH_HOST_KEY`) that **does not yet exist** in the repo. The
fixer cannot provision GitHub secrets. Hard-enabling strict host-key checking against a
missing/empty secret would immediately break real production deploys (every `ssh` would
fail host-key verification). Therefore the code change is deferred to a human operator who
has the VM's real host key in hand.

**Original issue:** The runner suppresses all `ssh-keyscan` errors (`|| true`) and then
connects with `StrictHostKeyChecking=no`, so the `known_hosts` write is purely decorative
and no host-key verification happens. An attacker who can spoof/hijack `GCE_VM_IP` gets a
MITM position on production deploys — harvesting the deploy key or serving
attacker-controlled responses to the VM-side commands (which run under `bash -s` and read
`DEPLOY_TAG`).

---

## Remediation (for a human with infra access)

This must be applied by someone who can add a GitHub Actions secret AND obtain the VM's
real SSH host public key from a trusted, out-of-band channel (the GCE serial console, the
provisioning logs, or a `gcloud compute ssh` session verified against the instance).

### Step 1 — Capture the VM's trusted host key (out-of-band)

From a trusted machine (NOT via the untrusted network path this vuln is about — ideally
from the GCE serial-port output or `gcloud compute instances get-serial-port-output`),
obtain the host key line(s). If you must use `ssh-keyscan`, cross-check the resulting
fingerprint against the value printed on the instance's serial console before trusting it:

```bash
# Produces the known_hosts line(s). VERIFY the fingerprint against the serial console.
ssh-keyscan -H <GCE_VM_IP>
# Cross-check fingerprint:
ssh-keyscan <GCE_VM_IP> | ssh-keygen -lf -
```

### Step 2 — Store it as a repo secret

Add the verified `known_hosts` content as a new Actions secret named `GCE_KNOWN_HOSTS`:

```bash
gh secret set GCE_KNOWN_HOSTS < known_hosts.verified
# or paste via: Settings → Secrets and variables → Actions → New repository secret
```

### Step 3 — Apply this exact `cd.yml` diff

Replace the "Configure SSH" step and the `ssh` invocation line in "Deploy to VM":

```diff
       - name: Configure SSH
         run: |
           mkdir -p ~/.ssh
           echo "${{ secrets.GCE_SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
           chmod 600 ~/.ssh/deploy_key
-          ssh-keyscan -H ${{ env.VM_HOST }} >> ~/.ssh/known_hosts 2>/dev/null || true
+          # Trust ONLY the pre-verified host key from the secret (no TOFU keyscan).
+          echo "${{ secrets.GCE_KNOWN_HOSTS }}" >> ~/.ssh/known_hosts
+          chmod 600 ~/.ssh/known_hosts

       - name: Deploy to VM
         run: |
           # Pass DEPLOY_TAG as a remote environment variable (allowlisted above) and
           # use a QUOTED heredoc so the VM-side shell performs all $(...)/$var
           # expansion — nothing from the workflow is expanded host-side.
-          ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no "${{ env.VM_USER }}@${{ env.VM_HOST }}" DEPLOY_TAG="$DEPLOY_TAG" bash -s << 'DEPLOY'
+          ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=yes "${{ env.VM_USER }}@${{ env.VM_HOST }}" DEPLOY_TAG="$DEPLOY_TAG" bash -s << 'DEPLOY'
```

Notes:
- `StrictHostKeyChecking=yes` requires the key to already be present in `known_hosts`
  (it will be, from Step 3's `GCE_KNOWN_HOSTS` write). If you prefer a slightly softer
  posture during a one-time key rotation, `accept-new` will trust an unknown host on first
  contact but still refuse a **changed** key — however `yes` + a seeded secret is the
  strongest and is the recommended target state.
- Do NOT re-add `ssh-keyscan` — pairing it with strict checking re-introduces TOFU and
  defeats the purpose.

### Step 4 — Verify before merging

- Confirm `secrets.GCE_KNOWN_HOSTS` is set (`gh secret list`).
- Trigger a manual `workflow_dispatch` deploy of the current release tag and confirm the
  "Deploy to VM" step connects without a host-key prompt/failure.
- If it fails with "Host key verification failed", the secret contents do not match the
  live host key — re-capture in Step 1 rather than falling back to `no`.

---

_Fixed: 2026-07-23T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
