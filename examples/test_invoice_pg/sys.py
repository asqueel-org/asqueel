"""Native declarations transcribed from original config_db methods.

No GenroPy imports or expanded legacy fixtures are needed.
"""


# projects/gnrcore/packages/sys/model/batch_log.py
# SHA256: b43c0a8faa957b3ccf64ae0e311b9c1c76d0e9f079bdc88b84ba928d7438ea16
def batch_log(pkg):
    tbl = pkg.table('batch_log', pkey='id', name_long='!!Batch log', name_plural='!!Batch logs', caption_field='log_caption')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('batch_title', name_long='!!Batch title')
    tbl.column('page_id', size='22', group='_', name_long='!!Page').weak_relation('adm.served_page.page_id', relation_name='batches', on_delete='raise')
    tbl.column('start_ts', dtype='DH', name_long='!!Start ts')
    tbl.column('end_ts', dtype='DH', name_long='!!End ts')
    tbl.column('notes', name_long='!!Notes')
    tbl.column('logbag', dtype='X', name_long='!!Log')
    tbl.column('tbl', name_long='!!Table')
    tbl.formulaColumn('log_caption', '$tbl || $batch_title', dtype='A')
    tbl.formulaColumn('logfile_url', "'/_site/batch_log/'||$id||'.log'", name_long='Log url', dtype='A')


# projects/gnrcore/packages/sys/model/calendar.py
# SHA256: 9930cb2e206bea9b1a60bedf708150d01878679e64037449ba7f3a621159f536
def calendar(pkg):
    tbl = pkg.table('calendar', pkey='date', name_long='!![en]Calendar', name_plural='!![en]Calendar Days', caption_field='date')
    tbl.column('date', dtype='D', name_long='!![en]Date', indexed=True, unique=True)
    tbl.formulaColumn('year_month', "to_char('YYYY-MM')", dtype='L', name_long='!![en]Month')
    tbl.pyColumn('holiday', name_long='!![en]Holiday', x_legacy__addClass='holiday', method='pyColumn_holiday')
    tbl.formulaColumn('dow', 'EXTRACT(ISODOW FROM $date)', dtype='L')
    tbl.formulaColumn('weekend', '$dow>5', dtype='B', x_legacy__addClass='weekend')
    tbl.pyColumn('day_cal', dtype='A', group='*', method='templateColumn', template_name='day_cal', template_localized=True)


# projects/gnrcore/packages/sys/model/dataretention.py
# SHA256: 6b9d8a9b05916c5f044ebf173490411ba71316e0cccb28c2b2a66bdbc5334c6d
def dataretention(pkg):
    tbl = pkg.table('dataretention', rowcaption='$table_fullname', caption_field='task_fullname', pkey='id', name_long='!!Data Retention Policy', name_plural='!!Data Retention Policies')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('table_fullname', name_long='!!Table', unique=True)
    tbl.column('filter_column', name_long='!!Filter Column')
    tbl.column('retention_period', dtype='L', name_long='!!Retention (days)')


# projects/gnrcore/packages/sys/model/dbchange.py
# SHA256: 50f5672d7a29b924bf12ccfc1543f1241cbf4db65d8d72e04f81483fc9735677
def dbchange(pkg):
    tbl = pkg.table('dbchange', pkey='ref', name_long='!!Dbchange', name_plural='!!Db change')
    tbl.options().sys_fields(id=False, ins=True, upd=False, ldel=False, user_upd=False, group_name='!![en]System')
    tbl.column('ref', dtype='serial', name_long='!!Reference')
    tbl.column('tbl', size=':80', name_long='!!Table')
    tbl.column('record_pkey', name_long='!!Record pkey')
    tbl.column('evt', size='1', name_long='Evt', name_short='!!Evt')
    tbl.column('record', dtype='X', name_long='!!Record')
    tbl.column('dbstore', size=':60', name_long='!!Dbstore')


