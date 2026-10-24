# Asqueel JS

Asqueel JS is the JavaScript package of Asqueel. It declares a model with the
same grammar as the Python package and runs it on SQLite. It targets local,
offline applications: the browser first, then Node.js and Bun.

- Package: `@asqueel/asqueel-js` on npm, Apache-2.0.
- Repository: <https://github.com/asqueel-org/asqueel-js>.
- Runtime: ES modules, Node.js 22.13 or later, Bun, or a browser worker.
- Database: SQLite only. PostgreSQL is not supported.

This chapter describes Asqueel JS 0.2.0. On 2026-10-24 the latest release on
npm is 0.1.1.

## Relation with the Python package

- The grammar is exported from the Python package. `npm run export:python`
  calls `SqlBuilder.to_grammar()` of Python Asqueel and writes
  `src/generated/grammar.json` and `src/generated/configuration-grammar.json`.
  The JavaScript `SqlBuilder` declares its elements from that file, so element
  and attribute names are the same in both languages.
- A model declared in JavaScript resolves to the same hierarchical model.
  `builder.toMigration()` returns the migration JSON of the model.
  `builder.resolve().toJSON()` exports the resolved model and
  `DbModel.fromJSON()` restores it.
- The test suite compares JavaScript with a pinned Python reference: model,
  migration JSON, SQL text, parameters and query results.
  `test/fixtures/provenance.json` records the reference commits.
- The package does not need Python at run time.
- Python classes do not cross the boundary. A table declared with
  `x_table_class` is refused when the model is resolved. Hooks and
  compiler callbacks are JavaScript functions registered at run time.

## Install

```sh
npm install @asqueel/asqueel-js
```

The package has these entry points:

| Import | Content |
|---|---|
| `@asqueel/asqueel-js` | `defineModel`, `SqlBuilder`, `DbModel`, error classes |
| `@asqueel/asqueel-js/sqlite` | `migrateSQLite`, `planSQLite`, `readSQLite` |
| `@asqueel/asqueel-js/adapters/node` | `openNodeSQLite` (`node:sqlite`) |
| `@asqueel/asqueel-js/adapters/bun` | `openBunSQLite` (`bun:sqlite`) |
| `@asqueel/asqueel-js/adapters/browser` | `openBrowserSQLite` (wa-sqlite on IndexedDB) |
| `@asqueel/asqueel-js/transfer` | `exportTransfer`, `importTransfer`, `readTransfer` |

## Minimal example

The example declares one table, creates it in an in-memory SQLite database,
inserts a row and reads it back on Node.js.

```js
import {defineModel} from '@asqueel/asqueel-js';
import {migrateSQLite} from '@asqueel/asqueel-js/sqlite';
import {openNodeSQLite} from '@asqueel/asqueel-js/adapters/node';

const model = defineModel(root => {
    const pkg = root.db({name: 'notes'}).packages()
        .package({name: 'app', sqlschema: 'main', sqlprefix: 'app'});
    const columns = pkg.tables().table({name: 'note', pkey: 'id'}).columns();
    columns.column({name: 'id', dtype: 'I'});
    columns.column({name: 'body', dtype: 'T'});
});
const adapter = openNodeSQLite(':memory:');
try {
    await migrateSQLite(adapter, model.toMigration());
    const notes = model.queries(adapter).table('app.note');
    await notes.insert({id: 1, body: 'A local note'});
    console.log(await notes.query({columns: '*', order_by: '$id'}).fetch());
} finally {
    await adapter.close();
}
```

The output is `[ { id: 1, body: 'A local note' } ]`. The physical table is
`app_note`: `sqlprefix` prefixes the table name.

- `model.queries(adapter).table(name)` returns `insert`, `update`, `delete`,
  `sql_insert` and `query`.
- `query(options)` returns `fetch()`, `fetchRecord()`, `count()` and `exists()`.
- `model.queries(adapter).transaction(async tx => ...)` runs several writes in
  one `BEGIN IMMEDIATE` ... `COMMIT`. An error in the callback rolls back.
- On Bun use `openBunSQLite`. In the browser use `openBrowserSQLite` inside a
  worker; the WASM file of wa-sqlite is served next to the bundle.

## Offline transfer

`exportTransfer` and `importTransfer` move a model and its data between Python
and SQLite in the browser. The model travels as a source Bag in TYTX, the
records as TYTX. The Python side is
`python/asqueel_transfer.py`, shipped in the npm package. Synchronisation of
the data stays with the application.

## Current limits

- SQLite only. The browser migrator accepts only implementation `sqlite` and
  the schema `main`.
- The migrator creates tables, primary keys, UNIQUE constraints, foreign keys
  and non-unique indexes. On an existing table it adds only nullable columns
  without UNIQUE and new indexes. It blocks type changes, removals, primary-key
  changes and tables absent from the model. It refuses CHECK constraints,
  views, triggers and generated columns found in an existing database.
- Nested transactions raise `TransactionStateError`.
- The Node.js and Bun adapters use synchronous drivers behind an asynchronous
  API. They do not move work to another thread.
- The browser adapter needs IndexedDB and Web Locks. A public worker API is not
  available yet; the caller coordinates direct access to the adapter.
- Many error messages of the package are in Italian.
- The repository files `docs/coverage.md` and `ROADMAP.md` list the features
  ported so far and the next steps.
