"""Bind direct SQL without rewriting literals, comments or quoted identifiers."""
import re

from ..contracts import EnvironmentBinding
from ..dialects.postgres import _tokens
from ..query_plan import Parameter, SqlStatement


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
    parts = []
    params = dict(sqlargs or {})
    keys = set()
    for kind, text in _runs(sql, sqlite=driver.dialect == 'sqlite'):
        if kind != 'code':
            parts.append(text)
            continue
        start = 0
        for match in re.finditer(r':([A-Za-z_][A-Za-z0-9_]*)', text):
            parts.append(text[start:match.start()])
            name = match[1]
            if name not in params and name.startswith('env_'):
                key = name[4:]
                if key in snapshot:
                    keys.add(key)
                    params[name] = snapshot[key]
            if name not in params:
                raise ValueError(f'Missing query parameter: {name}')
            parts.append(Parameter(name))
            start = match.end()
        parts.append(text[start:])
    binding = EnvironmentBinding(tuple(sorted(keys)), {key: snapshot[key] for key in keys}) if keys else None
    return driver.prepare(SqlStatement(tuple(parts), params, dialect=driver.dialect, environment=binding))
