"""PostgreSQL constructors for the existing typed Bag XML wire.

Tag normalization follows genro_bag._legacy_codec; type codes follow the
catalog used by the frozen wire tests. Values and escaping stay in PostgreSQL.
"""
import re

from .._legacy_sql import split_sql


_SQL_TYPES = {
    'smallint': 'L', 'integer': 'L', 'bigint': 'L', 'numeric': 'N',
    'real': 'R', 'double precision': 'R', 'boolean': 'B', 'date': 'D',
    'time without time zone': 'H', 'time with time zone': 'H',
    'timestamp without time zone': 'DH', 'timestamp with time zone': 'DHZ',
    'json': 'JS', 'jsonb': 'JS',
}


def _literal(value):
    return "'" + value.replace("'", "''") + "'"


def _field_xml(name, row, quote):
    value = f'{row}.{quote(name)}'
    # Same normalization as the installed typed Bag codec, without namespaces.
    tag = re.sub('_+', '_', re.sub(r'[^\w.]', '_', name or '_none_', flags=re.ASCII))
    if tag[0].isdigit():
        tag = '_' + tag
    kind = f'pg_typeof({value})::text'
    mapping = ' '.join(f'WHEN {_literal(sqltype)} THEN {_literal(code)}'
                       for sqltype, code in _SQL_TYPES.items())
    marker = f"CASE WHEN {value} IS NULL THEN 'NN' ELSE CASE {kind} {mapping} END END"
    attributes = [f'{marker} AS "_T"']
    if tag != name:
        attributes.insert(0, f'{_literal(name)} AS "_tag"')
    # JSON's scalar text conversion supplies ISO dates/times without depending
    # on DateStyle. Bag's boolean spelling is the existing True/False spelling.
    content = (f"CASE WHEN {kind}='boolean' THEN CASE {value}::text "
               f"WHEN 'true' THEN 'True' WHEN 'false' THEN 'False' END "
               f"ELSE to_json({value}) #>> '{{}}' END")
    return f'xmlelement(NAME {quote(tag)}, xmlattributes({", ".join(attributes)}), {content})'


def bag_xml_subquery(sql, alias, columns, quote):
    row = quote(alias)
    fields = []
    for column in split_sql(columns):
        parts = split_sql(column, ' AS ')
        # The SELECT compiler supplies an outer alias, authored or generated.
        name = parts[-1].strip()
        name = name[1:-1].replace('""', '"') if name.startswith('"') and name.endswith('"') else name.lower()
        fields.append(_field_xml(name, row, quote))
    numbered = quote(alias + '_xml')
    # The ordered SELECT is consumed directly by the window; no JOIN can
    # reorder it. Only generated integer labels enter the XML tag text.
    rows = (f'SELECT row_number() OVER () - 1 AS n, xmlconcat({", ".join(fields)}) AS fields '
            f'FROM ({sql}) AS {row}')
    node = (f"xmlparse(CONTENT '<r_' || {numbered}.n::text || '>' || {numbered}.fields::text "
            f"|| '</r_' || {numbered}.n::text || '>')")
    return (f'(SELECT xmlelement(NAME "GenRoBag", xmlagg({node} ORDER BY {numbered}.n))::text '
            f'FROM ({rows}) AS {numbered})')
