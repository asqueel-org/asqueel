# Release Asqueel

Distribution: `asqueel`. Python package: `asqueel`.
Repository: `asqueel-org/asqueel`. Prepared version: `0.5.0`.

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

The manual `publish.yml` workflow builds, validates and smoke-tests both artifacts;
it uploads to PyPI only when the selected ref is a matching `v*` version tag.
Do not create the release tag until the publisher configuration and release
contents have been reviewed. Uploaded PyPI files cannot be replaced in place.

The `migration` and `dev` extras require `asqueel-migration>=0.1.2,<0.2`: asqueel uses its structure factories.
Validate the selected dependency version before release. The source revision in
`requirements/core.in` is a development/CI input, not wheel dependency metadata.

No PyPI upload is performed by the rename itself. Read the Docs project/account
configuration is independent of the checked-in Sphinx configuration.
