# projects/gnrcore/packages/adm/model/notification.py
# SHA256: 7578129e611a533f1ed42a0d9f41afa3760d9b1e46aa2c60b254c9d4c3c9c6f8


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('notification', pkey='id', name_long='!!Notification', name_plural='!!Notifications', caption_field='title')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('title', name_long='!!Title')
        tbl.column('template', 'X', name_long='!!Template')
        tbl.column('confirm_label', name_long='!!Confirm label')
        tbl.column('tag_rule', name_long='!!Tag rule')
        tbl.column('group_code', name_long='!!Group code')
        tbl.column('all_users', 'B', name_long='!!For all users')
        tbl.column('letterhead_id', size='22', group='_', name_long='!!Letterhead').relation('htmltemplate.id', relation_name='notifications', foreign_key=True)
        tbl.column('linked_query', dtype='X', name_long='!![en]Linked query')
        tbl.column('dynamic_list', 'B', default=True, name_long='!!Dynamic list', name_short='!!Dynamic')
        tbl.column('start_date', 'D', name_long='!!Start date')
        tbl.column('end_date', 'D', name_long='!!End date')
        tbl.formulaColumn('existing_for_current_user', '\n                (EXISTS(SELECT * FROM adm.adm_user_notification AS un WHERE un.user_id=:env_user_id AND un.notification_id=#THIS.id))\n            ', dtype='B')
        tbl.formulaColumn('confirmed_count', select=dict(table='adm.user_notification', columns='COUNT(*)', where='$notification_id=#THIS.id AND $confirmed IS TRUE'), dtype='L', name_long='!!Confirmed users', name_short='!!Conf.users')
        tbl.formulaColumn('pending_count', select=dict(table='adm.user_notification', columns='COUNT(*)', where='$notification_id=#THIS.id AND $confirmed IS NOT TRUE'), dtype='L', name_long='!!Pending users', name_short='!!Pend.users')
