# Export and import data files

A query writes its rows to a CSV, JSON or TYTX file, and a table inserts the
records of such a file. Both move the rows in blocks, so a large table never
sits in memory at once.

## Export the rows of a query

`fetch(destination=...)` writes the rows instead of returning them and returns
the number of rows written:

```python
products = db.table("shop.product")
products.query(columns="$code, $name, $price", where="$stock > 0").fetch(destination="products.tytx")
```

The query chooses columns and rows; `destination` is a path or an open text
stream. The format comes from the extension (`.csv`, `.json`, `.tytx`) or from
`format=`, which a stream without a file name requires and which wins over the
extension:

```python
from io import StringIO

out = StringIO()
products.query(columns="$code, $name").fetch(destination=out, format="csv")
```

The rows are read from a server-side cursor on PostgreSQL (`iterfetch`) and
written as they arrive. The file shapes:

- **CSV**: a header with the column names, then one line per row.
- **JSON**: an array of objects. Dates and times are ISO texts, decimals are texts.
- **TYTX**: one TYTX value per line, for example
  `{"code":"TEA","price":"1.50::N"}::JS`. It is the only format that keeps the
  types of the values.

## Import a file

`sql_insert` accepts an open text file and returns the number of rows inserted:

```python
with open("products.tytx", encoding="utf-8") as source:
    products.sql_insert(source)
products.sql_insert(StringIO("code,name\nMUG,Mug\n"), format="csv")
db.commit()
```

The import is the raw insert of `sql_insert`: no triggers run, missing keys are
assigned as for a list, and the records are inserted in blocks of 1000 with `executemany`. The
transaction is left to the caller.

## Adapt the values

CSV and JSON carry no types. With `adapt=True` every record passes through
`table.adaptRecord(record)` before the insert, which converts text values to
the dtype of their column: `'24'` becomes `24` in an `L` column, `'2026-10-20'`
a `date` in a `D` column, `'yes'` `True` in a `B` column. An empty CSV cell is
`None`. Values that already have a type stay as they are, so TYTX passes
unchanged.

`adapt` defaults to `True` for a file and to `False` for a record or a list,
which keeps the legacy raw insert. An explicit value always wins:

```python
products.sql_insert(rows_from_an_api, adapt=True)
products.sql_insert(source, adapt=False)  # values as they are in the file
```

A key that is not a column, or a text that does not convert, raises
`ValueError` naming the record, the column and the value.

The `Table` class of the table's module in a package folder can override
`adaptRecord` for its own rules:

```python
# <folder>/model/product.py
class Table:
    def adaptRecord(self, record):
        record = super().adaptRecord(record)
        record["code"] = record["code"].upper()
        return record
```
