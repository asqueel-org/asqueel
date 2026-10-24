"""Native declarations transcribed from original config_db methods.

No GenroPy imports or expanded legacy fixtures are needed.
"""


# projects/gnrcore/packages/adm/model/_packages/sys/task.py
# SHA256: 40abd0b1f867381eb96213aaa8444ee770fecc378014a24bc148685d928e4fc9
def sys_task_contribution(pkg):
    tbl = pkg.table('task')
    tbl.column('user_id').relation('adm.user.id', onDelete='raise', foreign_key=True)


# projects/gnrcore/packages/adm/model/access_group.py
# SHA256: e2bcddd3ce1b79cfade1e83b8d365c81adfb2cf325abcd8d0b9da83d22ce2811
def access_group(pkg):
    tbl = pkg.table('access_group', pkey='code', name_long='!!Access group', name_plural='!!Access group', caption_field='code')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':10', name_long='!!Code')
    tbl.column('description', size=':30', name_long='!!Description')
    tbl.column('allowed_ip', name_long='!!Allowed ip')


# projects/gnrcore/packages/adm/model/api_token.py
# SHA256: 898e68417949db2b2989bb026a2fa03741416b5c15c864b8a3308da5488d4370
def api_token(pkg):
    tbl = pkg.table('api_token', pkey='id', name_long='!!API Token', name_plural='!!API Tokens', rowcaption='$description')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('token', size='64', unique=True, indexed=True, name_long='!!Token')
    tbl.column('description', name_long='!!Description')
    tbl.column('group_code', size=':15', name_long='!!Group').relation('group.code', relation_name='api_tokens', foreign_key=True)
    tbl.column('is_active', dtype='B', default=True, name_long='!!Active')
    tbl.column('expires_ts', dtype='DHZ', name_long='!!Expires')
    tbl.column('activated_ts', dtype='DHZ', name_long='!!Activated')
    tbl.column('last_used_ts', dtype='DHZ', name_long='!!Last Used')
    tbl.column('created_by', size='22', group='_', name_long='!!Created By').relation('adm.user.id', foreign_key=False, relation_name='api_tokens', onDelete='setnull')
    tbl.column('notes', dtype='T', name_long='!!Notes')
    tbl.column('token_hint', size='8', name_long='!!Token Hint')
    tbl.formulaColumn('all_tags', select=dict(table='adm.api_token_tag', columns='@tag_id.authorization_tag', where='$api_token_id=#THIS.id'), dtype='A', name_long='!!Tags')
    tbl.formulaColumn('status', "CASE\n                 WHEN $token IS NULL THEN 'to_activate'\n                 WHEN $is_active IS NOT TRUE THEN 'inactive'\n                 WHEN $expires_ts IS NOT NULL AND $expires_ts < CURRENT_TIMESTAMP THEN 'expired'\n                 ELSE 'active'\n               END", dtype='A', name_long='!!Status')


# projects/gnrcore/packages/adm/model/api_token_tag.py
# SHA256: 5b1f950098752fd888fe528d8460e4c09ea384c7b57738d0031816ff9c61f1f5
def api_token_tag(pkg):
    tbl = pkg.table('api_token_tag', pkey='id', name_long='!!API Token Tag', name_plural='!!API Token Tags')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('api_token_id', size='22', group='_', name_long='!!API Token').relation('api_token.id', relation_name='tags', onDelete='cascade', foreign_key=True)
    tbl.column('tag_id', size='22', group='_', name_long='!!Tag').relation('htag.id', relation_name='api_tokens', onDelete='cascade', foreign_key=True)
    tbl.aliasColumn('tag_code', '@tag_id.authorization_tag')
    tbl.aliasColumn('tag_description', '@tag_id.description')


# projects/gnrcore/packages/adm/model/audit.py
# SHA256: c8ce9d0bbf37f451955a3ec9cfa76164ff3f97c4b242413f59c5cee6608fe11c
def audit(pkg):
    tbl = pkg.table('audit', pkey='id', name_long='!!Audit', name_plural='!!Audit')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('tablename', name_long='!!Table name')
    tbl.column('event', size='1', name_long='!!Change type', validate_values='I:Insert,U:Update,D:Delete')
    tbl.column('username', name_long='!!User')
    tbl.column('record_pkey', name_long='!!Record Pkey')
    tbl.column('version', 'L', name_long='!!Version')
    tbl.column('data', 'X', name_long='!!Data')
    tbl.column('transaction_id', name_long='!!Transaction id')


