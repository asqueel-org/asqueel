# projects/gnrcore/packages/adm/model/htmltemplate.py
# SHA256: ec0430136127531ea582daddc4f263746f6269a54802fdc6240cc6a7f207eaf1


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('htmltemplate', pkey='id', name_long='!!Letterhead', name_plural='!!Letterheads', rowcaption='name')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('name', name_long='!!Name', validate_notnull=True)
        tbl.column('username', name_long='!!Username')
        tbl.column('version', name_long='!!Version')
        tbl.column('type_code', size=':15', name_long='Type').relation('letterhead_type.code', relation_name='letterheads', onDelete='raise', foreign_key=True)
        tbl.column('data', dtype='X', name_long='!!Data')
        tbl.column('center_height', dtype='I', name_long='!!Center height')
        tbl.column('center_width', dtype='I', name_long='!!Center width')
        tbl.column('based_on', size='22', group='_', name_long='!!Based on').relation('htmltemplate.id', relation_name='children', one_one=True, onDelete='raise', deferred=True, foreign_key=True)
        tbl.column('next_letterhead_id', size='22', group='_', name_long='!!Next letterhead').relation('htmltemplate.id', relation_name='previous', one_one=True, onDelete='raise', deferred=True, foreign_key=True)