# projects/gnrcore/packages/sys/model/error.py
# SHA256: 3628a4ddce290a0a437c244ddb8d38071e5f87fe4f437b64d6d4c672a6e5313a
def error(pkg):
    tbl = pkg.table('error', pkey='id', name_long='Debug Error', name_plural='!!Errors', caption_field='description', rowcaption='$error_type,$description')
    tbl.options().retention(field='__ins_ts', days=60)
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('description', name_long='!!Description')
    tbl.column('error_data', dtype='X', name_long='!!Traceback')
    tbl.column('username', name_long='User')
    tbl.column('user_ip', name_long='User ip')
    tbl.column('user_agent', name_long='User agent')
    tbl.column('fixed', name_long='Fixed')
    tbl.column('notes', name_long='Notes')
    tbl.column('error_type', name_long='!!Error type')
    tbl.column('error_code', name_long='!!Error code', indexed=True)
    tbl.formulaColumn('detail_url', "(CASE WHEN $request_host IS NULL\n                                THEN CASE WHEN $current_domain IS NOT NULL\n                                    THEN '/_main_/sys/ep_error?error_id=' || $id\n                                    ELSE '/sys/ep_error?error_id=' || $id END\n                                ELSE $request_host || CASE WHEN $current_domain IS NOT NULL\n                                    THEN '/_main_/sys/ep_error?error_id=' || $id\n                                    ELSE '/sys/ep_error?error_id=' || $id END\n                             END)\n                            ", name_long='!!Detail', dtype='A')
    tbl.column('request_uri', name_long='!!Request URI')
    tbl.column('request_host', name_long='!!Request Host')
    tbl.column('rpc_method', name_long='!!RPC Method')
    tbl.column('rpc_kwargs', dtype='X', name_long='!!RPC kwargs')
    tbl.column('page_id', name_long='!!Page ID', size='22')
    tbl.column('current_domain', name_long='!!Current domain')


# projects/gnrcore/packages/sys/model/external_token.py
# SHA256: b165f8942cca0ed7974ddeac1692eef024aeba54415611b93e7cdee251d4ce9d
def external_token(pkg):
    tbl = pkg.table('external_token', pkey='id', name_long='!!External Token', name_plural='!!External Tokens')
    tbl.column('id', size='22', name_long='!!id')
    tbl.column('datetime', 'DHZ', name_long='!!Date and Time')
    tbl.column('expiry', 'DHZ', name_long='!!Expiry')
    tbl.column('allowed_user', size=':32', name_long='!!Destination user')
    tbl.column('connection_id', size='22', name_long='!!Connection Id', indexed=True).weak_relation('adm.connection.id')
    tbl.column('max_usages', 'I', name_long='!!Max uses')
    tbl.column('allowed_host', name_long='!!Allowed host')
    tbl.column('page_path', name_long='!!Page path')
    tbl.column('method', name_long='!!Method')
    tbl.column('assigned_user_id', size='22', group='_', name_long='Assigned user id').weak_relation('adm.user.id', relation_name='assigned_tokens', on_delete='cascade')
    tbl.column('parameters', dtype='X', name_long='!!Parameters')
    tbl.column('exec_user', size=':32', name_long='!!Execute as user').weak_relation('adm.user.username')
    tbl.column('userobject_id', size='22', group='_', name_long='Userobject').relation('adm.userobject.id', relation_name='tokens', on_delete='cascade', foreign_key=True)
    tbl.pyColumn('external_url', method='pyColumn_external_url')


# projects/gnrcore/packages/sys/model/external_token_use.py
# SHA256: ee364435e2f03033709beb2266076a538aac6c0b16d3363bebad595c5cfca92f
def external_token_use(pkg):
    tbl = pkg.table('external_token_use', pkey='id', name_long='!!External token usage', name_plural='!!External token usages')
    tbl.column('id', size='22', name_long='!!id')
    tbl.column('external_token_id', size='22', name_long='!!External token id').relation('external_token.id', relation_name='usages', on_delete='cascade', foreign_key=True)
    tbl.column('datetime', 'DH', name_long='!!Date and Time')
    tbl.column('host', name_long='!!Host')


