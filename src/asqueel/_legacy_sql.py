"""SQL text algorithms ported from GenroPy, without a new expression grammar.

Reference: fa35e5ad, gnrsqldata/compiler.py (updateFieldDict, colPars loop)
and gnrstring.py (split, conditionalTemplate, templateReplace). The template
mapping here contains resolved SQL strings, not Bags or localized UI values.
Database quoting and parameter preparation do not belong to this module.
"""
import re
from string import Template


COLFINDER = re.compile(r'(\W|^)\$(\w+)')
RELFINDER = re.compile(r'([^A-Za-z0-9_]|^)(\@(\w[\w.@:]+))')
_CONDITIONAL = re.compile(r'\${([^}]*)}', flags=re.S)


def col_to_as(column):
    """GenroPy colToAs: the same spelling for a flattened reference/alias."""
    name = re.sub(r'\W', '_', column)
    return '_' + name if name[0].isdigit() else name


def projection_columns(columns, quote_alias):
    """Legacy ordered col_dict, recognizing outer AS with the existing splitter."""
    result = {}
    for column in dict.fromkeys(col for col in split_sql(columns) if col):
        column = column.strip()
        parts = split_sql(column, ' AS ')
        if len(parts) == 1:
            name = (column[1:] if column.startswith('$')
                    and column[1:].replace('_', '').isalnum() else col_to_as(column))
            alias = quote_alias(name)
            column = '%s AS %s' % (column, alias)
        else:
            alias = quote_alias(' AS '.join(parts[1:]).strip())
        result[alias] = column
    return tuple(result.values())


def embed_field_parameters(sql, params, table):
    """Legacy embedFieldPars, including its bytes conversion and word boundary.

    Return consumed names as bookkeeping for the existing query keyword check.
    Values stay in params, as in GenroPy; only WHERE text is replaced.
    """
    consumed = set()
    for name, value in list(params.items()):
        if isinstance(value, bytes):
            value = value.decode()
        if not isinstance(value, str):
            continue
        replace = False
        if value.startswith('@'):
            replace = value.split('.')[0] in table.relations
        elif value.startswith('$'):
            replace = value[1:] in table.columns or value[1:] in table.virtual_columns
        if replace:
            sql, count = re.subn(r'(:%s)(\W|$)' % name,
                                lambda match: '%s%s' % (value, match.group(2)), sql)
            if count:
                consumed.add(name)
    return sql, consumed


class FieldReferences:
    """One SELECT's relationDict and colPars, never stored on the model."""

    def __init__(self):
        self.paths = {}
        self.resolved = {}

    def discover(self, sql):
        """Legacy updateFieldDict; includes references inside SQL text/quotes."""
        for match in COLFINDER.finditer(sql):
            name = match.group(2)
            if name not in self.paths:
                self.paths[name] = name
        for match in RELFINDER.finditer(sql):
            name = match.group(2)
            alias = col_to_as(name)
            self.paths[alias] = name
            sql = sql.replace(name, '$%s' % alias, 1)
        return sql

    def resolve(self, get_field_alias):
        """Legacy colPars loop, including references added during resolution."""
        for key, path in list(self.paths.items()):
            if key not in self.resolved:
                self.resolved[key] = get_field_alias(path)
        missing = list(set(self.paths).difference(self.resolved))
        while missing:
            for key in missing:
                self.resolved[key] = get_field_alias(self.paths[key])
            missing = list(set(self.paths).difference(self.resolved))

    def substitute(self, sql, *, safe=False):
        return template_replace(sql, self.resolved, safe=safe)


def template_replace(sql, symbols, *, safe=False):
    """Legacy templateReplace for its plain dict of resolved SQL strings.

    Retain its empty-map shortcut, conditional ${...} blocks, $$ convention
    and safe-substitution for columns versus strict substitution for clauses.
    """
    sql = sql or ''
    if '$' not in sql or not symbols:
        return sql
    if '${' in sql:
        def conditional(match):
            content = match.group(1)
            symbol = re.search(r'\$([_a-zA-Z\@][_a-zA-Z0-9\.\@]*)', content)
            if (symbol and symbol.group(1) in symbols
                    and symbols[symbol.group(1)] not in (None, '')):
                return content
            return ''
        sql = _CONDITIONAL.sub(conditional, sql)
    template = Template(sql)
    return template.safe_substitute(symbols) if safe else template.substitute(symbols)


def split_sql(path, separator=','):
    """GenroPy gnrstring.split: separators outside quotes, parentheses/brackets.

    Deliberately retain the legacy traversal and errors. This is not the
    current dialect tokenizer and adds no dollar-quote or E-string grammar.
    """
    if not path:
        return ['']
    extended_separator = separator[1:]
    separator = separator[0]
    pattern = re.compile(
        r"([^\%s\'\"\(\[\)\]]*)(?:(?P<enditem>\%s|$)|(\')|(\")|(\()|(\[)|(\))|(\]))"
        % (separator, separator))
    result = []
    start = next_position = 0
    closing = []
    while start < len(path):
        start_position = start
        found_separator = False
        while not found_separator or closing:
            match = pattern.match(path, next_position)
            groups = match.groups()
            next_position = match.end()
            if groups[1] == '':
                if closing:
                    raise ValueError('wrong level: missing :' + closing.pop())
                found_separator = True
                block_end = match.end()
            elif not closing and groups[1] is not None:
                found_separator = True
                block_end = match.end() - 1
                if extended_separator and match.group('enditem') == separator:
                    if path[next_position:].startswith(extended_separator):
                        next_position += len(extended_separator)
                    else:
                        found_separator = False
            else:
                char = next((value for value in groups[2:] if value), None)
                if char:
                    if char in "'\"":
                        next_position = path.index(char, next_position) + 1
                    elif char == '(':
                        closing.append(')')
                    elif char == '[':
                        closing.append(']')
                    elif char in '])':
                        if char == closing[-1]:
                            closing.pop()
                        else:
                            raise ValueError('wrong level: missing :' + closing.pop())
        result.append(path[start_position:block_end])
        start = next_position
    return result


def _bag_item_path(itempath):
    """Legacy bagItemFormula path translation; the result is a bound value."""
    items = itempath.split('.')
    suffix = 'text()'
    if '?' in items[-1]:
        items[-1], attribute = items[-1].split('?')
        suffix = f'@{attribute}'
    path = '/'.join(item if not item.startswith('#') else f'*[{int(item[1:]) + 1}]'
                    for item in items)
    return f'/GenRoBag/{path}/{suffix}'



def _in_range(match):
    """Legacy expandInRange: inclusive bounds and SQL three-valued logic."""
    value, low, high = match.groups()
    # Put typed comparisons before IS NULL so PostgreSQL can infer the type
    # of a nullable bound parameter. The four legacy cases are unchanged.
    return (f'(({value}>={low} AND {value}<={high} AND '
            f'{low} IS NOT NULL AND {high} IS NOT NULL) OR '
            f'({low} IS NULL AND {high} IS NOT NULL AND {value}<={high}) OR '
            f'({low} IS NOT NULL AND {high} IS NULL AND {value}>={low}) OR '
            f'({low} IS NULL AND {high} IS NULL))')
