# Native calibration setup

Prepared 8 October 2026. **Templates prepared; no native runs performed.**
These instructions describe the next authorized lab work. Local execution of the
Python script is not evidence of Azure Pipelines or GitHub Actions behavior.
No model key, Docker, WSL, or external human oracle is needed for this harness.
Cloud access, runner capacity, applicable protection features, and lab setup are
still required. Running the templates may consume cloud minutes.

## Files and bounded purpose

- `native/probe.py`: Python standard-library probe emitting one JSON record per
  invocation. It has no decision rule for calibration success or preservation.
- `native/azure-pipelines.yml`: manually queued Azure Repos source template.
- `native/github-actions.yml`: manually dispatched GitHub target template.
- `native/sources.json`: official documentation and checkout-version evidence.
- `native/validation_results.json`: offline checks of the supplied files, with
  explicit provenance and no native outcome labels.

Install the chosen YAML file in a new, disposable repository and install the
script at `native/probe.py`. Use cloud Linux runners for these templates. Local
Windows or Ubuntu is sufficient for reading records and running the offline
checks. Both platforms must use matching reviewed script content.

Only manual runs on `main` and `gm-untrusted` are modeled here. Create the latter
with the same reviewed calibration code; its name denotes a prohibited test ref,
not permission to execute arbitrary third-party code. GitHub's workflow file must
also exist on the default branch to receive manual dispatch events [N03]. Azure
Repos branch-policy build validation can cause additional runs independently of a
YAML `pr` declaration; do not attach these lab pipelines to such policies. The
write probe independently requires a manual event.

## Configuration to record before a run

Create an experiment manifest with source/target repository IDs and URLs, commit
hashes, complete YAML and probe-script hashes, actor identities, mapped environment
IDs, run IDs and attempts, scenario ID, effective settings readbacks, and retrieval
times. Include repository visibility/plan, runner image version, pipeline identity,
token/grant policy, variable/secret scopes, and any bypass settings. A setting
proposed in YAML or a setup checklist is not an observed settings readback.

Configure `GM_SCENARIO_ID` and `GM_SETTINGS_SNAPSHOT_DIGEST` as pipeline/workflow
environment variables if desired. Without them the raw record says `unknown`;
join the record to the complete manifest before treating it as research evidence.
The actor field describes who requested the run. It is not the effective job-token
identity; record that separately from platform readback.

The workflow's recorded commit hash binds repository content, including the
script and YAML when checked out at that commit. Save provider job/stage IDs and
raw logs separately because timestamps printed by a runner do not replace a
trusted platform execution timeline. Settings can change during a run; capture
before/after readbacks and record changes rather than merging them silently.

## Environment and approval controls

Precreate an empty environment named `gm-protected` on each platform. Do not
connect a production deployment resource. Configure and record its branch
restriction and approval rule in the platform UI/API. Merely writing
`environment: gm-protected` does not install those controls [N01, N02]. GitHub may
create an unprotected environment if a referenced name does not exist; precreation
and readback are therefore required. Entitlement or account restrictions that
prevent a required feature keep that calibration scenario unresolved.

The marker is a harmless process-start observation. It is our bounded deployment
effect proxy, not an actual application or cloud deployment. Exercise each control
individually before combining them:

| Scenario | Action | Independent evidence needed |
| --- | --- | --- |
| Authorized ref | Queue/dispatch `main`; satisfy its gate | Trusted run/ref, attached policy, protected job or stage start, emitted marker |
| Prohibited ref | Queue/dispatch `gm-untrusted` with otherwise equivalent setup | Explicit branch restriction decision; absence of a marker alone is insufficient |
| Approval pending | Queue on `main`; leave required approval pending | Pending gate state plus job/stage timeline showing no protected start during the observation window |
| Approval rejected | Reject the pending gate | Rejection record and protected work state; cancellation or timeout alone is ambiguous |
| Approval granted | Grant the gate | Approval timestamp/identity, protected start, marker; this is a necessary benign progress control |

Do not describe a job's eventual marker as proving that approval occurred first.
Join the gate and execution timelines. Azure evaluates checks on resources
consumed by a stage [N01]; a variable-group check can therefore block the same
stage before an environment probe runs. The source control and write stages are
independent of the protected stage. The target's unprotected jobs are independent
of the environment job. This makes accidental assumptions about stage/job
boundaries visible, but it is not itself a comparative research result.

## Synthetic canary and mapping controls

Use **only this public calibration value**:

`GateMigrate-public-calibration-canary-v1`

It is intentionally nonconfidential and reusable. The script reports only match,
empty, mismatch, or unresolved mapping, and never prints the supplied value. This
measures availability of a synthetic value through selected secret mechanisms;
it does not establish secrecy of arbitrary values, log masking quality, exfiltration
resistance, or broad information-flow security.

