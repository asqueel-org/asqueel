# projects/gnrcore/packages/adm/model/user_notification.py
# SHA256: ab6f7f086c4312b5ef507c29cf8461d22a1c83647524a6863a1b5168155e9273


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('user_notification', pkey='id', name_long='User notification', name_plural='!!User notifications')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('user_id', size='22', group='_', name_long='!!User').relation('user.id', relation_name='user_notifications', onDelete='cascade', onDuplicate='ignore', foreign_key=True)
        tbl.column('notification_id', size='22', group='_', name_long='!!Notification').relation('notification.id', relation_name='notification_users', onDelete='cascade', onDuplicate='ignore', foreign_key=True)
        tbl.column('confirmed', dtype='B', name_long='!!Confirmed')
        tbl.column('notification', dtype='X', name_long='Custom Notification')
