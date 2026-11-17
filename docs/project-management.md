# Project management

## Ownership and fields

Target Project: **Warehouse Studio – Development**, owned by **SaikoAS**, public and linked to this repository. Actual setup status is recorded in the bootstrap PR and [administration checklist](phase-1-setup.md); this specification alone does not create GitHub settings.

| Field | Options / source |
| --- | --- |
| Status | Inbox, Ready, In Progress, Review, Blocked, Done |
| Priority | P0, P1, P2, P3 |
| Size | S, M, L |
| Execution | Human, Codex, Unassigned |
| Target version | Native Milestone field, no duplicate custom version field |
| Area | Repository labels |

P0 means urgent critical impact; P1 means next important work; P2 means normal planned work; P3 means later/nice-to-have. Priority and Status belong in Project fields, not duplicate labels. S is a small focused task, M is a bounded change, L needs decomposition where practical; these are relative sizes, not time estimates.

Inbox is untriaged. Ready requires Goal, Scope, Acceptance Criteria, Dependencies, Validation and Definition of Done. In Progress means a manually started task has an executor. Review means a PR is waiting for maintainer review. Blocked needs a cause and next action. Done means the issue's agreed outcome is completed or its closure reason is recorded; closure as not-planned is not evidence that a feature shipped.

## Views

| View | Layout | Filter / grouping |
| --- | --- | --- |
| Board | Board | Group by Status; show all six states |
| Backlog | Table | `is:issue is:open`; group by Priority, show Size, Execution, Milestone, Labels |
| Roadmap | Roadmap | `is:issue`; use optional Start date / Target date fields only after dates are approved |
| Agent Queue | Table | `is:issue is:open status:Ready execution:Codex`; show Priority, Size, Dependencies in issue body |

No fictional roadmap dates are assigned. Execution=Unassigned is an explicit option, not a GitHub assignee. The queue is a planning view, not an execution trigger.

## Native automation

- One auto-add workflow for `SaikoAS/Warehouse-Studio`, filter `is:issue is:open`; backfill existing open issues explicitly during setup.
- Item added: Status → Inbox. Confirm this also applies to auto-added issues.
- Issue closed: Status → Done. Pull request merged: Status → Done for PRs manually included in the Project.
- Reopened issues are triaged manually and moved from Done to Inbox/Ready as appropriate.
- Review and In Progress remain manual. A merged PR closes its issue only when an appropriate closing keyword links it.
- Do not enable the reverse workflow that closes issues just because a card is moved to Done.

## Labels

The exact names, colors and descriptions are defined in [labels.json](../.github/labels.json). That file is a manifest, not an automatic label synchronizer.

Types: `type:bug`, `type:feature`, `type:enhancement`, `type:refactor`, `type:docs`. Technical Tasks receive the appropriate type during triage rather than pretending all maintenance is a refactor.

Areas: `area:governance`, `area:ci`, `area:core`, `area:ui`, `area:data`. **Assumption:** core/ui/data are provisional sorting categories, not architecture decisions. Preserve existing GitHub default labels; use the namespaced taxonomy for new work. Reuse `good first issue` and `help wanted` for suitable community work.

## Roles and approval

SaikoAS decides product scope, architecture, task starts, merges and releases. ChatGPT supports planning; manually assigned Codex tasks implement bounded work and prepare PRs. Maximum two concurrent coding tasks is an organizational policy, not a technical account limit. Do not assign a coding agent through GitHub or invoke review commands as part of Phase 1.
