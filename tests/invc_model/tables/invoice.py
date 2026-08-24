"""Invoice header table."""


def config_db(tables):
    table = tables.table("invoice", pkey="id", caption_field="number")
    columns = table.columns()
    columns.column("id", dtype="serial")
    columns.column("number", dtype="A", size="0:24", notnull=True)
    customer_id = columns.column("customer_id", dtype="L", notnull=True)
    customer_id.relation(
        "invc.customer.id", foreign_key=True, on_delete="RESTRICT",
    )
    columns.column("invoice_date", dtype="D", notnull=True)
    columns.column("total", dtype="N", size="12,2", notnull=True)

    constraints = table.constraints()
    constraints.constraint(
        "uq_invoice_number", constraint_type="UNIQUE", columns="number",
    )
    constraints.constraint(
        "ck_invoice_total", constraint_type="CHECK", check_clause="(total >= 0)",
    )
    indexes = table.indexes()
    indexes.index(
        "ix_invoice_customer_date", columns="customer_id,invoice_date",
    )
    return table
