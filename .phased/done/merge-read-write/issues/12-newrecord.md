# Add newrecord, with default and default_from

## What is missing
There is no `newrecord` (nor `buildrecord`, `defaultValues`, `extendDefaultValues`, `recordCopy`). A project cannot build a new record with its defaults. A table whose columns declare `default`, `default_from` or `x_generation` cannot be written at all: `require_write_capabilities` refuses it before hooks and I/O with UnsupportedFeatureError.

## Evidence
- `src/asqueel/model_source.py:236-254` (`require_write_capabilities`)
- Already present: `checkPkey`, `newPkeyValue`, `pkeyValue`.

## References
- Legacy signature: `newrecord(assignId=False, resolver_one=None, _fromRecord=None, **kwargs)`; order `defaultValues()`, `recordCopy(_fromRecord)`, kwargs, `buildrecord`, `assignId` with `newPkeyValue`, `extendDefaultValues`.
- `recordToUpdate(insertMissing=True)` depends on it (see the recordToUpdate issue).