# projects/gnrcore/packages/adm/model/authorization.py
# SHA256: c1b4f9bd9f66abd88248db86c43965fc432140c9b2396fded98ea868077d30e2
def authorization(pkg):
    tbl = pkg.table('authorization', pkey='code', name_long='!!Authorization', name_plural='!!Authorizations')
    tbl.options().sysFields(id=False, user_ins=True, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':8', validate_case='U', name_long='!!Code', unmodifiable=True)
    tbl.column('user_id', size='22', name_long='!!User id').relation('user.id', foreign_key=True)
    tbl.column('use_ts', 'DH', name_long='!!Used datetime')
    tbl.column('used_by', name_long='!!Used by')
    tbl.column('note', name_long='!!Note')
    tbl.column('usage_scope', name_long='!!Use Scope')
    tbl.column('remaining_usages', 'L', name_long='!!Remaining usages', default=1)
    tbl.column('expiry_date', 'D', name_long='!!Expire Date')


# projects/gnrcore/packages/adm/model/backup.py
# SHA256: 0d32c160befdec3f83a27ae4782e3ac278fdc071a14023441053bc54e40fcc77
def backup(pkg):
    tbl = pkg.table('backup', pkey='id', name_long='!!Backup', name_plural='!!Backups', rowcaption='$name')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('name', name_long='!!Name')
    tbl.column('start_ts', dtype='DH', name_long='!!Backup start ts')
    tbl.column('end_ts', dtype='DH', name_long='!!Backup end ts')
    tbl.column('file_url', name_long='!!Download')
    tbl.formulaColumn('completed', '$end_ts IS NOT NULL', name_long='!!Completed', dtype='A')


# projects/gnrcore/packages/adm/model/ckstyle.py
# SHA256: 667119d0c8147361e933aa919c48d0bdaee6180093baf9c7aef13cdb3edc1db3
def ckstyle(pkg):
    tbl = pkg.table('ckstyle', pkey='id', name_long='Ckeditor style', name_plural='!!Ckeditor styles', caption_field='name', lookup=True)
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('name', name_long='!!Name')
    tbl.column('element', validate_values='div,span,h1,h2,h3', name_long='!!Dom element', name_short='Element')
    tbl.column('styles', name_long='!!Styles')
    tbl.column('attributes', name_long='!!Attributes')
    tbl.column('stylegroup', name_long='!!Group')
    tbl.formulaColumn('sgroup', "COALESCE($stylegroup,'')", dtype='A')


# projects/gnrcore/packages/adm/model/connection.py
# SHA256: 25922e6b4bcbf3572306f958aad3c16e73cf77c2f1ba242feb0b4a449065d08f
def connection(pkg):
    tbl = pkg.table('connection', pkey='id', name_long='!!Connection', name_plural='!!Connections')
    tbl.options().enabled_when(preference='adm.dev.connection_log_enabled')
    tbl.column('id', size='22', name_long='!!Connection id')
    tbl.column('userid', size='22', name_long='!!Userid').relation('user.id', foreign_key=False)
    tbl.column('username', size=':32', name_long='!!Username')
    tbl.column('ip', size=':255', name_long='!!Ip address')
    tbl.column('start_ts', 'DH', name_long='!!Start TS')
    tbl.column('end_ts', 'DH', name_long='!!End TS')
    tbl.column('end_reason', size=':12', name_long='!!End reason')
    tbl.column('user_agent', name_long='!!User agent')
    tbl.aliasColumn('user_fullname', relation_path='@userid.fullname', name_long='!!User fullname')


# projects/gnrcore/packages/adm/model/counter.py
# SHA256: 543fa4c606a978c6befb783874c7de0b3318b0e04a958e94787cce92398e5332
def counter(pkg):
    tbl = pkg.table('counter', pkey='codekey', pkey_columns='pkg,tbl,code,fld,period', name_long='!!Counter')
    tbl.options().sysFields(id=False, ins=True, upd=True, user_upd=False, group_name='!![en]System')
    tbl.column('codekey', size=':80', readOnly=True, name_long='!!Codekey', indexed=True)
    tbl.column('code', size=':12', readOnly=True, name_long='!!Code')
    tbl.column('pkg', size=':12', readOnly=True, name_long='!!Package')
    tbl.column('tbl', size=':30', readOnly=True, name_long='!!Table')
    tbl.column('fld', size=':30', readOnly=True, name_long='!!Counter Field')
    tbl.column('period', size=':10', name_long='!!Period', indexed=True)
    tbl.column('counter', 'L', name_long='!!Counter')
    tbl.column('last_used', 'D', name_long='!!Last used')
    tbl.column('holes', 'X', name_long='!!Holes')
    tbl.column('errors', 'X', name_long='!!Errors')


