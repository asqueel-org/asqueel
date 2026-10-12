"""Portable validation declarations and deterministic local rules."""
from __future__ import annotations

import re
from collections.abc import Mapping

RULES = {'notnull', 'len', 'min', 'max', 'regex', 'email', 'values', 'nodup', 'exists', 'messages'}


def normalize_embedded(values):
    rules, normalization, messages = {}, {}, {}
    for name, value in values.items():
        if name == 'case':
            normalization['case'] = value
        elif name.endswith('_error') and name[:-6] in RULES - {'messages'}:
            messages[name[:-6]] = value
        elif name in RULES:
            rules[name] = value
        else:
            raise ValueError(f'Unknown validation rule {name!r}')
    if messages:
        rules['messages'] = {**rules.get('messages', {}), **messages}
    return rules, normalization


def length_bounds(value):
    if isinstance(value, bool):
        raise ValueError('validation.len must be an integer or min:max')
    if isinstance(value, int):
        low = high = value
    elif isinstance(value, str) and re.fullmatch(r'\d*:\d*', value) and value != ':':
        lo, hi = value.split(':')
        low, high = int(lo) if lo else 0, int(hi) if hi else None
    else:
        raise ValueError('validation.len must be an integer or min:max')
    if low < 0 or high is not None and high < low:
        raise ValueError('validation.len has an inverted/negative range')
    return low, high


def validate_spec(spec):
    unknown = set(spec) - RULES - {'_meta'}
    if unknown:
        raise ValueError(f'Unknown validation rules: {sorted(unknown)}')
    for name in ('notnull', 'email', 'nodup'):
        if name in spec and not isinstance(spec[name], bool):
            raise ValueError(f'validation.{name} requires bool')
    if spec.get('len') is not None:
        length_bounds(spec['len'])
    if spec.get('regex') is not None:
        re.compile(spec['regex'])
    if spec.get('min') is not None and spec.get('max') is not None and spec['min'] > spec['max']:
        raise ValueError('validation.min exceeds max')
    if spec.get('messages') is not None and (not isinstance(spec['messages'], Mapping) or any(
            rule not in RULES - {'messages'} or not isinstance(text, str)
            for rule, text in spec['messages'].items())):
        raise ValueError('validation.messages requires known rules and string messages')


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
    if spec.get('nodup') or spec.get('exists'):
        raise ValueError('nodup/exists require an authoritative server validator')
    return tuple(failures)
