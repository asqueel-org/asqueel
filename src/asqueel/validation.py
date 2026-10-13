"""Portable validation declarations and deterministic local rules."""
from __future__ import annotations

import re

RULES = {'notnull', 'len', 'min', 'max', 'regex', 'email', 'values', 'nodup', 'exist', 'case'}
ERROR_KEYS = {f'{name}_error' for name in RULES}


def is_lookup_parameter(name):
    """Legacy lookup-rule attributes, including nodup's open query parameters."""
    return any(name.startswith(prefix) and len(name) > len(prefix)
               for prefix in ('exist_', 'nodup_'))


def length_bounds(value):
    if isinstance(value, bool):
        raise ValueError('validation.len must be an integer or min:max')
    if isinstance(value, int):
        low = high = value
    elif isinstance(value, str) and value.isdecimal():
        low = high = int(value)
    elif isinstance(value, str) and re.fullmatch(r'\d*:\d*', value) and value != ':':
        lo, hi = value.split(':')
        low, high = int(lo) if lo else 0, int(hi) if hi else None
    else:
        raise ValueError('validation.len must be an integer or min:max')
    if low < 0 or high is not None and high < low:
        raise ValueError('validation.len has an inverted/negative range')
    return low, high


def validate_spec(spec):
    unknown = {name for name in spec if name not in RULES | ERROR_KEYS | {'_meta'}
               and not is_lookup_parameter(name)}
    if unknown:
        raise ValueError(f'Unknown validation rules: {sorted(unknown)}')
    for name in ('notnull', 'email'):
        if name in spec and not isinstance(spec[name], bool):
            raise ValueError(f'validation.{name} requires bool')
    for name in ('exist', 'nodup'):
        if name in spec and not isinstance(spec[name], (bool, str)):
            raise ValueError(f'validation.{name} requires bool or str')
    if spec.get('len') is not None:
        length_bounds(spec['len'])
    # Legacy regex syntax belongs to its consumer; do not parse it as Python.
    if spec.get('case') is not None and not isinstance(spec['case'], str):
        raise ValueError('validation.case requires str')
    if spec.get('min') is not None and spec.get('max') is not None and spec['min'] > spec['max']:
        raise ValueError('validation.min exceeds max')
    for key in ERROR_KEYS:
        if spec.get(key) is not None and not isinstance(spec[key], str):
            raise ValueError(f'validation.{key} requires str')


def validate_value(value, spec):
    """Return local failed rules; server-only rules are explicitly reported."""
    validate_spec(spec)
    failures = []
    if spec.get('notnull') and (value is None or value == ''):
        failures.append('notnull')
    if value is None:
        return tuple(failures)
    if spec.get('len') is not None:
        low, high = length_bounds(spec['len'])
        if len(value) < low or high is not None and len(value) > high:
            failures.append('len')
    for name, invalid in (('min', lambda bound: value < bound), ('max', lambda bound: value > bound)):
        if spec.get(name) is not None and invalid(spec[name]):
            failures.append(name)
    if spec.get('regex') and re.search(spec['regex'], value) is None:
        failures.append('regex')
    if spec.get('email') and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value) is None:
        failures.append('email')
    if spec.get('values') is not None and value not in spec['values']:
        failures.append('values')
    if spec.get('nodup') or spec.get('exist'):
        raise ValueError('nodup/exist require an authoritative server validator')
    return tuple(failures)
