# Security policy

## Supported versions

No version has been released yet. During bootstrap, security fixes target the current development branch through reviewed pull requests. A supported-version table will be published with the first release; no support period or response SLA is promised at this stage.

## Report a vulnerability privately

Use **Security → Advisories → Report a vulnerability** in this repository when GitHub private vulnerability reporting is enabled:

<https://github.com/SaikoAS/Warehouse-Studio/security/advisories/new>

If that option is unavailable, do not open a public vulnerability issue or post exploit details. Ask @SaikoAS for a private reporting channel in a neutral issue containing no vulnerability details, and wait for that channel before sharing the report. This repository does not publish an unverified security email address.

Include the affected commit/version, impact, minimal reproduction and suggested mitigation. Remove personal data, live credentials and confidential warehouse data. Do not test against third-party or production systems without authorization.

The maintainer coordinates remediation and disclosure with the reporter. Public disclosure and release publication require the maintainer's decision.

## CI and agent boundaries

Phase 1 workflows use read-only repository tokens, no production secrets and no privileged `pull_request_target` execution. They do not launch coding agents, deploy software, merge pull requests or publish releases. Repository policy does not replace GitHub access controls; administrators must verify actual settings using the [setup checklist](docs/phase-1-setup.md).
