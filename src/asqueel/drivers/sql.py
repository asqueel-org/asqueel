"""Offline preparation ported from GenroPy execute/prepareSqlText.

Reference fa35e5ad: gnrsql/execute.py, _gnrbaseadapter, gnrpostgres,
gnrpostgres3 (collection expansion for psycopg 3), and gnrsqlite. This is
whole-text legacy preparation; it is not the structured statement formatter.
"""
from datetime import date
import re

from ..contracts import CompiledQuery, EnvironmentBinding


SQL_PARAMS = re.compile(r'(?<!:):(?!:)(\S\w*)(\W|$)')
ENV_PARAMS = re.compile(r':env_(\S\w*)(\W|$)')
_SQLITE_ILIKE = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]"
    r"|--[^\r\n]*|/\*[\s\S]*?\*/|(?<![\w:$@])(?P<operator>ILIKE)(?![\w$])",
    re.I,
)


def sqlite_ilike(sql):
    """Adapt only the ILIKE token, keeping quoted SQL and bindings intact."""
    return _SQLITE_ILIKE.sub(
        lambda match: match['operator'][1:] if match['operator'] else match[0], sql)


def prepare_arguments(sql, sqlargs, snapshot):
    """The value preparation from execute, without connection/store lifecycle."""
    keys = {key for key, _ in ENV_PARAMS.findall(sql)}
    params = {'env_' + key: snapshot.get(key) for key in keys}
    if 'env_workdate' in params:
        params['env_workdate'] = params['env_workdate'] or date.today()
    if snapshot.get('storename'):
        params['env_storename'] = snapshot['storename']
    keys = {key for key in keys if 'env_' + key not in (sqlargs or {})}
    params.update(sqlargs or {})
    for key, value in list(params.items()):
        if isinstance(value, bytes):
            value = value.decode('utf-8')
            params[key] = value
        if isinstance(value, str) and value.startswith((r'\$', r'\@')):
            params[key] = value[1:]
    return params, keys


def sqlite_collections(sql, params):
    """SqlDbBaseAdapter.adaptTupleListSet, including its generated names."""
    for key, values in [(k, v) for k, v in list(params.items())
                        if isinstance(v, (list, tuple, set))]:
        placeholders = '(%s) ' % ','.join(':%s%i' % (key, i) for i, _ in enumerate(values))
        params.pop(key)
        params.update(('%s%i' % (key, i), value) for i, value in enumerate(values))
        sql = re.sub(r':%s(\W|$)' % key, placeholders + r'\1', sql)
    return sql


def postgres_collections(sql, params):
    """gnrpostgres3.adaptTupleListSet: unroll IN values for psycopg 3.

    The old psycopg2 adapter kept a single tuple binding, which psycopg 3
    cannot use after IN. Reuse the existing legacy psycopg3 algorithm instead.
    """
    for key, values in list(params.items()):
        if not isinstance(values, (list, set, tuple)):
            continue
        if not isinstance(values, list):
            values = list(values)
        if not values:
            pattern = r'''((\"?t\d+)(_t\d+)*\"?.\"?\w+\"?" +)(NOT +)*(IN) *:%s''' % key
            sql = re.sub(pattern, lambda m: 'TRUE' if m.group(4) else 'FALSE', sql, flags=re.I)
        else:
            def unroll(match):
                params.pop(key, None)
                base = match.group(2)
                names = []
                for i, value in enumerate(values):
                    name = '%s_%s' % (base, i)
                    names.append(':' + name)
                    params[name] = value
                return '%s(%s)' % (match.group(1), ','.join(names))
            sql = re.sub(r'( *IN) *(?::)(%s)\b' % key, unroll, sql, flags=re.I)
    return sql


def sqlite_boolean(match):
    """gnrsqlite._booleanSubCb."""
    prefix, expr, is_not, truth = match.groups()
    value = '1' if truth.upper() == 'TRUE' else '0'
    if is_not:
        return '%s(%s IS NULL OR %s !=%s)' % (prefix, expr, expr, value)
    return '%s(%s IS NOT NULL AND %s =%s)' % (prefix, expr, expr, value)


def prepare_text(driver, sql, sqlargs, snapshot):
    params, keys = prepare_arguments(sql, sqlargs, snapshot)
    # execute shields escaped colons before adapter.prepareSqlText, then restores.
    sql = sql.replace(r'\:', chr(1))
    used = {name for name, _ in SQL_PARAMS.findall(sql)}
    # GenroPy 5ddb6813dc defaults missing bindings to None. Materialize them
    # before CompiledQuery freezes the mapping and drivers copy it to a dict.
    for name in sorted(used):
        params.setdefault(name, None)
    if driver.dialect == 'sqlite':
        sql = sqlite_collections(sql, params)
        sql = sqlite_ilike(sql).replace('~*', ' REGEXP ')
        sql = re.sub(r'(\(*)(["\w]["\w.]*) +IS +(NOT +)?(TRUE|FALSE)',
                     sqlite_boolean, sql, flags=re.I)
    else:
        sql = postgres_collections(sql, params)
        sql = SQL_PARAMS.sub(r'%(\1)s\2', sql).replace('REGEXP', '~*')
    sql = sql.replace(chr(1), ':')
    binding = (EnvironmentBinding(tuple(sorted(keys)),
                                  {key: snapshot[key] for key in keys if key in snapshot})
               if keys else None)
    return CompiledQuery(sql, params, dialect=driver.dialect, binding=driver.binding,
                         environment=binding, input_parameters=tuple(sorted(used)))
