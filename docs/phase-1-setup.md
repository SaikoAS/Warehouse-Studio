# Phase 1 administrator checklist

These are target settings. Files in a PR do not apply administrative settings. Consult the bootstrap PR for verified live results and any outstanding steps.

## GitHub Project and milestone

- Create a user-owned Project **Warehouse Studio – Development**, make it public, and link SaikoAS/Warehouse-Studio.
- Configure the exact fields, four views and native workflows in [project-management.md](project-management.md). Leave dates empty until agreed. Backfill existing open issues; auto-add alone may not backfill them.
- Create the open milestone **v0.1.0 – Initial Prototype**, description: "First usable prototype. Functional scope, stack and acceptance criteria require maintainer approval before implementation. No release is published by this milestone." Leave its due date empty.
- Apply labels from `.github/labels.json`; retain existing defaults. The manifest has no automatic synchronization or agent trigger.

## Repository checks and merge settings

- **Settings → Actions → General:** allow the pinned `actions/checkout` action; default workflow permissions **Read repository contents and packages**. Leave **Allow GitHub Actions to create and approve pull requests** off. Review fork-workflow approval policy. No secrets are needed by this CI.
- Verify the actual **Repository checks / docs-config** job succeeds on the bootstrap PR before requiring its observed check context.
- **Settings → General → Pull Requests:** allow Squash merging; disable Merge commits, Rebase merging and Auto-merge. No workflow or agent should merge automatically.

## Ruleset protect-main

In **Settings → Rules → Rulesets → New branch ruleset**:

- Name `protect-main`, Enforcement **Active**, target branch `main` only.
- Bypass list **empty**, including administrators and GitHub Apps: no agent bypass.
- Enable **Restrict deletions**, **Block force pushes**, **Require a pull request before merging**.
- Required approvals **0**; do not require code-owner approval, a second person or approval of the last push. Do not enable an extra Copilot approval requirement in this solo-maintainer phase.
- Allow only **Squash** for PR merges where the rule offers merge methods.
- After the actual CI run succeeds, enable **Require status checks to pass**, add the observed `docs-config` check from **GitHub Actions**, and require the branch to be up to date. Do not invent a test check or select an unobserved context.
- Verify the saved rule targets main, is active, has an empty bypass list and contains the expected required check. Do not test protection with a destructive push.

PR approval count zero means the maintainer's personal merge approval is a working rule, not an identity-specific technical gate. A connected app/user with sufficient repository rights may still be able to merge an eligible PR. No extra agent access is granted by this bootstrap.

## Security, community and Codex

- **Settings → Security / Advanced Security:** enable private vulnerability reporting if available; verify **Security → Advisories → Report a vulnerability** is present. SECURITY.md includes a safe fallback until verified.
- Keep Discussions optional until categories/moderation are chosen; no community launch is implied by these files. Choose a private Code of Conduct contact before inviting broader participation.
- Complete and verify [Codex Cloud setup](codex-cloud.md) personally, including repository authorization and environment settings. This repository does not activate account integrations.
- Launch coding tasks manually only, maintain at most two active tasks, and keep automatic reviews/task triggers off.
- Review and merge the bootstrap PR personally when satisfied. Issue Forms become available from the default branch after merge; no agent merges it.
- Approve v0.1.0 product scope and acceptance criteria separately. Do not create a tag or publish a release during Phase 1.
