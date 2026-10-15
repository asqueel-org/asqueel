"""Parameter scopes for one compilation, independent of SQL table aliases.

The allocator is shared by query, formula and subquery scopes. Values and
their scalar/collection usage belong to an origin, not to a mangled spelling.
Nothing is cached on the model or written into the application environment.
"""
from .query_plan import Parameter, expand_collection, member_name, parameter_use


class _Bindings:
    def __init__(self, values, dialect, snapshot, *, parent=None, namespace=''):
        self.available = dict(parent.available) if parent else {}
        self.available.update(values or {})
        self.dialect, self.snapshot = dialect, snapshot
        self.namespace = namespace
        self.params = parent.params if parent else {}
        self.state = parent.state if parent else {'counter': 0, 'names': set(), 'uses': {}}
        self.state['names'].update(self.available)
        self.environment_keys = parent.environment_keys if parent else set()
        self.consumed_inputs = parent.consumed_inputs if parent else set()
        self.input_origins = (parent.input_origins - set(values or {})
                              if parent else set(self.available))
        self.use_keys = dict(parent.use_keys) if parent else {}
        self.use_keys.update({name: (namespace, name) for name in values or {}})
        self.binding_names = {}

    def child(self, values, prefix):
        self.state['counter'] += 1
        return _Bindings(values, self.dialect, self.snapshot, parent=self,
                         namespace=f'{prefix}{self.state["counter"]}_')

    def add(self, name, value):
        """Reserve a generated input (period bound or policy) without capture."""
        while name in self.state['names']:
            name = '_' + name
        self.state['names'].add(name)
        self.available[name] = value
        return name

    def resolve(self, name):
        if name in self.input_origins:
            self.consumed_inputs.add(name)
        if name not in self.available:
            if name.startswith('env_'):
                key = name[4:]
                self.environment_keys.add(key)
                if key in self.snapshot:
                    self.available[name] = self.snapshot[key]
            if name not in self.available:
                raise ValueError(f'Missing query parameter: {name}')

    def _use(self, name, collection):
        self.resolve(name)
        parameter_use(self.state['uses'], self.use_keys.get(name, ('', name)),
                      collection, label=name)

    def binding(self, name):
        self._use(name, False)
        if name not in self.binding_names:
            bound_name = self.namespace + name
            if self.namespace:
                while bound_name in self.state['names']:
                    bound_name = '_' + bound_name
            self.state['names'].add(bound_name)
            self.binding_names[name] = bound_name
        bound_name = self.binding_names[name]
        self.params[bound_name] = self.available[name]
        return Parameter(bound_name)

    def collection(self, name, negated):
        self._use(name, True)

        def allocate(member):
            bound_name = member_name(self.namespace + name, self.state['names'])
            self.params[bound_name] = member
            return bound_name

        return expand_collection(name, self.available[name], negated, allocate,
                                 self.dialect.empty_collection)
