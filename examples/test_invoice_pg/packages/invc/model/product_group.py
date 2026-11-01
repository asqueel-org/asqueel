# projects/test_invoice/packages/invc/model/product_group.py
# SHA256: 843362e819ea035948036f0e4a441fed905998fc60c9693824beec19585fed41


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('product_group', pkey='id', name_long='!!Product group', name_plural='!!Product groups', caption_field='hierarchical_code')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.options().hierarchical('code,_row_count')
        tbl.options().counter()
        tbl.column('code', size=':10', name_long='!!Code')
        tbl.column('description', size=':50', name_long='!!Description')
