# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 17 contract — one internal catalog, no observable change."""

from asqueel_migration.structures import json_equal

from asqueel import SqlBuilder, SqlMigrationRenderer, SqlPythonEmitter
from asqueel.catalog import SqlModelCatalog


class _CatalogRecipe(SqlBuilder):
    def main(self, root):
        db = root.db(name="catalog")
        schema = db.schemas().schema(name="public")
        tables = schema.tables()
        customer = tables.table(name="customer", pkey="id")
        customer_columns = customer.columns()
        customer_columns.column(name="id", dtype="serial")
        customer_columns.column(name="name", dtype="A", size="0:80")

        invoice = tables.table(name="invoice", pkey="id")
        invoice_columns = invoice.columns()
        invoice_columns.column(name="id", dtype="serial")
        customer_id = invoice_columns.column(name="customer_id", dtype="L")
        customer_id.relation(to="public.customer.id", foreign_key=True)
        invoice.virtual_columns().aliasColumn(
            name="customer_name", relation_path="@customer_id.name",
        )
        invoice.composites().compositeColumn(
            name="identity", columns="id,customer_id",
        )
        invoice.constraints().constraint(
            name="uq_invoice_customer",
            constraint_type="UNIQUE",
            columns="id,customer_id",
        )
        invoice.indexes().index(
            name="ix_invoice_customer", columns="customer_id",
        )
        db.extensions().extension(name="pg_trgm")


def test_shared_catalog_preserves_every_existing_boundary():
    # wf:contract: one ordered internal catalog owns database, schema, table,
    # wf:contract: column-family, constraint, index and relation discovery.
    # wf:contract: validator, migration renderer and emitter consume it instead
    # wf:contract: of parsing fixed path offsets in separate collectors.
    # wf:contract: the current source paths, normalized JSON and emitted recipe
    # wf:contract: remain unchanged throughout this preparatory phase.
    model = _CatalogRecipe()
    model.create()
    catalog = SqlModelCatalog(model)

    assert catalog.db_name == "catalog"
    assert list(catalog.schemas) == ["public"]
    assert list(catalog.extensions) == ["pg_trgm"]
    assert list(catalog.tables) == [
        ("public", "customer"),
        ("public", "invoice"),
    ]
    assert list(catalog.physical_columns) == [
        ("public", "customer", "id"),
        ("public", "customer", "name"),
        ("public", "invoice", "id"),
        ("public", "invoice", "customer_id"),
    ]
    assert list(catalog.virtual_columns) == [
        ("public", "invoice", "customer_name"),
    ]
    assert list(catalog.composites) == [("public", "invoice", "identity")]
    assert list(catalog.constraints) == [
        ("public", "invoice", "uq_invoice_customer"),
    ]
    assert list(catalog.indexes) == [
        ("public", "invoice", "ix_invoice_customer"),
    ]
    assert [path for path, _node in catalog.relations] == [
        "db.schemas.public.tables.invoice.columns.customer_id.relation_0",
    ]

    rendered = SqlMigrationRenderer(model).render()
    emitted = SqlPythonEmitter(model).emit()
    assert emitted == SqlPythonEmitter(model).emit()
    namespace = {}
    exec(compile(emitted, "<catalog-recipe>", "exec"), namespace)
    rebuilt = namespace["ImportedDatabase"]()
    rebuilt.create()
    assert json_equal(rendered, SqlMigrationRenderer(rebuilt).render())
