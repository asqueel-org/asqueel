"""Physical projection of the completed hierarchy, following legacy OrmExtractor.

Only the existing physical builder is produced. No source expansion, resolved
descriptor graph, formula analysis, connection or compiler is involved.
"""
from collections.abc import Mapping

from .builder import SqlBuilder
from .common import INDEX_OPTIONS, default_index_name, split_names
from .contracts import UnsupportedFeatureError
from .projection import _column_storage


def _fields(model, table, names):
    return [field for name in split_names(names) for field in model.physical_columns(table, name)]


def _mapped(model, table, names):
    return ','.join(table.columns[name].sqlname for name in _fields(model, table, names))


def _indexes(model, table, node):
    container = None
    pkey = _fields(model, table, table.pkey)
    for index in table.indexes.values():
        attrs = index.attributes
        names = split_names(attrs['columns'])
        generated = index.structnode is None
        # Automatic indexes on a PK or a UNIQUE column are already represented
        # by the corresponding constraint, as in the existing migration renderer.
        if generated and (names == pkey or (len(names) == 1 and
                                           table.columns[names[0]].attributes.get('unique'))):
            continue
        data = {key: attrs[key] for key in INDEX_OPTIONS if attrs.get(key) is not None}
        columns = attrs['columns']
        data['columns'] = ({table.columns[name].sqlname: order for name, order in columns.items()}
                           if isinstance(columns, Mapping) else _mapped(model, table, columns))
        if data.get('where') and any(c.sqlname != c.name for c in table.columns.values()):
            raise UnsupportedFeatureError(f'{table.fullname}: partial index with remapped columns')
        if container is None:
            container = node.indexes()
        # The GenroPy default name leaves the physical name to the migrator, as legacy.
        name = None if index.name == default_index_name(table.name, names) else index.name
        container.index(name=name, **data)


def _constraints(model, table, node):
    constraints = table.get('constraints')
    if constraints is None:
        return
    container = node.constraints()
    for constraint in constraints.values():
        attrs = constraint.attributes
        data = {key: attrs[key] for key in ('constraint_type', 'columns', 'check_clause') if key in attrs}
        if data.get('columns'):
            data['columns'] = _mapped(model, table, data['columns'])
        if data.get('check_clause') and any(c.sqlname != c.name for c in table.columns.values()):
            raise UnsupportedFeatureError(f'{table.fullname}: CHECK with remapped columns')
        container.constraint(constraint.name, **data)


def project_tree(model) -> SqlBuilder:
    """Translate physical objects and outbound FK joiners to the existing grammar."""
    result = SqlBuilder()
    db = result.source.db(model.name)
    extensions = model._database.get('extensions')
    if extensions is not None:
        container = db.extensions()
        for extension in extensions.values():
            container.extension(extension.name)
    schemas = db.schemas()
    schema_nodes = {}
    for package in model.obj.values():
        if package.sqlschema not in schema_nodes:
            schema_nodes[package.sqlschema] = schemas.schema(package.sqlschema).tables()
    owners = {}
    for table in model.tables.values():
        if table.sqlschema not in schema_nodes:
            if table.pkg.tag == 'package':
                raise ValueError(f'{table.fullname}: sqlschema {table.sqlschema!r} is not derived from a package')
            schema_nodes[table.sqlschema] = schemas.schema(table.sqlschema).tables()
        attrs = {'comment': table.attributes['comment']} if table.attributes.get('comment') else {}
        node = schema_nodes[table.sqlschema].table(
            table.sqlname, pkey=_mapped(model, table, table.pkey) or None, **attrs)
        columns = node.columns()
        for column in table.columns.values():
            dtype, attrs = _column_storage(
                column, packaged=table.pkg.tag == 'package',
                implementation=model.implementation)
            owners[(table.fullname, column.name)] = columns.column(column.sqlname, dtype=dtype, **attrs)
        if table.composites:
            composites = node.composites()
            for column in table.composites.values():
                owners[(table.fullname, column.name)] = composites.compositeColumn(
                    column.name, columns=_mapped(model, table, column.attributes['columns']),
                    unique=column.attributes.get('unique', False))
        _constraints(model, table, node)
        _indexes(model, table, node)

    # The global relation branch is the authority for endpoints and direction.
    # Read declaration-only SQL attributes (e.g. deferrable) from the same owner.
    for package in model.relations:
        for table_node in package.value:
            for relation in table_node.value:
                joiner = relation.attr
                if joiner['mode'] != 'O' or not joiner.get('foreignkey'):
                    continue
                local_name, local_column = joiner['many_relation'].rsplit('.', 1)
                remote_name, remote_column = joiner['one_relation'].rsplit('.', 1)
                table, remote = model.table(local_name), model.table(remote_name)
                owner = owners.get((local_name, local_column))
                if owner is None:
                    raise UnsupportedFeatureError(f'{local_name}.{local_column}: physical FK on virtual column')
                column = table.column(local_column)
                declaration = next(child for child in column.values()
                                   if child.tag == 'relation')
                target = remote.composites.get(remote_column) or remote.columns.get(remote_column)
                if target is None:
                    raise UnsupportedFeatureError(f'{remote_name}.{remote_column}: physical FK to virtual column')
                target_name = remote_column if target.tag == 'compositeColumn' else target.sqlname
                attrs = {key: declaration.attributes[key] for key in (
                    'onDelete_sql', 'onUpdate_sql', 'deferrable', 'initially_deferred',
                    'deferred', 'indexed', 'constraint_name',
                ) if key in declaration.attributes}
                owner.relation(f'{remote.sqlschema}.{remote.sqlname}.{target_name}', foreign_key=True, **attrs)
    result.validate_model()
    return result
