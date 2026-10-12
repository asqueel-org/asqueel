"""Versioned JSON data for the semantic model; never connection configuration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
import json

from .contracts import Column, Relation, Table, ResolvedModel, RowPolicies, PartitionScope
from .model_sections import Schema, Package, Option, Declaration

_TYPES = {cls.__name__: cls for cls in (
    Column, Relation, Table, ResolvedModel, RowPolicies, PartitionScope,
    Schema, Package, Option, Declaration)}


def _encode(value):
    if is_dataclass(value) and type(value).__name__ in _TYPES:
        return {'kind': type(value).__name__, 'fields': {
            field.name: _encode(getattr(value, field.name)) for field in fields(value)}}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError('Model mappings require string keys')
        return {'mapping': {key: _encode(item) for key, item in value.items()}}
    if isinstance(value, list):
        return {'list': [_encode(item) for item in value]}
    if isinstance(value, tuple):
        return {'sequence': [_encode(item) for item in value]}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f'Model export requires symbolic references, not {type(value).__name__}')


def _decode(value):
    if not isinstance(value, dict):
        if value is None or isinstance(value, (str, bool, int, float)):
            return value
        raise ValueError('Invalid model value')
    if set(value) == {'mapping'} and isinstance(value['mapping'], dict):
        return {key: _decode(item) for key, item in value['mapping'].items()}
    if set(value) == {'list'} and isinstance(value['list'], list):
        return [_decode(item) for item in value['list']]
    if set(value) == {'sequence'} and isinstance(value['sequence'], list):
        return tuple(_decode(item) for item in value['sequence'])
    if set(value) == {'kind', 'fields'} and value['kind'] in _TYPES:
        cls = _TYPES[value['kind']]
        return cls(**{key: _decode(item) for key, item in value['fields'].items()})
    raise ValueError('Unknown semantic model record')


def model_to_json(model: ResolvedModel, *, indent=2) -> str:
    return json.dumps({'format': 'asqueel.model', 'version': 1, 'model': _encode(model)},
                      ensure_ascii=False, allow_nan=False, indent=indent) + '\n'


def model_from_json(document: str) -> ResolvedModel:
    envelope = json.loads(document)
    if (set(envelope) != {'format', 'version', 'model'} or
            envelope['format'] != 'asqueel.model' or envelope['version'] != 1):
        raise ValueError('Unsupported semantic model format/version')
    model = _decode(envelope['model'])
    if not isinstance(model, ResolvedModel):
        raise ValueError('Expected a resolved database model')
    return model
