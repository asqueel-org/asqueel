"""Customer table."""


def config_db(tables):
    table = tables.table("customer", pkey="id", caption_field="name")
    columns = table.columns()
    columns.column("id", dtype="serial")
    columns.column("code", dtype="A", size="0:20", notnull=True, unique=True)
    columns.column("name", dtype="A", size="0:120", notnull=True)
    columns.column("vat_number", dtype="A", size="0:24")
    indexes = table.indexes()
    indexes.index("ix_customer_name", columns="name")
    return table