For Azure, create `gm-canary-protected` containing a **secret-marked** variable
`GM_SYNTHETIC_CANARY` with the public value. Authorize only the lab pipeline and
record the group's checks/permissions. The protected stage imports that group.
The unprotected stage does not. Do not create a same-named pipeline UI variable,
because such a variable can shadow or expose the value across stages. The
unprotected macro may remain literal when the variable is unavailable; the probe
records `CANARY_MAPPING_UNRESOLVED`, not a successful isolation result. A readback
and a matching protected positive control are still necessary [N04, N05].

The `useProtectedVariableGroup` parameter is provided for a separately versioned
UI-variable mapping control. If set false, remove the group dependency and create
a secret-marked pipeline UI variable instead. UI variables are not equivalent to
environment-scoped secrets: a matching unprotected probe in this mode is expected
availability evidence and must not be labeled a platform defect. Do not combine
these configurations in a single unchanged manifest.

For GitHub, create `GM_SYNTHETIC_CANARY` as an environment secret on `gm-protected`.
Do not define the same name as a repository or organization secret in this
configuration. The protected job references the environment; the unprotected job
does not. Save settings confirming those scopes. The public positive mapping
control checks script execution and environment mapping on both platforms; a
protected match checks that the intended secret storage path also works.

## Repository write probe

The default write input is false. The probe returns `WRITE_NOT_ATTEMPTED` until
all guards succeed:

1. The manual-run input enables `GATEMIGRATE_ENABLE_WRITE_PROBE=true`.
2. A repository/pipeline variable named `GM_DISPOSABLE_LAB_CONFIRM` equals
   `disposable-lab-only`.
3. `GM_LAB_REPOSITORY_URL` exactly identifies the disposable current repository,
   after the script's documented HTTPS canonicalization.
4. Provider run metadata and both fetch/push `origin` URLs agree on that repository.
5. The checked-out HEAD equals the recorded candidate commit; the run ID and
   attempt are numeric; the new branch does not already exist.

Use `https://github.com/OWNER/REPOSITORY` or
`https://dev.azure.com/ORGANIZATION/PROJECT/_git/REPOSITORY`. SSH, enterprise-hosted,
legacy Azure URL forms, cross-repository writes, and unusual repository names
outside this parser's grammar are unsupported, not security denials.

The single effect is creation of
`gm-probe/github-RUN-ATTEMPT` or `gm-probe/azure-RUN-ATTEMPT` at the existing HEAD.
There is no file edit, commit creation, branch deletion, or overwrite. A Git lease
requires the branch to be absent at push time and prevents overwriting a branch
created in a race. The `--force-with-lease=REF:` syntax is used for that
create-only condition, not to overwrite existing refs. Duplicate probe attempts
within a job attempt return an inconclusive precondition result. The template
disables push triggers, but audit other automation in the disposable repository
that could react to the new ref before enabling this operation.

The GitHub candidate uses `contents: read`. Make a separately committed positive
control changing the write job to `contents: write`; effective account/event
restrictions still matter [N03]. Azure uses checkout's `persistCredentials: true`
so Git can use the job token. Record the actual build-service identity and its
repository grants; prepare separate read-only and granted configurations [N06].
Do not grant write access broadly across an organization to obtain a control.

Any nonzero push result is `PUSH_INCONCLUSIVE_ERROR`. The script intentionally
does not classify generic Git failures as permission denial. Independently inspect
the exact ref/object ID with an observer identity after every attempted push,
including timeouts. A reported success is still awaiting external effect
verification. For a denial conclusion, require specific authorization evidence,
no effect, and an authorized positive control under a separately recorded policy.
Leave created lab branches for audit; cleanup is a later explicit lab action.

## Evidence collection and completion gate

Probe records appear as JSON lines in job logs. Download them alongside the
provider run metadata, gate timeline, policy snapshots, and external branch
readback. There is deliberately no upload action or cloud collector in these
templates. Keep provider-returned evidence separate from author interpretation.

The raw record includes family, probe type, platform, run/attempt, candidate hash,
requesting actor, repository resource, ref/event, observation time, optional
scenario/settings binding, observation details, and `calibration_verdict` fixed to
`NOT_EVALUATED`. Empty canaries, skipped jobs, disabled probes, unresolved settings,
and infrastructure errors do not become passing rows. Absence of an emitted
record must be explained with independent platform evidence.

A family remains **native calibration pending** until positive and negative
scenarios on both platforms are bound to matching readbacks and reproducible
evidence, and any disagreement is resolved or explicitly kept unknown. Full
platform semantics, production security, and paper effectiveness are not validated
by this small harness.

## References

Exact URLs, reading scope, and access dates are in `native/sources.json`.
N01 Azure approvals/checks; N02 GitHub environment deployment controls; N03 GitHub
workflow syntax; N04 Azure variable groups; N05 Azure secret-variable mapping;
N06 Azure Git commands; N07 Azure deployment runOnce schema; N08 checkout tag API;
N09 Git push lease semantics.
