# projects/test_invoice/packages/invc/model/price_year.py
# SHA256: 48961724f864f130c2c59b42cf50ba684bbb075c67ae990418a10417d0562983


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('price_year', pkey='id', name_long='!!Price Year', name_plural='!!Price Years')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('product_id', size='22', group='_', name_long='!!Product').relation('product.id', relation_name='price_years', onDelete='cascade', foreign_key=True)
        tbl.column('year', dtype='L', name_long='!!Year')
        tbl.column('unit_price', dtype='money', name_long='!!Unit Price')
        tbl.column('note', name_long='!!Note')
        tbl.compositeColumn('product_year_key', columns='product_id,year', unique=True)
        tbl.formulaColumn('price_label', sql_formula="CAST($year AS TEXT) || ': ' || CAST($unit_price AS TEXT)", dtype='T', name_long='Price Label')
        tbl.aliasColumn('product_description', relation_path='@product_id.description', name_long='Product Description')
