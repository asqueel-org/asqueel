"""Recognize named bindings outside SQL literals, identifiers and comments.

This is only the binding boundary, not a SQL parser. PostgreSQL ordinary
strings follow standard_conforming_strings=on; backslash escapes use E'…'.
MySQL runs with ANSI_QUOTES and NO_BACKSLASH_ESCAPES, so its strings follow
the same rule; it adds backtick identifiers and ``#`` comments.
"""
import re


_COMMON = (
    r"'(?:''|[^'])*(?:'|$)|\"(?:\"\"|[^\"])*(?:\"|$)"
    r"|--[^\r\n]*|(?P<block>/\*)|\\:"
)
_PARAMETER = r'|(?<!:):(?P<parameter>\w+)'
_POSTGRES = re.compile(
    r"(?<![\w$])[eE]'(?:\\[\s\S]|''|[^'\\])*(?:'|$)"
    r'|(?P<dollar>(?<![\w$])\$(?:[^\W\d]\w*)?\$)|' + _COMMON + _PARAMETER)
_SQLITE = re.compile(
    r'`(?:``|[^`])*(?:`|$)|\[[^\]]*(?:\]|$)|' + _COMMON + _PARAMETER)
_MYSQL = re.compile(
    r'`(?:``|[^`])*(?:`|$)|#[^\r\n]*|' + _COMMON + _PARAMETER)
_COMMENT_EDGE = re.compile(r'/\*|\*/')


def parameter_matches(sql, dialect='postgresql'):
    """Yield only real :name matches, preserving offsets in the original SQL."""
    pattern = {'sqlite': _SQLITE, 'mysql': _MYSQL}.get(dialect, _POSTGRES)
    postgres = pattern is _POSTGRES
    position = 0
    while match := pattern.search(sql, position):
        position = match.end()
        if match.lastgroup == 'parameter':
            yield match
        elif match.lastgroup == 'dollar':
            end = sql.find(match[0], position)
            position = len(sql) if end < 0 else end + len(match[0])
        elif match.lastgroup == 'block':
            # PostgreSQL nests block comments; SQLite and MySQL close at the first */.
            depth = 1
            while depth:
                edge = _COMMENT_EDGE.search(sql, position)
                if edge is None:
                    position = len(sql)
                    break
                position = edge.end()
                if edge[0] == '*/':
                    depth -= 1
                elif postgres:
                    depth += 1


def substitute_parameters(sql, replace, dialect='postgresql'):
    """Replace real bindings with a callback; leave all other text untouched."""
    parts = []
    position = 0
    for match in parameter_matches(sql, dialect):
        parts.extend((sql[position:match.start()], replace(match)))
        position = match.end()
    parts.append(sql[position:])
    return ''.join(parts)
