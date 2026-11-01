# projects/test_invoice/packages/invc/model/product_type.py
# SHA256: f8a6bc9a38bd27e366a60e3c14367092eb47e15cf119aa280fd64a410916ba0f


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('product_type', pkey='id', name_long='!!Product type', name_plural='!!Product types', caption_field='hierarchical_description')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.options().hierarchical('description')
        tbl.options().counter()
        tbl.options().df()
        tbl.column('description', size=':50', name_long='!!Description')