# projects/gnrcore/packages/sys/model/externalcall_log.py
# SHA256: 9155945c68e4a2ecdc77a451aeab360a8b799928f3fb86cb52bf3656de98e6e2
def externalcall_log(pkg):
    tbl = pkg.table('externalcall_log', pkey='id', name_long='External call log', name_plural='External call log', caption_field='methodname')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('endpoint', name_long='Endpoint')
    tbl.column('methodname', name_long='Method')
    tbl.column('parameters', dtype='X', name_long='Parameters')
    tbl.column('error', name_long='Error')
    tbl.column('result', dtype='X', name_long='Result')


# projects/gnrcore/packages/sys/model/service.py
# SHA256: da87c01ca4c9e83d93d3e326e47849208b09f10c2d52a481ae90150673e9a853
def service(pkg):
    tbl = pkg.table('service', name_long='!!Service', name_plural='!!Services', caption_field='service_identifier', pkey='service_identifier', pkey_columns='service_type,service_name')
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('service_identifier', size=':60', name_long='!!Identifier')
    tbl.column('service_type', size=':30', name_long='!!Service type')
    tbl.column('service_name', size=':30', name_long='!!Service name')
    tbl.column('implementation', name_long='!!Implementation')
    tbl.column('parameters', dtype='X', name_long='!!Parameters')
    tbl.column('daemon', dtype='B', name_long='!!Daemon')
    tbl.column('disabled', dtype='B', name_long='!!Disabled')


# projects/gnrcore/packages/sys/model/shared_object.py
# SHA256: c496cdb230492554ac815160eb5a07a007c045e5cced3322131a111c4025d156
def shared_object(pkg):
    tbl = pkg.table('shared_object', pkey='id', name_long='!!Shared Object', name_plural='Shared objects')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('data', 'X', name_long='!!Data')
    tbl.column('backup', 'X', name_long='!!Backup')
    tbl.column('description', size=':50', name_long='Code', indexed=True)
    tbl.column('linked_table', name_long='!!Table')


# projects/gnrcore/packages/sys/model/shorturl.py
# SHA256: 1f2a2e134e3f1d353753afb1c019c16ae0bf63ef93941f0d8b6a4d0e2d2b83f9
def shorturl(pkg):
    tbl = pkg.table('shorturl', pkey='codekey', pkey_columns='$domain,$key', name_long='Shorturl', name_plural='Shorturl', caption_field='shorturl')
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('codekey', size=':100', name_long='Codekey')
    tbl.column('service_identifier', size=':60', group='_', name_long='Service').relation('service.service_identifier', relation_name='urls', on_delete='raise', foreign_key=True)
    tbl.column('longurl', name_long='Long url')
    tbl.column('shorturl', name_long='Short url', name_short='Short')
    tbl.column('domain', name_long='Domain')
    tbl.column('key', name_long='Key')
    tbl.column('expiration', 'D', name_long='Expiration')
    tbl.column('traking', dtype='X', name_long='Traking')


