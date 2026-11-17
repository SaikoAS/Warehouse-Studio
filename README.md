# Warehouse-Studio

Warehouse Studio is an open-source warehouse software project. The first prototype focuses on locally importing CSV data, preparing it through saved steps, and viewing the result. Application implementation is pending.

## Project status

- Initial target: **v0.1.0 – Initial Prototype**. See the [architecture decision and planned acceptance checks](docs/adr/0001-v0.1.0-architecture.md).
- Stack: TypeScript, React and Vite for the interface. A local Python service and one SQLite file per project support offline use in Edge on Windows.
- Development model: GitHub Issues and pull requests, with manually launched Codex tasks and human approval of every merge and release.
- License: [MIT](LICENSE), retained from the initial repository.

## Participate

Use the [issue forms](https://github.com/SaikoAS/Warehouse-Studio/issues/new/choose) for bugs, features and technical tasks. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md) before contributing. Report vulnerabilities through the private process in [SECURITY.md](SECURITY.md).

## Development and planning

- [Public development Project](https://github.com/users/SaikoAS/projects/6)
- [Verified Phase 1 setup and remaining owner actions](docs/phase-1-status.md)
- [Agent working rules](AGENTS.md)
- [Project fields, labels and workflow](docs/project-management.md)
- [Codex Cloud setup and manual task handoff](docs/codex-cloud.md)
- [Versioning and release checklist](docs/releases.md)
- [Phase 1 administration checklist](docs/phase-1-setup.md)

CI currently runs documentation and configuration checks. The runtime and application checks are planned as part of v0.1.0 implementation.
