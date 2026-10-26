"""Recognize named bindings outside SQL literals, identifiers and comments.

This is only the binding boundary, not a SQL parser. PostgreSQL ordinary
strings follow standard_conforming_strings=on; backslash escapes use E'…'.
SQL Server quotes identifiers in [...] too and nests block comments.
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
_MSSQL = re.compile(
    r'\[(?:\]\]|[^\]])*(?:\]|$)|' + _COMMON + _PARAMETER)
_COMMENT_EDGE = re.compile(r'/\*|\*/')


def parameter_matches(sql, dialect='postgresql'):
    """Yield only real :name matches, preserving offsets in the original SQL."""
    nested = dialect != 'sqlite'
    pattern = {'sqlite': _SQLITE, 'mssql': _MSSQL}.get(dialect, _POSTGRES)
    position = 0
    while match := pattern.search(sql, position):
        position = match.end()
        if match.lastgroup == 'parameter':
            yield match
        elif match.lastgroup == 'dollar':
            end = sql.find(match[0], position)
            position = len(sql) if end < 0 else end + len(match[0])
        elif match.lastgroup == 'block':
            # PostgreSQL and SQL Server nest block comments; SQLite closes at the first */.
            depth = 1
            while depth:
                edge = _COMMENT_EDGE.search(sql, position)
                if edge is None:
                    position = len(sql)
                    break
                position = edge.end()
                if edge[0] == '*/':
                    depth -= 1
                elif nested:
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


def substitute_parameters_and_text(sql, replace, replace_text, dialect='postgresql'):
    """As substitute_parameters, also passing every non-binding span through replace_text."""
    parts = []
    position = 0
    for match in parameter_matches(sql, dialect):
        parts.extend((replace_text(sql[position:match.start()]), replace(match)))
        position = match.end()
    parts.append(replace_text(sql[position:]))
    return ''.join(parts)
