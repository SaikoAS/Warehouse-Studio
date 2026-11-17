# Contributing

Thank you for helping build Warehouse Studio. The [v0.1.0 architecture decision](docs/adr/0001-v0.1.0-architecture.md) describes the approved stack and scope. The runnable application and its test suite are pending.

## Propose work

Use Bug Report, Feature Request or Technical Task in the issue chooser. Include a goal, bounded scope (including exclusions), measurable acceptance criteria, dependencies (or None), validation evidence and a definition of done. Use synthetic examples without personal, customer or warehouse-sensitive data.

The maintainer triages new items in Inbox, chooses Priority, Size and Execution, and moves complete tasks to Ready. Ready and Execution=Codex do not launch agents. Large tasks should be split; blocked tasks need a recorded reason. See [project management](docs/project-management.md).

## Develop a change

1. Agree on the issue scope with the maintainer. Product scope, architecture and stack selection require explicit decisions.
2. Create a branch such as `feat/123-short-description`, `fix/123-short-description` or `docs/123-short-description` from main. External contributors use a fork.
3. Keep changes focused; preserve source provenance and avoid committing confidential data or credentials.
4. For the current bootstrap, run `python -m pip install -r .github/requirements-ci.txt`, `python scripts/check_repository.py` and `git diff --check` using Python 3.11+. These are repository checks, not application tests.
5. Open a pull request using the template. Link the issue, explain behavior and evidence, and identify limits. Use `Closes #123` only when the whole issue is actually completed.
6. Move the task to Review manually. Address feedback. The maintainer decides whether to squash-merge; no mandatory second human approval is required for this solo-maintainer phase.

Agents follow [AGENTS.md](AGENTS.md). At most two coding tasks may run concurrently as an organizational policy. No label, status change or public issue automatically starts a task.

## Community and security

Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Use issues for actionable work and questions until Discussions are enabled. Do not post vulnerabilities publicly; follow [SECURITY.md](SECURITY.md).

Contributions are made under the existing [MIT license](LICENSE). Release publication and permission changes remain maintainer decisions; see the [release checklist](docs/releases.md).
