"""Independent all-package acceptance tests for the migration milestone."""
import json
from pathlib import Path
from xml.etree import ElementTree

import pytest

from asqueel.legacy_source import from_expanded_legacy_xml
from asqueel_migration import SqlMigrator

SOURCE = Path(__file__).parent / 'oracles/test_invoice_pg'


#: Legacy attributes outside the asqueel grammar, removed from a copy of the
#: frozen oracle before loading it (the oracle itself stays byte-identical).
OUTSIDE_GRAMMAR = {
    'package': {'_syspackage', 'name_full'},
    'table': {'archivable', 'atc_attachmenttable', 'audit', 'broadcast', 'checkpref', 'counter',
              'group_b_address', 'group_c_contacts', 'group_d_billing', 'group_e_activity',
              'group_subtables', 'group_y_other', 'group_z_relations', 'group_zzz', 'hierarchical',
              'hierarchical_caption_field', 'lastTS', 'multi_tenant', 'noTestForMerge',
              'partition_customer_state', 'partition_state', 'retention_policy', 'sysRecord_masterfield'},
    'column': {'_counter_fkey', '_owner_package', '_sendback', '_sysfield', 'batch_assign', 'counter',
               'defaultFrom', 'encrypted', 'hierarchical_field_of', 'legacy_name', 'one_group',
               'readOnly', 'subfields', 'values'},
    'virtual_column': {'_addClass', '_owner_package', '_sysfield', 'bagcolumn', 'cell_format', 'format',
                       'itempath', 'subquery', 'template_localized', 'template_name'},
}
#: Extra keys of a composite (composed_of) and of a join_column relation.
COMPOSITE_OUTSIDE_GRAMMAR = {'dtype', 'sql_formula', 'static'}
JOIN_RELATION_OUTSIDE_GRAMMAR = {'mode', 'onUpdate_sql', 'one_one', 'relation_name'}


def grammar_copy():
    """The oracle source and profile without what lies outside the asqueel grammar."""
    root = ElementTree.fromstring((SOURCE / 'source.xml').read_bytes())
    for parent in root.iter():
        for child in list(parent):
            if child.get('tag') == 'subtable_list':
                parent.remove(child)
                continue
            strip = set(OUTSIDE_GRAMMAR.get(child.get('tag'), ()))
            if child.get('composed_of'):
                strip |= COMPOSITE_OUTSIDE_GRAMMAR
            if child.tag == 'relation' and parent.get('join_column'):
                strip |= JOIN_RELATION_OUTSIDE_GRAMMAR
            for key in strip & set(child.keys()):
                del child.attrib[key]
    profile = json.loads((SOURCE / 'adapter-profile.json').read_text())
    for aliases in profile['type_aliases'].values():
        for spec in aliases.values():
            spec.pop('x_ui', None)
    return ElementTree.tostring(root, encoding='unicode'), profile


def invoice_source():
    document, profile = grammar_copy()
    return from_expanded_legacy_xml(document, **profile)


def test_legacy_loader_refuses_the_first_attribute_outside_the_grammar():
    profile = json.loads((SOURCE / 'adapter-profile.json').read_text())
    with pytest.raises(ValueError, match="sys: legacy attribute '_syspackage' is outside the asqueel grammar"):
        from_expanded_legacy_xml((SOURCE / 'source.xml').read_text(), **profile)


def test_legacy_loader_builds_the_grammar_copy_of_the_oracle():
    builder = invoice_source()
    builder.validate_source()
    table = builder.source['db.packages.invc.tables.invoice']
    assert table.get_attr('logicalDeletionField') == '__del_ts'
    assert 'lastTS' not in table.attr


def prepared(database, structure):
    migrator = SqlMigrator(database, removeDisabled=True)
    migrator.ormStructure = structure
    migrator.prepareMigrationCommands()
    assert not migrator.warnings, migrator.warnings
    return migrator
