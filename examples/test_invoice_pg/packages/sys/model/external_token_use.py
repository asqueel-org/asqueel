# projects/gnrcore/packages/sys/model/external_token_use.py
# SHA256: ee364435e2f03033709beb2266076a538aac6c0b16d3363bebad595c5cfca92f


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('external_token_use', pkey='id', name_long='!!External token usage', name_plural='!!External token usages')
        tbl.column('id', size='22', name_long='!!id')
        tbl.column('external_token_id', size='22', name_long='!!External token id').relation('external_token.id', relation_name='usages', onDelete='cascade', foreign_key=True)
        tbl.column('datetime', 'DH', name_long='!!Date and Time')
        tbl.column('host', name_long='!!Host')