# projects/gnrcore/packages/adm/model/day.py
# SHA256: c30d7f03c80d4c9e84dea55821b9e491357653eda9a12df323d2edd9022738ca
def day(pkg):
    tbl = pkg.table('day', pkey='date', name_long='!!Days', name_plural='!!Days', caption_field='date')
    tbl.column('date', dtype='D', name_long='!!Date')
    tbl.column('weekday', dtype='L', name_long='!!Weekday')
    tbl.column('is_holyday', dtype='B', name_long='!!Is holyday')


# projects/gnrcore/packages/adm/model/group.py
# SHA256: 2edae1c79e42217cb98f3ebfdb145a2db4028905f4e092bbae23275e716bd20c
def group(pkg):
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


# projects/gnrcore/packages/adm/model/group_helpdoc.py
# SHA256: a27d57f7946d10830b47b418919836e72d60a76994522addeec2f29dee32aee5
def group_helpdoc(pkg):
    tbl = pkg.table('group_helpdoc', pkey='id', name_long='!![en]Help document for group', name_plural='!![en]Help documents for group', caption_field='')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.options().counter('group_code')
    tbl.column('group_code', size=':15', group='_', name_long='Group').relation('group.code', relation_name='helpdocs', onDelete='raise', foreign_key=True)
    tbl.column('helpdoc_id', size='22', group='_', name_long='Help document').relation('helpdoc.id', relation_name='connected_groups', onDelete='cascade', foreign_key=True)
    tbl.aliasColumn('url', '@helpdoc_id.url', name_long='Url', static=True)


# projects/gnrcore/packages/adm/model/helpdoc.py
# SHA256: 7f362f8b23a22928a3cedb9d469bb370ca88d64caaeca1c45da10759fc0a810e
def helpdoc(pkg):
    tbl = pkg.table('helpdoc', pkey='id', name_long='!![en]Help document', name_plural='!![en]Help documents', caption_field='title', lookup=True)
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('title', size=':25', name_long='Title')
    tbl.column('url', name_long='Url')
    tbl.column('description', name_long='Description')


# projects/gnrcore/packages/adm/model/htag.py
# SHA256: cc1c146c9c1315b878a216e630cd1881cad9bf1dec99f0f08755e66d53827270
def htag(pkg):
    tbl = pkg.table('htag', pkey='id', name_long='!!Tag', rowcaption='$code,$description', caption_field='hierarchical_description', newrecord_caption='!!New tag')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System', syscode=True)
    tbl.options().hierarchical('code,description')
    tbl.options().counter()
    tbl.column('code', name_long='!!Code', validate_notnull=True, validate_nodup=True, unique=True)
    tbl.column('description', name_long='!!Description', validate_notnull=True)
    tbl.column('require_2fa', dtype='B', name_long='Require 2fa')
    tbl.column('isreserved', 'B', name_long='!!Reserved')
    tbl.column('note', name_long='!!Notes')
    tbl.column('linked_table', name_long='Linked table')
    tbl.formulaColumn('authorization_tag', 'COALESCE($__syscode,$hierarchical_code)', dtype='A')


# projects/gnrcore/packages/adm/model/htmltemplate.py
# SHA256: ec0430136127531ea582daddc4f263746f6269a54802fdc6240cc6a7f207eaf1
def htmltemplate(pkg):
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


# projects/gnrcore/packages/adm/model/htmltemplate_atc.py
# SHA256: 1bb40a448344e1c3b72062d6ed80f4fb6858ef85b05b5aa0f2d4b191463f86eb
def htmltemplate_atc(pkg):
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


# projects/gnrcore/packages/adm/model/install_checklist.py
# SHA256: 20ed0176b4a46a0ae2d9d5a364bc0845d45beae0898ad1c33472b02362fbf813
def install_checklist(pkg):
    tbl = pkg.table('install_checklist', pkey='__syscode', name_long='!!Install checklist', name_plural='!!Install checklist', caption_field='description')
    tbl.options().sysFields(id=False, ins=False, upd=False, user_upd=False, group_name='!![en]System')
    tbl.column('__syscode', size=':20', unique=True, indexed=True, name_long='!![en]Internal code')
    tbl.column('name', name_long='!!Name')
    tbl.column('description', name_long='!!Description')
    tbl.column('pkg', size=':20', name_long='!!Package')
    tbl.column('checked', dtype='B', name_long='!!Checked')
    tbl.column('check_ts', dtype='DH', name_long='!!Check ts')
    tbl.column('check_user', size=':30', name_long='!!Check user')
    tbl.column('annotations', name_long='!!Annotations')
    tbl.column('doc_url', name_long='!!Documentation url', name_short='!!Url')


