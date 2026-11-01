# projects/gnrcore/packages/adm/model/group.py
# SHA256: 2edae1c79e42217cb98f3ebfdb145a2db4028905f4e092bbae23275e716bd20c


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('group', pkey='code', name_long='Group', name_plural='!!Groups', caption_field='description')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.options().counter()
        tbl.column('code', size=':15', name_long='!!Code', unmodifiable=True)
        tbl.column('description', name_long='!!Description')
        tbl.column('custom_menu', dtype='X', name_long='!!Custom menu')
        tbl.column('rootpage', name_long='!![en]Root Page')
        tbl.column('require_2fa', dtype='B', name_long='Require 2fa', name_short='2FA')
        tbl.column('no2fa_alternative_group', size=':15', group='_', name_long='Without 2FA').relation('adm.group.code', one_one=True, onDelete='setnull', foreign_key=True)
        tbl.formulaColumn('group_tags', "string_agg(#tg,',')", select_tg=dict(columns='$tag_code', where='$group_code=#THIS.code', distinct=True, table='adm.user_tag'), dtype='A')