# projects/gnrcore/packages/sys/model/task.py
# SHA256: 2ed0868a185ab0a77f5d37773326638dcd4a471e190b32c44c709cf9216ab137
def task(pkg):
    tbl = pkg.table('task', rowcaption='$task_name', caption_field='task_name', pkey='id', name_long='!!Task', name_plural='!!Tasks')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('table_name', name_long='!!Table')
    tbl.column('task_name', name_long='!!Task name', name_short='!!Name')
    tbl.column('command', name_long='!!Command')
    tbl.column('month', name_long='!!Month', validate_values='1:[!!Jan],2:[!!Feb],3:[!!Mar],4:[!!Apr],5:[!!May],6:[!!Jun],7:[!!Jul],8:[!!Aug],9:[!!Sep],10:[!!Oct],11:[!!Nov],12:[!!Dec]')
    tbl.column('day', name_long='!!Day', validate_values=','.join([str(x + 1) for x in range(31)]))
    tbl.column('weekday', name_long='!!Weekday', validate_values='0:[!!Sun],1:[!!Mon],2:[!!Tue],3:[!!Wed],4:[!!Thu],5:[!!Fri],6:[!!Sat]')
    tbl.column('hour', name_long='!!Hour', validate_values=','.join([str(x) for x in range(24)]))
    tbl.column('minute', name_long='!!Minute', validate_values=','.join([str(x) for x in range(60)]))
    tbl.column('frequency', dtype='L', name_long='!!Freq.(min)')
    tbl.column('parameters', dtype='X', name_long='!!Parameters')
    tbl.column('last_scheduled_ts', 'DHZ', name_long='!!Last scheduled', indexed=True)
    tbl.column('last_execution_ts', 'DHZ', name_long='!!Last Execution')
    tbl.column('last_error_ts', 'DHZ', name_long='!!Last Error')
    tbl.column('last_error_info', 'X', name_long='!!Last Error Info')
    tbl.column('run_asap', 'B', name_long='!!Run ASAP')
    tbl.column('max_workers', 'L', name_long='!!Max workers')
    tbl.column('log_result', 'B', name_long='!!Log Task')
    tbl.column('user_id', size='22', group='_', name_long='User id')
    tbl.column('date_start', 'D', name_long='!!Start Date')
    tbl.column('date_end', 'D', name_long='!!End Date')
    tbl.column('stopped', 'B', name_long='!!Stopped')
    tbl.column('worker_code', size=':10', name_long='Worker code', indexed=True)
    tbl.column('saved_query_code', size=':40', name_long='!![en]Query')
    tbl.formulaColumn('active_workers', select=dict(table='sys.task_execution', where='$task_id=#THIS.id AND $start_ts IS NOT NULL AND $end_ts IS NULL', columns='COUNT(*)'), dtype='N', name_long='N.Active workers')
    tbl.formulaColumn('last_result_ts', select=dict(table='sys.task_result', columns='MAX($start_time)', where='$task_id = #THIS.id'), name_long='!!Last Execution', dtype='A')
    tbl.formulaColumn('last_completed', dtype='DH', name_long='!![en]Last completed', select=dict(table='sys.task_execution', where='$task_id=#THIS.id AND $end_ts IS NOT NULL', order_by='$end_ts DESC', limit=1, columns='$end_ts'))
    tbl.formulaColumn('last_error', dtype='DH', name_long='!![en]Last error', select=dict(table='sys.task_execution', where='$task_id=#THIS.id AND $is_error IS TRUE', order_by='$start_ts DESC', limit=1, columns='$start_ts'))