# projects/gnrcore/packages/adm/model/language.py
# SHA256: dc068abbcdb347fc06b21606c7396c4f730fd8a8ba4ae859f2fc103c8eab70e4
def language(pkg):
    tbl = pkg.table('language', pkey='code', name_long='Language', name_plural='!!Languages', lookup=True, caption_field='name')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System', syscode=True)
    tbl.options().counter()
    tbl.column('code', size=':2', name_long='!!Code')
    tbl.column('name', name_long='!!Name')


# projects/gnrcore/packages/adm/model/letterhead_type.py
# SHA256: 114c622198873165bf4ce131aa830cfd6d54d4abcedf23e0c02c428ca31311e8
def letterhead_type(pkg):
    tbl = pkg.table('letterhead_type', pkey='code', name_long='Letterhead type', name_plural='Letterhead types', lookup=True)
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':15', name_long='!!Code', indexed=True, unique=True, validate_notnull='Required')
    tbl.column('description', name_long='!!Description')


# projects/gnrcore/packages/adm/model/menu.py
# SHA256: 724f702d49e10f513c8d96257437d76927560437603148f006e3ab2f167584fe
def menu(pkg):
    tbl = pkg.table('menu', pkey='id', name_long='!!Menu Directory', name_plural='!!Menu Directories', rowcaption='$hierarchical_label', caption_field='hierarchical_label')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.options().hierarchical('label')
    tbl.options().counter()
    tbl.column('label', name_long='!!Label')
    tbl.column('tags', name_long='!!Tags')
    tbl.column('summary', name_long='!!Summary')
    tbl.column('ts_import', dtype='DH')
    tbl.column('page_id', size='22').relation('menu_page.id', relation_name='links', foreign_key=True)
    tbl.aliasColumn('page_label', relation_path='@page_id.label')
    tbl.aliasColumn('page_filepath', relation_path='@page_id.filepath')
    tbl.aliasColumn('page_tbl', relation_path='@page_id.tbl')
    tbl.aliasColumn('page_metadata', relation_path='@page_id.metadata')


# projects/gnrcore/packages/adm/model/menu_page.py
# SHA256: e50d123b5757086f20bea8d9254e4bd4842e956bf089c4402dc49d2bac8335cf
def menu_page(pkg):
    tbl = pkg.table('menu_page', pkey='id', name_long='!!Menu Page', name_plural='!!Menu Pages', rowcaption='$label', caption_field='label')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('label', name_long='!!Label')
    tbl.column('filepath', name_long='!!Filepath')
    tbl.column('tbl', name_long='!!Table')
    tbl.column('pkg', name_long='!!Package')
    tbl.column('metadata', name_long='!!Metadata')


# projects/gnrcore/packages/adm/model/notification.py
# SHA256: 7578129e611a533f1ed42a0d9f41afa3760d9b1e46aa2c60b254c9d4c3c9c6f8
def notification(pkg):
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


# projects/gnrcore/packages/adm/model/pkginfo.py
# SHA256: 0e081ed451e78bafb6150236e41b1827c62b0b07be44a0b534a3277e4e3750b1
def pkginfo(pkg):
    tbl = pkg.table('pkginfo', pkey='pkgid', name_long='!!Package info', name_plural='!!Package info', caption_field='pkgid')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('pkgid', size=':50', name_long='!!Package')
    tbl.column('prj', size=':50', name_long='!!Project')


# projects/gnrcore/packages/adm/model/preference.py
# SHA256: ba074cf58b4bf21b1f2f6728e0a232d54728d69fd28b6e0c1d619d1d9235fa86
def preference(pkg):
    tbl = pkg.table('preference', pkey='code', name_long='!!Preference', name_plural='!!Preference')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size='12', name_long='!!Code')
    tbl.column('data', 'X', name_long='!!Data')


# projects/gnrcore/packages/adm/model/record_tag.py
# SHA256: 06c231ecc1dc94753ece00060d0bf48934346331da8171ebe0d120eec74abf6c
def record_tag(pkg):
    tbl = pkg.table('record_tag', pkey='id', name_long='!!Table tag', name_plural='!!Table tags')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('tablename', name_long='!!Table name')
    tbl.column('tag', name_long='!!Tag')
    tbl.column('description', name_long='!!Description')


# projects/gnrcore/packages/adm/model/sent_email.py
# SHA256: 52d74065aed1a460490475bb369b485f97173ec853e7f212580213f04c1000c1
def sent_email(pkg):
    tbl = pkg.table('sent_email', pkey='id', name_long='Sent email', name_plural='!!Sent email', caption_field='batch_key')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('code', name_long='!!Code')
    tbl.column('tbl', name_long='!!Table')
    tbl.column('mail_address', name_long='!!Email address')
    tbl.column('sent_ts', dtype='DH', name_long='!!Sent ts')
    tbl.column('record_id', name_long='Record id')


