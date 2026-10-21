# Release Asqueel

Distribution: `asqueel`. Python package: `asqueel`.
Repository: `asqueel-org/asqueel`. Release version: `0.6.3`.
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
/tmp/asqueel-release-check/bin/python -m pip install --index-url https://pypi.org/simple 'dist/asqueel-0.6.3-py3-none-any.whl[dev]' pytest-cov
/tmp/asqueel-release-check/bin/python -m pip check
env -u PYTHONPATH /tmp/asqueel-release-check/bin/python scripts/check_installed.py --workers 2
```

Run this against the same source snapshot used to build the wheel. The script
copies the tests, examples and all three invoice JSON fixtures into a temporary
directory and checks that imports come from the installed environment. The
source archive also includes these fixtures. Some existing integration fixtures
access PostgreSQL even without the `postgresql` marker; provide the disposable
test service configured through `GNR_TEST_PG_*`. Use `--postgresql` to include
the explicitly marked PostgreSQL tests as well.

`--workers 2` uses pytest-xdist to distribute whole test files between two
processes. This retains module-scoped fixtures and runs every selected test;
pytest-cov combines both workers into the same coverage report. Temporary
PostgreSQL database names are unique per fixture invocation. Omit `--workers`
(or use `--workers 0`) to reproduce a serial run. The checker prints the twenty
slowest test phases to make performance regressions visible in CI logs.

Before tagging, ensure all required source modules and artifacts are tracked by
Git: a local build may include untracked files that a fresh CI checkout cannot
see. Keep the checkout stable during the verification.

The manual `publish.yml` workflow builds, validates and smoke-tests both artifacts;
it uploads to PyPI only when the selected ref is a matching `v*` version tag.
Do not create the release tag until the publisher configuration and release
contents have been reviewed. Uploaded PyPI files cannot be replaced in place.

## Dependency policy

The wheel requires `genro-bag>=0.28.0`,
`genro-builders>=0.29.0` and `genro-toolbox>=0.18.0`.
The `migration` and `dev` extras require `asqueel-migration>=0.3.1`.
Internal tools have minimum versions only: do not add upper bounds to hide
regressions. Fix incompatibilities with the latest published versions instead.
The full CI matrix installs `requirements/*.in` with eager upgrades, including
transitive dependencies, so new releases are exercised by the existing suites.
The `requirements/*.txt` files are reproducible snapshots for diagnosis only;
they do not select CI dependencies.

Verify the resolved versions with the installed wheel; tests against a sibling
checkout do not certify PyPI packages.

Migration 0.3.1 was published on 2026-10-20. Verify SQLite (file and memory) and
PostgreSQL creation, introspection, empty second diff and schema evolution using
the package downloaded from PyPI. Include generated columns, `serial4`, indexes,
foreign keys, refused unsupported changes and DDL rollback.

## Publish and confirm

Check both Git tags and PyPI before selecting a version: a successful tag-triggered
publication does not create a GitHub Release automatically. Never reuse a version
already uploaded to PyPI. After the release commit passes CI and is merged, tag
that commit, push the tag, and wait for `publish.yml` to succeed. Create the GitHub
Release from the same tag and changelog. Finally install the published package
with its `migration` extra in a fresh environment and repeat the migration checks.

## CI events

The full test matrix runs once per pull request revision and again after a merge
or direct push to `main`, to verify the integrated commit. Topic-branch pushes do
not start a second copy. A newer revision cancels the previous run of that same
PR; main and manual runs remain independent. The required job names and test
coverage are unchanged.

Version tags trigger only `publish.yml`, which builds, validates and smoke-tests
the distributions before uploading them. They do not restart the full test
matrix. Publish from the verified release commit. Use `workflow_dispatch` only
when an additional full test run is deliberately needed; prefer rerunning a
failed job instead of starting a duplicate run on the same commit.

Read the Docs project/account
configuration is independent of the checked-in Sphinx configuration.
