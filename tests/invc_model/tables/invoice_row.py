"""Invoice row table."""


def config_db(tables):
    table = tables.table("invoice_row", pkey="id")
    columns = table.columns()
    columns.column("id", dtype="serial")
    invoice_id = columns.column("invoice_id", dtype="L", notnull=True)
    invoice_id.relation(
        "invc.invoice.id", foreign_key=True, on_delete="CASCADE",
    )
    columns.column("line_no", dtype="I", notnull=True)
    columns.column("description", dtype="A", size="0:200", notnull=True)
    columns.column("quantity", dtype="N", size="10,2", notnull=True)
    columns.column("unit_price", dtype="N", size="12,2", notnull=True)

    constraints = table.constraints()
    constraints.constraint(
        "uq_invoice_row_line",
        constraint_type="UNIQUE",
        columns="invoice_id,line_no",
    )
    constraints.constraint(
        "ck_invoice_row_quantity",
        constraint_type="CHECK",
        check_clause="(quantity > 0)",
    )
    indexes = table.indexes()
    indexes.index(
        "ix_invoice_row_invoice_line", columns="invoice_id,line_no",
    )
    return table