# projects/gnrcore/packages/adm/model/served_page.py
# SHA256: 863a47ed32e3331267bb05444af93faa090348da282ec17c6ec14110c5c09761
def served_page(pkg):
    tbl = pkg.table('served_page', pkey='page_id', name_long='!!Served page', name_plural='!!Served pages')
    tbl.options().enabled_when(preference='adm.dev.connection_log_enabled')
    tbl.column('page_id', size='22', name_long='!!Page id')
    tbl.column('pagename', name_long='!!Page name')
    tbl.column('connection_id', size='22', group='_').relation('connection.id', relation_name='pages', onDelete='cascade', foreign_key=True)
    tbl.column('start_ts', 'DH', name_long='!!Start ts')
    tbl.column('end_ts', 'DH', name_long='!!End ts')
    tbl.column('end_reason', size=':12', name_long='!!End Reason')


# projects/gnrcore/packages/adm/model/shortcut.py
# SHA256: e48adcb5c48f9ba211f01559ec6f4eb8eb51b40d275b9de17e52df6b4a8b77e8
def shortcut(pkg):
    tbl = pkg.table('shortcut', pkey='keycode', name_long='!!Shortcut', name_plural='!!Shortcuts', caption_field='phrase', lookup=True)
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.options().counter()
    tbl.column('keycode', size=':10', name_long='!!Key')
    tbl.column('phrase', name_long='!!Phrase')
    tbl.column('groupcode', size=':20', name_long='!!Group')


# projects/gnrcore/packages/adm/model/tblinfo.py
# SHA256: 62441dab50c549d424819c6ff518f4b0e515113b7dfd7800b48000e8636e0384
def tblinfo(pkg):
    tbl = pkg.table('tblinfo', pkey='tblid', name_long='!!Table Info', name_plural='!!Table info')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('tblid', size=':50', name_long='!!Table')
    tbl.column('pkgid', size=':50', name_long='!!Package').relation('pkginfo.pkgid', foreign_key=False, relation_name='tables')
    tbl.column('description', size=':50', name_long='!!Description')


# projects/gnrcore/packages/adm/model/tblinfo_item.py
# SHA256: 97a7af17cabfb43a7bad4f47116cb590d418987e11a54c12f5e9dfe15849c70f
def tblinfo_item(pkg):
    tbl = pkg.table('tblinfo_item', pkey='info_key', pkey_columns='tblid,item_type,code', name_long='!!Tblinfo item', pkey_columns_joiner='/', name_plural='!!Tblinfo items', caption_field='description')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('info_key', size=':50', readOnly=True, name_long='!!Info key', indexed=True)
    tbl.column('code', size=':50', name_long='!!Code')
    tbl.column('description', size=':50', name_long='!!Description')
    tbl.column('item_type', size=':5', name_long='!!Type', validate_values='QTREE:Quick tree,FTREE:Full tree')
    tbl.column('data', dtype='X', name_long='!!Data')
    tbl.column('tblid', size=':50').relation('tblinfo.tblid', relation_name='items', onDelete='cascade', foreign_key=True)


