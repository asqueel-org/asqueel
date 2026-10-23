"""Helpers of the database environment: copied values and the :env_* query arguments."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import date
import re
from typing import Any


_TRANSACTION_KEYS = re.compile(r'((to|after)_commit_defer_calls|_pendingExceptions|_virtual_columns)_.*')


def _copy_values(values: Mapping[str, Any], operation: str) -> dict[str, Any]:
    try:
        return deepcopy(dict(values))
    except Exception as error:
        raise ValueError(
            f'Cannot copy SQL environment values during {operation}; '
            'values must support deepcopy'
        ) from error



def environment_arguments(keys, snapshot):
    """The :env_* values of ``keys`` in ``snapshot``, read at every execution as legacy execute."""
    params = {'env_' + key: snapshot.get(key) for key in keys}
    if 'env_workdate' in params:
        params['env_workdate'] = params['env_workdate'] or date.today()
    return params
