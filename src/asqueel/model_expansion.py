"""Deterministic native option expansion; no DB access or generated values."""
from __future__ import annotations

from .catalog import SqlModelCatalog
from .model_source import options


def expand_options(builder):
    catalog = SqlModelCatalog(builder)
    with builder.contribution('@options'):
        for (package, name), entry in catalog.tables.items():
            table = entry['node']
            configured = options(table)
            fields = configured.get('sys_fields')
            if fields is None or not fields.enabled:
                continue
            spec = fields.attributes
            definitions = {
                'id': ('id', 'A', {'size': '22', 'x_generation': {'type': 'uuid', 'algorithm': 'legacy22'}}),
                'ins': ('__ins_ts', spec['timestamp_type'], {'indexed': True}),
                'upd': ('__mod_ts', spec['timestamp_type'], {'indexed': True}),
                'user_ins': ('__ins_user', 'T', {}), 'user_upd': ('__mod_user', 'T', {}),
                'ldel': ('__del_ts', spec['timestamp_type'], {'indexed': True}),
                'draft': ('__is_draft', 'B', {'indexed': True}),
            }
            for setting, (column_name, dtype, defaults) in definitions.items():
                enabled = spec[setting]
                if enabled is False:
                    continue
                custom = dict(enabled) if not isinstance(enabled, bool) else {}
                custom.pop('type', None)
                existing = entry['columns'].get(column_name)
                structural = {'dtype': dtype, **({'size': '22'} if setting == 'id' else {})}
                if existing is not None:
                    for key, value in structural.items():
                        if existing.get_attr(key) is not None and existing.get_attr(key) != value:
                            raise ValueError(f'{package}.{name}.{column_name}: conflicts with sys_fields {key}')
                data = {'group': spec['group'], **defaults, **custom}
                if existing is not None:
                    data.update({key: value for key, value in existing.attr.items() if key not in ('_meta', 'name')})
                data.update(structural)
                table.column(column_name, **data)
            if spec['id'] is not False and 'pkey' not in table.attr:
                table.attr['pkey'] = 'id'
            pkey = table.get_attr('pkey')
            if pkey and '__record_pointer' not in entry['family']:
                table.formulaColumn('__record_pointer',
                    sql_formula=f"'{package}.{name}.' || CAST(${pkey} AS text)", dtype='T')