# projects/gnrcore/packages/adm/model/user.py
# SHA256: a5aba23ecf28a376b6e4dd4bd293857f6d588aa91a80f157efe43f0cd2344b11
def user(pkg):
    tbl = pkg.table('user', pkey='id', name_long='!!User', rowcaption='username,email:%s (%s)', caption_field='username', tabletype='main')
    tbl.options().sysFields(ins=True, upd=True, user_upd=False, group_name='!![en]System')
    tbl.column('__rec_md5', group='zzz', name_long='!![en]Update date')
    tbl.column('id', size='22', group='_', readOnly=True, name_long='Id')
    tbl.column('username', size=':32', name_long='!!Username', unique=True, indexed=True, validate_notnull=True, validate_notnull_error='!!Mandatory field')
    tbl.column('email', name_long='Email', validate_notnull=True, validate_notnull_error='!!Mandatory field')
    tbl.column('mobile', name_long='Mobile')
    tbl.column('firstname', name_long='!!First name', validate_notnull=True, validate_case='c', validate_notnull_error='!!Mandatory field')
    tbl.column('lastname', name_long='!!Last name', validate_notnull=True, validate_case='c', validate_notnull_error='!!Mandatory field')
    tbl.column('registration_date', 'D', name_long='!!Registration Date')
    tbl.column('auth_tags', name_long='!!Authorization Tags')
    tbl.column('status', name_long='!!Status', size=':4', validate_values='invt:Invited,new:New,wait:Waiting,conf:Confirmed,bann:Banned')
    tbl.column('md5pwd', name_long='!!PasswordMD5', size=':65')
    tbl.column('locale', name_long='!![it]Default locale', size=':12')
    tbl.column('language', size=':2', name_long='!![it]Language').relation('adm.language.code', foreign_key=False)
    tbl.column('preferences', dtype='X', name_long='!!Preferences')
    tbl.column('menu_root_id', size='22')
    tbl.column('avatar_rootpage', name_long='!!Root Page')
    tbl.column('sms_login', dtype='B', name_long='!!Sms login')
    tbl.column('sms_number', name_long='!!Sms Number')
    tbl.column('photo', dtype='P', name_long='!![en]Photo')
    tbl.column('group_code', size=':15', name_long='!!Group').relation('group.code', relation_name='users', foreign_key=True)
    tbl.column('xgroup', size=':10', name_long='!!Deployment group').relation('adm.xgroup.code', relation_name='users', onDelete='setnull', foreign_key=True)
    tbl.column('custom_menu', dtype='X', name_long='!!Custom menu')
    tbl.column('custom_fields', dtype='X', name_long='!!Custom fields')
    tbl.column('avatar_secret_2fa', dtype='T', name_long='!![en]Secret 2fa')
    tbl.column('avatar_last_2fa_otp', name_long='Last 2fa')
    tbl.pyColumn('all_tags', name_long='All tags', dtype='A', method='pyColumn_all_tags')
    tbl.pyColumn('cover_logo', name_long='Cover logo', dtype='A', method='pyColumn_cover_logo')
    tbl.pyColumn('square_logo', name_long='Square logo', dtype='A', method='pyColumn_square_logo')
    tbl.formulaColumn('custom_groups', 'null', name_long='!!Custom groups', dtype='A')
    tbl.formulaColumn('other_groups', select=dict(columns="string_agg($group_code,',')", where='$user_id=#THIS.id AND $group_code!=#THIS.group_code', table='adm.user_group'), dtype='A')
    tbl.formulaColumn('all_groups', "\n                                            CASE WHEN $group_code IS NOT NULL THEN $group_code ELSE '' END ||\n                                            CASE WHEN $group_code IS NOT NULL AND $other_groups IS NOT NULL THEN ',' ELSE '' END ||\n                                            CASE WHEN $other_groups IS NOT NULL THEN $other_groups ELSE '' END ||\n                                            CASE WHEN ($group_code IS NOT NULL OR $other_groups IS NOT NULL) AND $custom_groups IS NOT NULL THEN ',' ELSE '' END ||\n                                            CASE WHEN $custom_groups IS NOT NULL THEN $custom_groups ELSE '' END\n                                        ", dtype='A')
    tbl.formulaColumn('fullname', "CASE WHEN $firstname IS NOT NULL AND $lastname IS NOT NULL THEN $firstname||' '||$lastname\n                                            WHEN $lastname IS NOT NULL THEN $lastname\n                                            ELSE $username END\n                                        ", name_long=u'!!Name', static=True, dtype='A')
    tbl.formulaColumn('recover_pwd_email', '$email', name_long=u'!!Recover email', static=True, dtype='A')
    tbl.formulaColumn('watermark_notice', "'Copy for ' || $username", dtype='A')


# projects/gnrcore/packages/adm/model/user_access_group.py
# SHA256: f321b5e6ba1ee55589dc612fd0ce37f15d792984308978239346dfd44ce88620
def user_access_group(pkg):
    tbl = pkg.table('user_access_group', pkey='id', name_long='!!User access', name_plural='!!User access')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('user_id', size='22', group='_', name_long='!!User').relation('user.id', relation_name='access_groups', onDelete='cascade', foreign_key=True)
    tbl.column('access_group_code', size=':10', group='_', name_long='!!Access group').relation('access_group.code', relation_name='access_users', onDelete='cascade', foreign_key=True)


# projects/gnrcore/packages/adm/model/user_config.py
# SHA256: da717140d0406b5cd89c470b0a38745ac940b1277d93a2c2a0fc45ce42fe885b
def user_config(pkg):
    tbl = pkg.table('user_config', pkey='ruleid', name_long='!!User config', name_plural='!!User config')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('ruleid', size=':80')
    tbl.column('user_group', size=':15', name_long='!!Group').relation('group.code', relation_name='custom_info', foreign_key=True)
    tbl.column('username', size=':32', group='_', name_long='!!User').relation('user.username', foreign_key=False, relation_name='custom_info', onDelete='cascade')
    tbl.column('pkgid', size=':50', name_long='!!Pkg').relation('pkginfo.pkgid', relation_name='rules', foreign_key=True)
    tbl.column('tblid', size=':50', name_long='!!Tbl').relation('tblinfo.tblid', relation_name='rules', foreign_key=True)
    tbl.column('data', dtype='X', name_long='!!Data')
    tbl.formulaColumn('calc_pkgid', "CASE WHEN $pkgid IS NOT NULL THEN $pkgid\n                                               WHEN $tblid IS NOT NULL THEN split_part($tblid,'.',1)\n                                               ELSE NULL END", dtype='A')
    tbl.formulaColumn('rank', 'CAST(($tblid IS NOT NULL) AS int)*8+\n                                    CAST(($pkgid IS NOT NULL) AS int)*2+\n                                    CAST(($username IS NOT NULL) AS int)*4+\n                                    CAST(($user_group IS NOT NULL) AS int)*1', dtype='L')


