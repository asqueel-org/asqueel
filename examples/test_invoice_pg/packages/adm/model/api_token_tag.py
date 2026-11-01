# projects/gnrcore/packages/adm/model/api_token_tag.py
# SHA256: 5b1f950098752fd888fe528d8460e4c09ea384c7b57738d0031816ff9c61f1f5


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('api_token_tag', pkey='id', name_long='!!API Token Tag', name_plural='!!API Token Tags')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('api_token_id', size='22', group='_', name_long='!!API Token').relation('api_token.id', relation_name='tags', onDelete='cascade', foreign_key=True)
        tbl.column('tag_id', size='22', group='_', name_long='!!Tag').relation('htag.id', relation_name='api_tokens', onDelete='cascade', foreign_key=True)
        tbl.aliasColumn('tag_code', '@tag_id.authorization_tag')
        tbl.aliasColumn('tag_description', '@tag_id.description')
