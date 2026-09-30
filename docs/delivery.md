# External delivery gate

Aggiornamento successivo: il [rapporto V1 nativo](native-v1-delivery.md) verifica
il migratore pubblicato su PyPI 0.1.0 e supera i precedenti expected failure.
Il testo seguente conserva la baseline storica, non lo stato corrente.

Status checked on 2026-08-24. This record describes local verified work; it
does not claim that an upstream release is available.

## Local upstream commits

- `dced81ca6e601d067a647727d4d329b63da2bb70` preserves explicit PostgreSQL
  index names and the zero-based `indoption` position used for descending
  columns.
- `2cb51a45c118a8d601d2d43da752fef792cc966c` quotes and escapes index
  identifiers in every dialect writer and rejects sort tokens other than
  `None` and `DESC` at the shared writer boundary.
- `bb3f425b229d9c4c988e308e164faa4c1b54fb7e` is the final readability-only
  cleanup of that shared escaping helper.

All three commits are local descendants of the checkout used by this workflow.
The current GitHub default branch was `main` at
`e64fa00b22b304263f515765bb44e5b74d9e9534` when checked.

## Public state

- `asqueel-org/asqueel-migration#8` is open and assigned to `fporcari`.
- No pull request currently carries these local commits.
- The repository currently has no GitHub release or tag.
- PyPI currently has no matching `asqueel-migration` distribution.
- `asqueel` therefore retains the existing non-invented lower bound
  `asqueel-migration>=0.1.0`; it does not claim that this version contains
  the two local fixes.

## Remaining external actions

1. Publish the local commits on an issue branch and open a pull request against
   the repository default branch. The PR body must contain `Fixes #8`, the PR
   must be assigned to its author, and an eligible reviewer must be requested.
2. After the required approvals, let the PR assignee merge it under the
   repository workflow.
3. Publish a release containing all three commits.
4. Only after that release exists, raise the `asqueel` migration minimum to
   its exact version and replace the sibling development-install command with
   `pip install -e ".[dev]"`.

No publish, pull request, merge or release action is part of this workflow.


## Verification on 2026-09-29

The public migration repository still points to
`e64fa00b22b304263f515765bb44e5b74d9e9534`; no tag or additional branch carries
the fixes above. The final cited commit is not retrievable from GitHub, and
issue #8 remains open. The dependency is therefore fixed to the available
public SHA in `requirements/*.txt` for reproducible tests.

The SQL source now uses Bag/Builders 0.27. With the public migrator, the two
remaining integration regressions are:

- authored index names and DESC inspection (PostgreSQL);
- missing `quote_identifier` in the dialect writer API.

The original regression assertions remain intact. Tests mark exactly these two
cases as strict expected failures only when installed migration metadata records
the SHA above. No exemption applies to another revision or an editable install;
`pytest --runxfail` disables the expectations. These failures are not fixed by
this SQL update, and the index behavior is not certified. There is no SQL-side
quoting workaround, monkeypatch of production writers or invented release.

Replace the pinned revision and remove the expectations after the upstream
fixes become available. The original local commit identifiers above remain
historical evidence, not installable dependency references.
