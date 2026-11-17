# Versioning and release process

Warehouse Studio uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Release tags use `vMAJOR.MINOR.PATCH`. No tag or release is created by the Phase 1 bootstrap.

During `0.x`, the product is experimental: use a new minor version for breaking changes or substantial features, a patch for compatible fixes, and document every breaking change and migration. Before `1.0.0`, define the supported public API and compatibility guarantees. From `1.0.0`, use major/minor/patch according to incompatible/compatible-feature/compatible-fix changes. Prereleases may use suffixes such as `v0.1.0-alpha.1`.

## Initial milestone

**v0.1.0 – Initial Prototype** is a planning milestone, not a release commitment. No due date is invented. Its functional scope, stack and measurable acceptance criteria must be approved before implementation; the bootstrap alone does not complete it.

## Manual release checklist

1. Agree milestone scope and acceptance criteria; link the intended issues and PRs. Record incomplete items and move them explicitly to a later milestone.
2. Verify the intended main commit, successful CI and all stack-specific and manual acceptance checks once available. Bootstrap docs/config checks alone are insufficient for a prototype release.
3. Review the diff, dependency/license changes, security issues, compatibility changes and migration instructions. Never include confidential data or credentials.
4. Prepare release notes listing user-visible changes, resolved issues, known limits and the exact commit. Decide whether the release is a prerelease and which artifacts, if any, are needed.
5. Obtain the maintainer's explicit approval of version, commit, notes and artifacts. Only the maintainer creates the tag and publishes the GitHub Release from that reviewed commit.
6. Verify the published tag, notes and artifacts; close the completed milestone. Do not mark uncompleted work Done solely because a release was published.

Phase 1 has no tag-triggered publishing, deployment, release-creation Action or API orchestrator. Automation may check PRs; it cannot substitute for merge/release approval.
