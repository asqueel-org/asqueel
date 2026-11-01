# projects/test_invoice/packages/invc/model/price_year_note.py
# SHA256: e22bea4fdfce53faf64d1974ad8a3fc826ca613e8c156d1c6804277d3dc7e49f


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('price_year_note', pkey='id', name_long='!!Price Year Note', name_plural='!!Price Year Notes')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('product_id', size='22', group='_', name_long='!!Product').relation('product.id', relation_name='price_year_notes', onDelete='cascade', foreign_key=True)
        tbl.column('year', dtype='L', name_long='!!Year')
        tbl.compositeColumn('product_year_ref', columns='product_id,year').relation('price_year.product_year_key', foreign_key=False, relation_name='notes')
        tbl.column('note_text', name_long='!!Note Text')
        tbl.column('importance', dtype='I', name_long='!!Importance')
        tbl.aliasColumn('price_year_price', relation_path='@product_year_ref.unit_price', name_long='Price Year Price')
        tbl.aliasColumn('price_year_label', relation_path='@product_year_ref.price_label', name_long='Price Year Label')
        tbl.aliasColumn('product_description', relation_path='@product_year_ref.@product_id.description', name_long='Product Description')
