"""Resolve declarative models into the deliberately small native SQL profile."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from genro_toolbox import extract_kwargs

from .contracts import (
    PartitionScope, RowPolicies, UnsupportedFeatureError,
)


def column_ui(path: str, identity: str,
              ui: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    """Apply the path overlay, then the stable identity overlay."""
    result: dict[str, Any] = {}
    overlays = ui or {}
    result.update(overlays.get(path, {}))
    if identity != path:
        result.update(overlays.get(identity, {}))
    forbidden = {'dtype', 'formula', 'sql_name', 'notnull', 'unique', 'pkey'} & result.keys()
    if forbidden:
        raise ValueError(f'UI metadata cannot override column semantics: {sorted(forbidden)}')
    return result


def _subquery_definition(value, label):
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(f'{label}: subquery method reference must be nonempty')
        return value  # Resolve on the current SELECT's table, only at compilation.
    if not isinstance(value, Mapping):
        raise ValueError(f'{label}: subquery must be a mapping')
    for required in ('table', 'where'):
        field = value.get(required)
        if not isinstance(field, str) or not field.strip():
            raise ValueError(f'{label}: subquery requires nonempty {required}')
    return deepcopy(dict(value))


def _formula_definition(metadata, label):
    if metadata.get('sql_formula') is not None and metadata.get('expression') is not None:
        raise ValueError(f'{label}: sql_formula and expression are aliases; specify only one')
    formula = metadata.get('sql_formula')
    if formula is None:
        formula = metadata.get('expression')
    select, exists = metadata.get('select'), metadata.get('exists')
    if formula is True:
        raise UnsupportedFeatureError(f'{label}: SQL formula method callbacks are unsupported')
    if formula is not None and (not isinstance(formula, str) or not formula.strip()):
        raise ValueError(f'{label}: sql_formula must be a nonempty string')
    if sum(value is not None for value in (formula, select, exists)) != 1:
        raise ValueError(f'{label}: specify exactly one of sql_formula, select, exists')
    subqueries = {key[7:]: _subquery_definition(value, f'{label}.{key}')
                  for key, value in metadata.items() if key.startswith('select_')}
    if subqueries and formula is None:
        raise ValueError(f'{label}: named subqueries require sql_formula')
    for name in subqueries:
        if not re.search(r'#' + re.escape(name) + r'\b', formula):
            raise ValueError(f'{label}: unused named subquery {name!r}')
    return (formula,
            _subquery_definition(select, f'{label}.select') if select is not None else None,
            _subquery_definition(exists, f'{label}.exists') if exists is not None else None,
            subqueries)


@extract_kwargs(var=True)
def _formula_parameters(label, *, var_kwargs=None, parameters=None, **attributes):
    """Existing var_* declarations and their parameters spelling, scoped locally."""
    if parameters is not None and not isinstance(parameters, Mapping):
        raise ValueError(f'{label}: formula parameters must be a mapping')
    local = dict(parameters or {})
    repeated = local.keys() & (var_kwargs or {}).keys()
    if repeated:
        raise ValueError(f'{label}: repeated formula parameters: {sorted(repeated)}')
    local.update(var_kwargs or {})
    if any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_]\w*', name)
           for name in local):
        raise ValueError(f'{label}: formula parameters require valid names')
    return local




def _policy_field(value, label: str) -> str:
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError(f'{label} must name a column or forward relation path')
    if value.startswith('$"'):
        if not re.fullmatch(r'\$"(?:[^"]|"")+"', value):
            raise ValueError(f'{label}: malformed quoted field')
        return value[2:-1].replace('""', '"')
    return value[1:] if value.startswith('$') else value


def _parse_row_policies(attributes: Mapping[str, Any]) -> RowPolicies:
    if 'x_partition' in attributes and 'x_partitions' in attributes:
        raise ValueError('x_partition and x_partitions are mutually exclusive')
    definitions = []
    if 'x_partition' in attributes:
        definitions = [attributes['x_partition']]
    elif 'x_partitions' in attributes:
        definitions = attributes['x_partitions']
        if not isinstance(definitions, (list, tuple)) or not definitions:
            raise ValueError('x_partitions must be a nonempty list of partition mappings')
    partitions = []
    for definition in definitions:
        if not isinstance(definition, Mapping):
            raise ValueError('Each partition must be a mapping')
        unknown = definition.keys() - {'field', 'current', 'allowed', 'include_null'}
        if unknown:
            raise ValueError(f'Unknown partition options: {sorted(unknown)}')
        if not {'field', 'current'} <= definition.keys():
            raise ValueError('Partition requires field and current environment key')
        partitions.append(PartitionScope(
            _policy_field(definition['field'], 'partition field'), definition['current'],
            definition.get('allowed'), definition.get('include_null', True),
        ))
    markers = {}
    for key, native, target in [
            ('x_draft_field', 'x_legacy_draftField', 'draft_field'),
            ('x_logical_deletion_field', 'x_legacy_logicalDeletionField', 'logical_deletion_field')]:
        declared = [_policy_field(attributes[k], k) for k in (key, native) if k in attributes]
        if len(set(declared)) > 1:
            raise ValueError(f'Conflicting row policy markers: {key}, {native}')
        if declared:
            markers[target] = declared[0]
    return RowPolicies(tuple(partitions), **markers)


def resolve_model(builder):
    """Render the source into the single hierarchical model, without a connection."""
    from .configuration import _owned_handler
    from .object_tree_renderer import render_model
    return render_model(_owned_handler(builder))
