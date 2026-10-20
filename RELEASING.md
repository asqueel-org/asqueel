# Release Asqueel

Distribution: `asqueel`. Python package: `asqueel`.
Repository: `asqueel-org/asqueel`. Prepared version: `0.6.0` (unreleased).
See [CHANGELOG.md](CHANGELOG.md) for compatibility notes. Preparing and verifying
the artifacts does not publish them.

## One-time PyPI setup

While signed in as the intended PyPI owner, open
[Publishing](https://pypi.org/manage/account/publishing/) and add a pending GitHub
publisher with these exact values:

| Field | Value |
|---|---|
| PyPI project name | `asqueel` |
| GitHub owner | `asqueel-org` |
| Repository | `asqueel` |
| Workflow filename | `publish.yml` |
| GitHub environment | `release` |

A pending publisher does not reserve a project name. The first successful upload
creates the project. The repository must have a `release` environment matching this
configuration. No API token is required. See the official
[Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Verify before publishing

Run the test suite, build documentation, then run:

```sh
python -m build
python -m twine check --strict dist/*
python scripts/check_distribution.py dist/*
```

Verify the wheel in a fresh virtual environment with dependencies downloaded
from PyPI. Do not use an editable installation, the sibling migration checkout,
or a `PYTHONPATH` pointing to either repository:

```sh
python -m venv /tmp/asqueel-release-check
/tmp/asqueel-release-check/bin/python -m pip install --index-url https://pypi.org/simple 'dist/asqueel-0.6.0-py3-none-any.whl[dev]' pytest-cov
/tmp/asqueel-release-check/bin/python -m pip check
env -u PYTHONPATH /tmp/asqueel-release-check/bin/python scripts/check_installed.py
```

Run this against the same source snapshot used to build the wheel. The script
copies the tests, examples and all three invoice JSON fixtures into a temporary
directory and checks that imports come from the installed environment. The
source archive also includes these fixtures. Some existing integration fixtures
access PostgreSQL even without the `postgresql` marker; provide the disposable
test service configured through `GNR_TEST_PG_*`. Use `--postgresql` to include
the explicitly marked PostgreSQL tests as well.

Before tagging, ensure all required source modules and artifacts are tracked by
Git: a local build may include untracked files that a fresh CI checkout cannot
see. Keep the checkout stable during the verification.

The manual `publish.yml` workflow builds, validates and smoke-tests both artifacts;
it uploads to PyPI only when the selected ref is a matching `v*` version tag.
Do not create the release tag until the publisher configuration and release
contents have been reviewed. Uploaded PyPI files cannot be replaced in place.

## Dependency baseline

The wheel requires `genro-bag>=0.27.0,<0.28` and
`genro-builders>=0.27.0,<0.28`. Bag 0.28 no longer accepts the
`Bag(xml_string)` constructor used by the legacy XML importer; Builders 0.28
requires Bag 0.28. Keep the tested 0.27 APIs until their upgrade is addressed
separately. Toolbox requires `>=0.18.0` for mutable NamedList result rows.

The `migration` and `dev` extras require `asqueel-migration>=0.2.2,<0.3`;
development/CI requirements pin `0.2.2`. An allowed dependency range and a fixed
CI baseline have different purposes. Verify the resolved versions with the
installed wheel; tests against the sibling checkout do not certify PyPI packages.

Migration 0.2.2 was published on 2026-10-15. It includes UNIQUE removal using
real constraint/index names and `serial4` support; these are the reasons for the
new minimum. Verify the release against the package downloaded from PyPI, not
against the migration checkout or a locally built migration wheel. Earlier
compatibility checks with 0.1.2–0.2.1 do not cover these fixes.

Read the Docs project/account
configuration is independent of the checked-in Sphinx configuration.
