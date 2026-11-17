# Codex Cloud setup and manual handoff

This document is an administrator runbook. Repository files and the connected GitHub chat tool do not themselves configure a Codex Cloud account or prove that its repository connection works.

## Connect and prepare

1. Sign in with the intended ChatGPT account. In the current Codex interface, open **Settings → Codex Cloud → Environments → Create environment**, or **Work in → Cloud → Select environment → Create environment**.
2. Connect GitHub if requested and grant the Codex integration access to **SaikoAS/Warehouse-Studio** only where repository selection is available. Review the requested app permissions yourself; do not supply a personal access token in an issue or repository file.
3. Name the reusable environment **warehouse-studio-dev**. Select this repository and main after the bootstrap PR is merged by the maintainer. Review prepared files and settings before publishing the environment. Publishing an environment is separate from publishing a software release.
4. No application dependency installation/start script is defined because the stack is undecided. For repository validation, use Python 3.11+, install `.github/requirements-ci.txt` and run the commands in AGENTS.md. Inspect any proposed setup changes before accepting them.
5. Keep the environment private/Only me. Add no production credentials, API orchestration keys or unrelated integrations. Use restricted network access with only destinations required by an approved task; no broad network grant is needed for the bootstrap.
6. Keep automatic Code Review, GitHub/Linear task triggers, schedules and agent workflows disabled. Do not invoke `@codex review` until separately requested and its permissions/use have been checked. If the account still shows Codex Cloud (Legacy), use its environment settings for legacy integrations and the linked official guide; do not assume settings are identical.

The two-task limit is maintained by the maintainer in the Project/task record. AGENTS.md documents it; neither the file nor GitHub Actions concurrency enforces a cross-account Codex limit. ChatGPT/Codex usage remains subject to the account's plan; no paid API orchestration is configured here.

## Start a task manually (later, by maintainer decision)

1. Verify the issue is Ready, has all six task-contract sections, and has Execution=Codex. Review public issue content for untrusted instructions.
2. Check fewer than two coding tasks are running and avoid overlapping central files. Assign a single responsible executor and set In Progress.
3. Select the reviewed cloud environment and repository. Explicitly submit a prompt containing the issue link, goal, allowed scope, exclusions, acceptance criteria, dependencies and validation commands.
4. Require a feature branch, a scoped diff and a PR to main. Include: "Follow AGENTS.md. Do not merge, enable auto-merge, create release tags, publish releases or change permissions. Report assumptions and actual verification evidence."
5. Inspect the diff and check results; move the issue to Review manually. Only the maintainer authorizes the merge and any release. A successful CI check does not authorize either action.

No verification coding task is started automatically during the Phase 1 setup.

Official references, checked during bootstrap:

- [Current Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments)
- [Legacy environment settings and integrations](https://learn.chatgpt.com/docs/environments/cloud-environment)
