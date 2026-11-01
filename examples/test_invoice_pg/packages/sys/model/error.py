# projects/gnrcore/packages/sys/model/error.py
# SHA256: 3628a4ddce290a0a437c244ddb8d38071e5f87fe4f437b64d6d4c672a6e5313a


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('error', pkey='id', name_long='Debug Error', name_plural='!!Errors', caption_field='description', rowcaption='$error_type,$description')
        tbl.options().retention(field='__ins_ts', days=60)
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
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
