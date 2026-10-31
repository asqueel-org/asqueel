# projects/gnrcore/packages/adm/model/ckstyle.py
# SHA256: 667119d0c8147361e933aa919c48d0bdaee6180093baf9c7aef13cdb3edc1db3


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('ckstyle', pkey='id', name_long='Ckeditor style', name_plural='!!Ckeditor styles', caption_field='name', lookup=True)
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('name', name_long='!!Name')
        tbl.column('element', validate_values='div,span,h1,h2,h3', name_long='!!Dom element', name_short='Element')
        tbl.column('styles', name_long='!!Styles')
        tbl.column('attributes', name_long='!!Attributes')
        tbl.column('stylegroup', name_long='!!Group')
        tbl.formulaColumn('sgroup', "COALESCE($stylegroup,'')", dtype='A')
