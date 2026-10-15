"""Text bindings for the hierarchical compiler, independent of SQL aliases.

The allocator and scope inheritance follow _compiler_bindings._Bindings;
substitution follows the legacy experimental mangle algorithm. No Parameter,
Fragment, model state or application environment is written here.
"""
from copy import deepcopy
import re


class SqlBindings:
    def __init__(self, values=None, *, parent=None, prefix=''):
        values = deepcopy(dict(values or {}))
        self.available = dict(parent.available) if parent else {}
        self.available.update(values)
        self.params = parent.params if parent else dict(values)
        self.state = parent.state if parent else {'counter': 0, 'names': set(), 'generated': set()}
        self.state['names'].update(values)
        self.consumed = parent.consumed if parent else set()
        self.inputs = parent.inputs - values.keys() if parent else set(values)
        self.names = dict(parent.names) if parent else {}
        self.embed_values = dict(parent.embed_values) if parent else {}
        for name in values:
            self.embed_values.pop(name, None)
        if prefix != 'f':
            self.embed_values.update(values)
        self.namespace = ''
        if parent:
            self.state['counter'] += 1
            namespace = self.namespace = f'{prefix}{self.state["counter"]}_'
            for name in values:
                bound = namespace + name
                while bound in self.state['names']:
                    bound = '_' + bound
                self.state['names'].add(bound)
                self.names[name] = bound
                self.state['generated'].add(bound)
        else:
            self.names.update({name: name for name in values})

    def child(self, values, prefix):
        return type(self)(values, parent=self, prefix=prefix)

    def add(self, name, value):
        """Existing allocator for policy/period values, outside caller inputs."""
        name = self.namespace + name
        while name in self.state['names']:
            name = '_' + name
        self.state['names'].add(name)
        self.state['generated'].add(name)
        self.available[name] = deepcopy(value)
        self.names[name] = name
        self.params[name] = self.available[name]
        return name

    def substitute(self, sql):
        def replace(match):
            name = match[2]
            if name not in self.names:
                return match[0]
            if name in self.inputs:
                self.consumed.add(name)
            bound = self.names[name]
            self.params[bound] = self.available[name]
            return f'{match[1]}{bound}{match[3]}'
        return re.sub(r'(:)(\w+)(\W|$)', replace, sql)
