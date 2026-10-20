from gnr.sql.gnrsqlmodel import bagItemFormula

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