# projects/gnrcore/packages/sys/model/task_execution.py
# SHA256: 9f3279b30413ddb7004f887bfe32618d78ec25a2774657e4bf7241000031cda5
def task_execution(pkg):
    tbl = pkg.table('task_execution', pkey='id', name_long='!!Task execution', name_plural='!!Task executions')
    tbl.options().retention(field='__ins_ts', days=180)
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('task_id', size='22', name_long='!!Task ID').relation('sys.task.id', relation_name='executions', on_delete='cascade', foreign_key=True)
    tbl.column('result', 'X', name_long='!!result')
    tbl.column('logbag', 'X', name_long='!!Logbag')
    tbl.column('errorbag', 'X', name_long='!!Errors')
    tbl.column('pid', dtype='L', name_long='!!Process id', name_short='!!PID')
    tbl.column('start_ts', dtype='DH', name_long='!!Start Time', indexed=True)
    tbl.column('end_ts', dtype='DH', name_long='!!End Time', indexed=True)
    tbl.column('is_error', 'B', name_long='!!Is Error', indexed=True)
    tbl.column('exec_reason', size=':20', name_long='!!Exec reason')
    tbl.column('reasonkey', size=':60', indexed=True)
    tbl.aliasColumn('task_table', '@task_id.table_name', name_long='!!Table')
    tbl.aliasColumn('task_name', '@task_id.task_name', name_long='!!Task name', name_short='!!Name')
    tbl.aliasColumn('task_command', '@task_id.command', name_long='!!Task command', name_short='!!Command')
    tbl.aliasColumn('task_stopped', '@task_id.stopped', dtype='B', name_long='!!Stopped')
    tbl.aliasColumn('task_parameters', '@task_id.parameters', dtype='X', name_long='!!Parameters')
    tbl.aliasColumn('task_saved_query', '@task_id.saved_query_code', dtype='B', name_long='!!Saved query')
    tbl.aliasColumn('task_worker_code', '@task_id.worker_code', dtype='L', name_long='!!Task worker code')
    tbl.aliasColumn('task_max_workers', '@task_id.max_workers', dtype='L', name_long='!!Task Max workers')
    tbl.aliasColumn('task_active_workers', '@task_id.active_workers', dtype='L', name_long='!!Task Active workers')
    tbl.formulaColumn('status', "\n            (CASE WHEN $is_error IS TRUE THEN 'error'\n                 WHEN $end_ts IS NOT NULL THEN 'completed'\n                 WHEN $start_ts IS NOT NULL THEN 'running'\n                 ELSE 'waiting'\n            END)\n        ", name_long='Status', dtype='A')


# projects/gnrcore/packages/sys/model/task_result.py
# SHA256: fbc99a46858ca9f82cba2dfef8044b33f0fbc2893f220f656fc6fac51439ab60
def task_result(pkg):
    tbl = pkg.table('task_result', pkey='id', name_long='!!Task log')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('task_id', size='22', name_long='!!Task ID').relation('sys.task.id', relation_name='logs', foreign_key=True)
    tbl.column('result', 'X', name_long='!!result')
    tbl.column('result_time', dtype='DH', name_long='!!Result Time')
    tbl.column('start_time', dtype='DH', name_long='!!Start Time')
    tbl.column('end_time', dtype='DH', name_long='!!Start Time')
    tbl.column('is_error', 'B', name_long='!!Is Error')


# projects/gnrcore/packages/sys/model/upgrade.py
# SHA256: b256d035a05d580eeeb2575c52eb81ab0d15bfc13edde54f23ff663c3e2f9440
def upgrade(pkg):
    tbl = pkg.table('upgrade', pkey='codekey', pkey_columns='pkg,filename', pkey_columns_joiner='|', name_long='!!Upgrade ', name_plural='!!Upgrades', caption_field='codekey')
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('codekey', size=':306', name_long='Identifier')
    tbl.column('pkg', size=':50', name_long='Package')
    tbl.column('filename', size=':255', name_long='!!Filename')
    tbl.column('error', name_long='!!Upgrade error', name_short='!!Error')


# projects/gnrcore/packages/sys/model/widget.py
# SHA256: f0fa9b6419021899fadc943dbf25d65d974b4290df8f55d453f0d7d79b2e883c
def widget(pkg):
    tbl = pkg.table('widget', pkey='id', name_long='!!Widget', name_plural='!!Widgets', caption_field='name')
    tbl.options().audit('lazy')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.options().hierarchical('name')
    tbl.options().dynamic_fields()
    tbl.column('name', name_long='!!Name')
    tbl.column('summary', name_long='!!Summary')
    tbl.column('server', dtype='B', name_long='!!Server')


def configure(pkg):
    batch_log(pkg)
    calendar(pkg)
    dataretention(pkg)
    dbchange(pkg)
    error(pkg)
    external_token(pkg)
    external_token_use(pkg)
    externalcall_log(pkg)
    service(pkg)
    shared_object(pkg)
    shorturl(pkg)
    task(pkg)
    task_execution(pkg)
    task_result(pkg)
    upgrade(pkg)
    widget(pkg)
