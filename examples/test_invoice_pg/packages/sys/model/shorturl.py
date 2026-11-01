# projects/gnrcore/packages/sys/model/shorturl.py
# SHA256: 1f2a2e134e3f1d353753afb1c019c16ae0bf63ef93941f0d8b6a4d0e2d2b83f9


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('shorturl', pkey='codekey', pkey_columns='$domain,$key', name_long='Shorturl', name_plural='Shorturl', caption_field='shorturl')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('codekey', size=':100', name_long='Codekey')
        tbl.column('service_identifier', size=':60', group='_', name_long='Service').relation('service.service_identifier', relation_name='urls', onDelete='raise', foreign_key=True)
        tbl.column('longurl', name_long='Long url')
        tbl.column('shorturl', name_long='Short url', name_short='Short')
        tbl.column('domain', name_long='Domain')
        tbl.column('key', name_long='Key')
        tbl.column('expiration', 'D', name_long='Expiration')
        tbl.column('traking', dtype='X', name_long='Traking')