# projects/gnrcore/packages/adm/model/user_group.py
# SHA256: c8c825ed64cbc76705d00b754221e272ebd1a19a6dca1d7b62e26bb1c7fe3e23
def user_group(pkg):
    tbl = pkg.table('user_group', pkey='id', name_long='!![en]User groups', name_plural='!![en]User groups')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('user_id', size='22', group='_', name_long='User').relation('user.id', relation_name='extra_groups', onDelete='cascade', foreign_key=True)
    tbl.column('group_code', size=':15', group='_', name_long='Group').relation('group.code', relation_name='user_groups', onDelete='cascade', foreign_key=True)


# projects/gnrcore/packages/adm/model/user_notification.py
# SHA256: ab6f7f086c4312b5ef507c29cf8461d22a1c83647524a6863a1b5168155e9273
def user_notification(pkg):
    tbl = pkg.table('user_notification', pkey='id', name_long='User notification', name_plural='!!User notifications')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('user_id', size='22', group='_', name_long='!!User').relation('user.id', relation_name='user_notifications', onDelete='cascade', onDuplicate='ignore', foreign_key=True)
    tbl.column('notification_id', size='22', group='_', name_long='!!Notification').relation('notification.id', relation_name='notification_users', onDelete='cascade', onDuplicate='ignore', foreign_key=True)
    tbl.column('confirmed', dtype='B', name_long='!!Confirmed')
    tbl.column('notification', dtype='X', name_long='Custom Notification')


# projects/gnrcore/packages/adm/model/user_setting.py
# SHA256: 95bd97ee8e32d58175d8a9059d2b16548d87465248a159f239ddc2e755162aa9
def user_setting(pkg):
    tbl = pkg.table('user_setting', pkey='identifier', pkey_columns='user_id,setting_code', name_long='User setting', name_plural='User setting', caption_field='')
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('user_id', size='22', group='_', name_long='User', notnull=True).relation('adm.user.id', relation_name='settings', onDelete='cascade', foreign_key=True)
    tbl.column('setting_code', size=':20', name_long='Setting code', notnull=True)
    tbl.column('setting_data', dtype='X', name_long='Setting data')
    tbl.column('identifier', size=':42', name_long='Setting identifier')


# projects/gnrcore/packages/adm/model/user_tag.py
# SHA256: 48f17ae76da82d6f6be003583c5b82eecbc718991d0ebd2682a70019c35c57fd
def user_tag(pkg):
    tbl = pkg.table('user_tag', pkey='id', name_long='!!User tag', name_plural='!!User tags')
    tbl.options().sysFields(user_upd=False, group_name='!![en]System')
    tbl.column('group_code', size=':15', name_long='!!Group').relation('group.code', relation_name='tags', onDelete='cascade', foreign_key=True)
    tbl.column('user_id', size='22', group='_', name_long='!!User').relation('user.id', onDelete='cascade', relation_name='tags', foreign_key=True)
    tbl.column('tag_id', size='22', group='_', name_long='!!Tag').relation('htag.id', onDelete='cascade', relation_name='users', foreign_key=True)
    tbl.aliasColumn('user', relation_path='@user_id.username')
    tbl.aliasColumn('fullname', relation_path='@user_id.fullname')
    tbl.aliasColumn('email', relation_path='@user_id.email')
    tbl.aliasColumn('tag_description', relation_path='@tag_id.description')
    tbl.aliasColumn('tag_note', relation_path='@tag_id.note')
    tbl.aliasColumn('linked_table', relation_path='@tag_id.linked_table', static=True)
    tbl.aliasColumn('require_2fa', '@tag_id.require_2fa')
    tbl.aliasColumn('tag_code', '@tag_id.authorization_tag')
    tbl.formulaColumn('user_or_group', 'COALESCE($user,$group_code)', dtype='A')


