"""Approved aggr arguments, using the existing legacy text helpers.

This expands a projection into child columns, aggregation modes and output names. Field
resolution, correlation, SQL assembly and bindings stay in the SELECT compiler.
"""
import re

from ._legacy_sql import col_to_as, split_sql
from .contracts import UnsupportedFeatureError


def aggregate_columns(arguments, path):
    result = []
    for argument in arguments:
        parts = split_sql(argument.strip(), ' AS ')
        call = re.fullmatch(r'(\w+)\s*\((.*)\)', parts[0].strip(), re.S)
        if call is None:
            raise ValueError('aggr requires aggregate function calls')
        function, text = call.groups()
        function = function.lower()
        if function not in ('count', 'sum', 'avg', 'min', 'max', 'join', 'to_json', 'to_xml'):
            raise UnsupportedFeatureError(f'aggr: {function}() is not available in this release')
        outer_name = parts[1].strip() if len(parts) == 2 else None
        if len(parts) > 2:
            raise ValueError('An aggregate result requires at most one AS')
        if function in ('to_json', 'to_xml'):
            selection = text.strip()
            suffix = '_' + selection.removeprefix('$') if selection else ''
            name = outer_name or col_to_as(path + suffix + '_' + function.removeprefix('to_'))
            result.append((selection or '*', name, function))
            continue
        if function == 'count':
            if text.strip():
                raise UnsupportedFeatureError('aggr: only count() without arguments is supported')
            result.append(('COUNT(*)', outer_name or col_to_as(path + '_count'), None))
            continue
        values = split_sql(text)
        if not text.strip():
            raise ValueError(f'{function} requires an expression')
        if function == 'join':
            if len(values) not in (2, 3):
                raise ValueError('join requires an expression, separator and optional placeholder')
            expression = values[0].strip()
            name = outer_name or col_to_as(path + '_' + expression.removeprefix('$') + '_join')
            expression = column_expression(expression)
            placeholder = values[2] if len(values) == 3 else "''"
            # Normalize each row before aggregation, retaining its position.
            columns = (f"COALESCE(NULLIF(CAST({expression} AS text), ''), {placeholder}) AS value,"
                       f'{values[1]} AS separator')
            result.append((columns, name, 'join'))
            continue
        if outer_name and len(values) != 1:
            raise ValueError('Use AS on each argument of a multiple-column aggregate')
        for value in values:
            parts = split_sql(value.strip(), ' AS ')
            expression = parts[0].strip()
            if not expression or len(parts) > 2 or (len(parts) == 2 and outer_name):
                raise ValueError('An aggregate argument requires an expression and at most one AS')
            name = (parts[1].strip() if len(parts) == 2 else outer_name)
            name = name or col_to_as(path + '_' + expression.removeprefix('$') + '_' + function)
            expression = column_expression(expression)
            result.append((f'{function.upper()}({expression})', name, None))
    if not result:
        raise ValueError('aggr requires at least one aggregate')
    return result


def column_expression(expression):
    # The agreed bare-column shorthand, not a second SQL expression parser.
    if re.fullmatch(r'[a-zA-Z_]\w*', expression) and expression.upper() != 'NULL':
        return '$' + expression
    return expression
