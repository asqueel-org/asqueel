# projects/gnrcore/packages/adm/model/sent_email.py
# SHA256: 52d74065aed1a460490475bb369b485f97173ec853e7f212580213f04c1000c1


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('sent_email', pkey='id', name_long='Sent email', name_plural='!!Sent email', caption_field='batch_key')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('code', name_long='!!Code')
        tbl.column('tbl', name_long='!!Table')
        tbl.column('mail_address', name_long='!!Email address')
        tbl.column('sent_ts', dtype='DH', name_long='!!Sent ts')
        tbl.column('record_id', name_long='Record id')
