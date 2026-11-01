# projects/test_invoice/packages/invc/model/invoice_note.py
# SHA256: fdf3e7d61cb64e9876bbfa273d7f45e5eebff48a0b23374a0ebca3d7550d55c3


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('invoice_note', pkey='id', name_long='!!Invoice Note', name_plural='!!Invoice Notes')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('invoice_id', size='22', group='_', name_long='!!Invoice').relation('invoice.id', relation_name='notes', onDelete='cascade', foreign_key=True)
        tbl.column('note_type', size=':20', name_long='!!Note Type')
        tbl.column('note_text', name_long='!!Note Text')
        tbl.column('priority', dtype='I', name_long='!!Priority')
        tbl.formulaColumn('is_warning', sql_formula='$note_type LIKE :warn_pat', var_warn_pat='WARN%%', dtype='B', name_long='Is Warning')
        tbl.formulaColumn('note_type_clean', sql_formula='UPPER(TRIM($note_type))', dtype='T', name_long='Note Type Clean')
        tbl.formulaColumn('created_date', sql_formula="date_trunc('day', $__ins_ts)", dtype='D', name_long='Created Date')
        tbl.formulaColumn('note_text_rtrim', sql_formula='RTRIM($note_text)', dtype='T', name_long='Note Text Rtrim')
