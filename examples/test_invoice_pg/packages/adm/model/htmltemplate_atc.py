# projects/gnrcore/packages/adm/model/htmltemplate_atc.py
# SHA256: 1bb40a448344e1c3b72062d6ed80f4fb6858ef85b05b5aa0f2d4b191463f86eb


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('htmltemplate_atc', pkey='id', caption_field='description', rowcaption='$description',
                        name_long='!!Letterhead  Attachment', name_plural='!!Letterhead Attachments')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.options().counter('maintable_id')
        tbl.column('id', size='22', group='_', name_long='Id')
        tbl.column('filepath', name_long='!![en]Filepath')
        tbl.column('filepath_hash', name_long='MD5 hash')
        tbl.column('filepath_original_name', name_long='!![en]Original name')
        tbl.column('external_url', name_long='!![en]External url')
        tbl.column('description', name_long='!![en]Description')
        tbl.column('mimetype', name_long='!![en]Mimetype')
        tbl.column('text_content', name_long='!![en]Content')
        tbl.column('info', dtype='X', name_long='!![en]Additional info')
        tbl.column('is_foreign_document', dtype='B', name_long='!![en][Is foreign document]', name_short='!![en]Ext')
        tbl.column('maintable_id', size='22', group='*', name_long='htmltemplate').relation(
            'htmltemplate.id', relation_name='atc_attachments', onDelete='cascade', onDelete_sql='cascade',
            onDuplicate=False, deferred=True)
        tbl.formulaColumn('adapted_url', """CASE WHEN position('\\:' in $filepath)>0 THEN '/'||$filepath
             ELSE '/_vol/' || $filepath
            END""", group='_')
        tbl.pyColumn('fileurl', dtype='T', method='filepath_endpoint_url', name_long='Fileurl',
                     required_columns='$external_url,$filepath', static=True)
        tbl.pyColumn('missing_file', dtype='B', method='pyColumn_missing_file', name_long='Missing file')
        tbl.pyColumn('full_external_url', dtype='T', method='pyColumn_full_external_url', name_long='Full external url')
