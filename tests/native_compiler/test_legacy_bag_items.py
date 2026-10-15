"""Seven unchanged helper test bodies, adapted to the internal translation boundary.

Asqueel exposes no new bagItemFormula method: this test-only adapter calls the
path translator and dialect used by native bagItemColumn compilation.
"""
import pytest

from asqueel import build_database
from examples.test_invoice_pg import source
from asqueel.compiler import _bag_item_path
from asqueel.dialects.postgres import PostgresDialect


def bagItemFormula(*, bagcolumn, itempath, dtype, kwargs):
    kwargs['var_calculated_path'] = _bag_item_path(itempath)
    return PostgresDialect().bag_item_formula(bagcolumn, dtype)


class TestHelpers:

    def test_bagItemFormula_text(self):
        kw = {}
        result = bagItemFormula(bagcolumn='$details', itempath='a.b', dtype='T', kwargs=kw)
        assert 'xpath' in result
        assert 'var_calculated_path' in kw
        assert kw['var_calculated_path'] == '/GenRoBag/a/b/text()'

    def test_bagItemFormula_numeric(self):
        kw = {}
        result = bagItemFormula(bagcolumn='$details', itempath='x.y', dtype='N', kwargs=kw)
        assert 'numeric' in result

    def test_bagItemFormula_positional_index(self):
        kw = {}
        bagItemFormula(bagcolumn='$col', itempath='#0.item', dtype='T', kwargs=kw)
        assert '*[1]' in kw['var_calculated_path']

    def test_bagItemFormula_xml_attribute(self):
        kw = {}
        bagItemFormula(bagcolumn='$col', itempath='a.b?myattr', dtype='T', kwargs=kw)
        assert '@myattr' in kw['var_calculated_path']

    def test_bagItemFormula_integer(self):
        kw = {}
        result = bagItemFormula(bagcolumn='$details', itempath='x.y', dtype='I', kwargs=kw)
        assert 'integer' in result

    def test_bagItemFormula_timestamp(self):
        kw = {}
        result = bagItemFormula(bagcolumn='$details', itempath='x.y', dtype='DH', kwargs=kw)
        assert 'timestamp without time zone' in result

    def test_bagItemFormula_unknown_dtype_falls_back_to_text(self):
        # issue #22: unresolved dtypes must not raise KeyError
        kw = {}
        result = bagItemFormula(bagcolumn='$details', itempath='x.y', dtype='money', kwargs=kw)
        assert 'xpath' in result
        assert 'money' not in result


# Legacy model/table tests adapted to native metadata and compile-time SQL.
# No table.bagItemFormula API is added solely to reproduce a legacy helper.


@pytest.fixture(scope='module')
def invoice():
    with build_database(source()) as db:
        yield db


def test_bag_item_column(invoice):
    table = invoice.model.table('invc.product')
    virtual_columns = {name for name, column in table.columns.items() if column.is_virtual}
    assert 'detail_weight' in virtual_columns
    assert 'detail_color' in virtual_columns


def test_bagItemFormula(invoice):
    column = invoice.model.table('invc.product').columns['detail_weight']
    kwargs = {}
    result = bagItemFormula(bagcolumn=column.attributes['bagcolumn'],
                            itempath=column.attributes['itempath'], dtype=column.dtype, kwargs=kwargs)
    assert isinstance(result, str)
    assert 'xpath' in result
    assert 'numeric' in result
    assert 'var_calculated_path' in kwargs
    assert kwargs['var_calculated_path'] == '/GenRoBag/specs/weight/text()'


def test_bagItemColumn_custom_dtype(invoice):
    column = invoice.model.table('invc.product').columns['detail_price']
    assert column is not None
    assert column.dtype == 'N'
    assert column.attributes['size'] == '14,2'
    assert 'numeric' in invoice.table('invc.product').query('$detail_price').compiled.sql


def test_tableobj_bagItemFormula_custom_dtype(invoice):
    column = invoice.model.table('invc.product').columns['detail_price']
    kwargs = {}
    result = bagItemFormula(bagcolumn='$details', itempath='specs.price',
                            dtype=column.dtype, kwargs=kwargs)
    assert 'numeric' in result
