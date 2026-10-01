"""Bind direct SQL without rewriting literals, comments or quoted identifiers."""
from ..contracts import EnvironmentBinding
from ..dialects.postgres import PostgresDialect, _tokens
from ..dialects.sqlite import SqliteDialect
from ..query_plan import _PARAM, Parameter, SqlStatement, expand_collection, member_name, parameter_use


def _runs(sql, *, sqlite=False):
    buffer = []
    for kind, text in _tokens(sql, sqlite=sqlite):
        if kind == 'code':
            buffer.append(text)
        else:
            if buffer:
                yield 'code', ''.join(buffer)
                buffer.clear()
            yield kind, text
    if buffer:
        yield 'code', ''.join(buffer)


def prepare_text(driver, sql, sqlargs, snapshot):
    sqlite = driver.dialect == 'sqlite'
    dialect = SqliteDialect() if sqlite else PostgresDialect()
    parts = []
    params = dict(sqlargs or {})
    names = set(params)
    uses = {}
    keys = set()
    for kind, text in _runs(sql, sqlite=sqlite):
        if kind != 'code':
            parts.append(text)
            continue
        start = 0
        for match in _PARAM.finditer(text):
            parts.append(text[start:match.start()])
            name = match['name']
            if name not in params and name.startswith('env_'):
                key = name[4:]
                if key in snapshot:
                    keys.add(key)
                    params[name] = snapshot[key]
                    names.add(name)
            if name not in params:
                raise ValueError(f'Missing query parameter: {name}')
            if match['keyword'] is None:
                parameter_use(uses, name, False)
                parts.append(Parameter(name))
            else:
                parameter_use(uses, name, True)

                def allocate(member, name=name):
                    bound_name = member_name(name, names)
                    params[bound_name] = member
                    return bound_name

                parts.extend(expand_collection(name, params[name],
                                               match['keyword'][:3].upper() == 'NOT',
                                               allocate, dialect.empty_collection))
            start = match.end()
        parts.append(text[start:])
    for name, collection in uses.items():
        if collection:
            del params[name]
    binding = EnvironmentBinding(tuple(sorted(keys)), {key: snapshot[key] for key in keys}) if keys else None
    return driver.prepare(SqlStatement(tuple(parts), params, dialect=driver.dialect, environment=binding))
