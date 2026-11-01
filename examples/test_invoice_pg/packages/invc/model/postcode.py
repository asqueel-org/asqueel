# projects/test_invoice/packages/invc/model/postcode.py
# SHA256: 100df477a120d6e5cd7a18b3e303b9f0cedc38a4b105416181610c298bf985ef


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('postcode', name_long='Postcode', name_plural='Postcodes', pkey='id', caption_field='postcode', lookup=False)
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('postcode', size=':10', name_long='postcode', unique=False, indexed=True)
        tbl.column('suburb', size=':100', name_long='suburb')
        tbl.column('state', size=':5', name_long='state').relation('state.code', relation_name='postcodes', foreign_key=True)
        tbl.column('lat', name_long='lat')
        tbl.column('lon', name_long='lon')
