# Phase 1 setup status

Verified on **2026-11-17** for [SaikoAS/Warehouse-Studio](https://github.com/SaikoAS/Warehouse-Studio). This is a setup snapshot; future settings may change.

| Package | Verified result |
| --- | --- |
| Governance | README expanded with its original heading retained; AGENTS.md, CONTRIBUTING.md, SECURITY.md, Code of Conduct and PR template prepared in [PR #1](https://github.com/SaikoAS/Warehouse-Studio/pull/1). Original MIT LICENSE unchanged. |
| Issues and labels | Three Issue Forms prepared in PR #1. Ten namespaced labels created, existing GitHub defaults retained, including good first issue and help wanted. Forms become available from the default branch after the maintainer merges the PR. |
| Project | [Warehouse Studio – Development, #6](https://github.com/users/SaikoAS/projects/6), public, owned by SaikoAS and linked to the repository. Six ordered status values, Priority P0–P3, Size S/M/L, Execution Human/Codex/Unassigned. Board, Backlog, Roadmap and Agent Queue views saved. |
| CI | [Repository checks](https://github.com/SaikoAS/Warehouse-Studio/actions/workflows/repository-checks.yml) runs docs/config checks only. Initial branch and [PR run](https://github.com/SaikoAS/Warehouse-Studio/actions/runs/44168629442) succeeded at bootstrap commit c8ef362. No application stack or application tests exist. Inspect the latest PR check for subsequent commits. |
| Main protection | [protect-main #27493265](https://github.com/SaikoAS/Warehouse-Studio/rules/27493265) active on refs/heads/main. PR required; required approvals 0; no code-owner/last-push/extra unattributed-change approval. Deletion and force-push blocked. Empty bypass list, including apps/admins. Required observed docs-config check is tied to GitHub Actions, with up-to-date branch required. Squash only; Auto-merge off. |
| Codex | Repository policy and [manual setup instructions](codex-cloud.md) prepared. Personal Cloud connection/environment is **not configured or verified** by this bootstrap. No coding agent/review task started. |
| Versioning | Open [v0.1.0 – Initial Prototype milestone](https://github.com/SaikoAS/Warehouse-Studio/milestone/1), without due date; SemVer and manual release process documented. No tag or release published. |

## Project automation and initial work

- Auto-add is enabled only for open issues in SaikoAS/Warehouse-Studio: `is:issue is:open`. Creating [issue #3](https://github.com/SaikoAS/Warehouse-Studio/issues/3) after setup verified automatic inclusion with Status Inbox.
- Item added → Inbox; Item closed → Done; Pull request merged → Done are enabled. Their saved configuration was inspected; no disposable issue/PR was closed or merged merely to test them.
- Auto-close issue, auto-add sub-issues, PR-linked progress changes, review-driven changes, reopen and archive automation are off. Review/In Progress and reopened-item triage remain manual.
- [Issue #2: approve prototype scope and stack](https://github.com/SaikoAS/Warehouse-Studio/issues/2) and [issue #3: personal Codex setup](https://github.com/SaikoAS/Warehouse-Studio/issues/3) are assigned to SaikoAS with Execution Human. Initial planning assumptions: P1 for both, Size M for scope and S for account setup; maintainer may reprioritize. Both remain Inbox pending triage. PR #1 was manually added at Review.
- Roadmap has optional Start date and Target date fields; no item dates or artificial deadlines were set. Agent Queue filters to open, Ready issues with Execution Codex and is initially empty.

## Security and permissions

GitHub private vulnerability reporting is enabled. Actions default workflow permissions are read-only and workflows cannot approve PRs. The CI uses no secrets and no privileged pull_request_target event.

The chat GitHub connector rejected branch/issue writes with HTTP 403. File publication, issues and administrative API changes were therefore made using the existing GitHub CLI login **SaikoAS**; Project and label setup used the signed-in GitHub browser. No new token, app scope or permission grant was created. CLI Project access lacks the project scope; the Project was configured and inspected in the browser.

**Approval boundary:** zero required reviews avoids an impossible second-human gate for a solo maintainer. PR/CI protection does not technically identify the maintainer's personal approval when an app or tool uses the same write-capable account. Human-only merges/releases and the two-task concurrency limit remain explicit organizational policies; no new agent bypass or merge grant was added.

## Remaining owner checklist

1. Review [PR #1](https://github.com/SaikoAS/Warehouse-Studio/pull/1), its latest docs-config check and these files; merge personally only when satisfied. Main remains at the initial commit until then. Verify the Issue Forms after merge.
2. Complete [issue #3](https://github.com/SaikoAS/Warehouse-Studio/issues/3): sign in to Codex Cloud, authorize repository access personally, create private environment warehouse-studio-dev from the approved repository state and inspect the setup. Current route: Settings → Codex Cloud → Environments → Create environment, or Work in → Cloud → Select environment → Create environment.
3. Keep automatic reviews, schedules, execution triggers and paid API orchestration off. Review network access and supply no production secrets. Maintain at most two manually started coding tasks; repository files do not enforce this account limit. No trial task is launched automatically.
4. Decide the prototype scope and stack in issue #2 before implementation. Release/tag creation requires a later explicit approval following [releases.md](releases.md).

No additional GitHub Project, ruleset, label or milestone activation is outstanding in this snapshot. A dedicated confidential Code of Conduct contact is not configured; choose one before wider community onboarding. Discussions remain optional and were not enabled by this bootstrap.
