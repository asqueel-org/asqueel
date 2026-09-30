"""Readable acceptance checks for the modular invoicing model."""

from asqueel_migration.structures import json_equal

from asqueel import SqlMigrationRenderer, SqlPythonEmitter

from tests.invc_model.schema import InvoiceModel


def _model():
    model = InvoiceModel()
    model.create()
    model.validate_model()
    return model


def test_invoice_schema_is_explicit_and_complete():
    model = _model()
    prefix = "db.schemas.invc.tables"
    assert model.source[f"{prefix}.customer.columns.name"] is not None
    assert model.source[f"{prefix}.invoice.columns.customer_id.relation_0"] is not None
    assert model.source[f"{prefix}.invoice_row.columns.invoice_id.relation_0"] is not None
    assert model.source[f"{prefix}.invoice.constraints.uq_invoice_number"] is not None
    assert model.source[
        f"{prefix}.invoice_row.indexes.ix_invoice_row_invoice_line"
    ] is not None


def test_invoice_schema_emits_and_rebuilds_strictly():
    model = _model()
    expected = SqlMigrationRenderer(model).render()
    source = SqlPythonEmitter(model).emit(class_name="EmittedInvoiceModel")
    namespace = {}
    exec(compile(source, "<invoice-model>", "exec"), namespace)
    rebuilt = namespace["EmittedInvoiceModel"]()
    rebuilt.create()
    assert json_equal(expected, SqlMigrationRenderer(rebuilt).render())