# projects/gnrcore/packages/adm/model/userobject.py
# SHA256: 95f1eda3d637ab8c3266a1d5557d0db30a6e8ceef8beacdeee80547638ac031c
def userobject(pkg):
    tbl = pkg.table('userobject', pkey='id', name_long='!![en]User Object', name_plural='!![en]User Objects', rowcaption='$code,$objtype')
    tbl.options().broadcast('objtype')
    tbl.options().archive()
    tbl.options().sysFields(id=True, ins=True, upd=True, user_upd=False, group_name='!![en]System')
    tbl.column('identifier', size=':120', indexed=True, sql_value="COALESCE(:tbl,:pkg,'')||:objtype||:code|| CASE WHEN :private THEN :userid ELSE '' END", unique=True)
    tbl.column('code', size=':40', name_long='!![en]Code', indexed=True, validate_notnull=True)
    tbl.column('objtype', size=':20', name_long='!![en]Object Type', indexed=True)
    tbl.column('pkg', size=':50', name_long='!![en]Package', default_from='@tbl.pkgid').relation('pkginfo.pkgid', foreign_key=False, relation_name='objects')
    tbl.column('tbl', size=':50', name_long='!![en]Table').relation('tblinfo.tblid', foreign_key=False, relation_name='objects')
    tbl.column('userid', size=':50', name_long='!![en]User ID', indexed=True)
    tbl.column('description', size=':50', name_long='!![en]Description', indexed=True)
    tbl.column('notes', 'T', name_long='!![en]Notes')
    tbl.column('data', 'X', name_long='!![en]Data')
    tbl.column('authtags', 'T', name_long='!![en]Auth tags')
    tbl.column('private', 'B', name_long='!![en]Private')
    tbl.column('quicklist', 'B', name_long='!![en]Quicklist')
    tbl.column('flags', 'T', name_long='!![en]Flags')
    tbl.column('required_pkg', name_long='!![en]Required pkg')
    tbl.column('preview', name_long='!![en][it]Preview')
    tbl.formulaColumn('system_userobject', '$code LIKE :scode', var_scode='\\_\\_%%', dtype='B')
    tbl.pyColumn('resource_status', name_long='!![en]Resources', required_columns='$data', method='pyColumn_resource_status')
    tbl.formulaColumn('is_mail', ":email ILIKE ANY(string_to_array($flags,','))", var_email='is_mail', dtype='B', static=True)
    tbl.formulaColumn('is_row', ":row ILIKE ANY(string_to_array($flags,','))", var_row='is_row', dtype='B', static=True)
    tbl.formulaColumn('is_print', ":print ILIKE ANY(string_to_array($flags,','))", var_print='is_print', dtype='B', static=True)


# projects/gnrcore/packages/adm/model/week.py
# SHA256: 546e517062efdf3a9ad61c68e467b74ae2f9db7a72e39b010f5aae6d0d40829b
def week(pkg):
    tbl = pkg.table('week', pkey='start_date', name_long='!![en]Week', name_plural='!![en]Week', caption_field='week')
    tbl.column('start_date', dtype='D', name_long='!![en]Start Date')
    tbl.formulaColumn('week', "to_char($start_date, 'YYYY-IW')", dtype='T', name_long='Week', static=True)
    tbl.formulaColumn('end_date', "$start_date + interval '6 days' ", dtype='D', name_long='!![en]End Date')


# projects/gnrcore/packages/adm/model/xgroup.py
# SHA256: c5ba506d4c3486cff97fe321055d804e4eb2f650c69107e98fada791914df6f6
def xgroup(pkg):
    tbl = pkg.table('xgroup', pkey='code', name_long='!!Deployment group', name_plural='!!Deployment groups', caption_field='description', lookup=True)
    tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System', syscode=True)
    tbl.column('code', size=':10', name_long='!!Code')
    tbl.column('description', name_long='!!Description')


def configure(pkg):
    access_group(pkg)
    api_token(pkg)
    api_token_tag(pkg)
    audit(pkg)
    authorization(pkg)
    backup(pkg)
    ckstyle(pkg)
    connection(pkg)
    counter(pkg)
    day(pkg)
    group(pkg)
    group_helpdoc(pkg)
    helpdoc(pkg)
    htag(pkg)
    htmltemplate(pkg)
    htmltemplate_atc(pkg)
    install_checklist(pkg)
    language(pkg)
    letterhead_type(pkg)
    menu(pkg)
    menu_page(pkg)
    notification(pkg)
    pkginfo(pkg)
    preference(pkg)
    record_tag(pkg)
    sent_email(pkg)
    served_page(pkg)
    shortcut(pkg)
    tblinfo(pkg)
    tblinfo_item(pkg)
    user(pkg)
    user_access_group(pkg)
    user_config(pkg)
    user_group(pkg)
    user_notification(pkg)
    user_setting(pkg)
    user_tag(pkg)
    userobject(pkg)
    week(pkg)
    xgroup(pkg)
