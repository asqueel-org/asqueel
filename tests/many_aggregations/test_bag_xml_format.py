"""Verify the existing typed Bag wire independently of the future compiler."""
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from genro_bag import Bag
import pytest

from tests.many_aggregations.bag_samples import TYPES, VALUES, sample

DATA = Path(__file__).with_name('data')


@pytest.fixture(scope='module')
def catalog():
    module = pytest.importorskip('gnr.core.gnrclasses', reason='Optional real GenroPy catalog for typed Bag round-trip')
    return module.GnrClassCatalog()


def xml_shape(xml):
    """Ignore XML declaration/indentation, never field text or type attributes."""
    def node_shape(node):
        children = list(node)
        return (node.tag, node.attrib, None if children else (node.text or ''),
                [node_shape(child) for child in children])
    return node_shape(ET.fromstring(xml))


def test_oracle_provenance_is_intact():
    metadata = json.loads((DATA / 'provenance.json').read_text())
    assert metadata['bag_version'] == '0.27.0'
    for name, digest in metadata['fixtures'].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == digest


def test_labels_root_and_empty_bag_use_existing_format():
    root = ET.fromstring((DATA / 'rows.xml').read_text())
    assert root.tag == 'GenRoBag'
    assert [node.tag for node in root] == ['r_0', 'r_1']
    assert [node.tag for node in root[0]] == list(VALUES)
    empty = ET.fromstring((DATA / 'empty.xml').read_text())
    assert empty.tag == 'GenRoBag' and len(empty) == 0


@pytest.mark.parametrize('field', list(VALUES))
def test_type_markers_null_empty_and_escaping(field):
    node = ET.fromstring((DATA / 'rows.xml').read_text()).find('r_0/' + field)
    assert node is not None
    assert node.get('_T') == TYPES[field]
    if field == 'code':
        assert node.text == VALUES[field]
    if field in ('empty', 'missing'):
        assert node.text is None
        assert (node.get('_T') == 'NN') == (field == 'missing')


@pytest.mark.parametrize('name', ['rows', 'empty'])
def test_installed_bag_serializer_matches_frozen_wire(catalog, name):
    bag = sample() if name == 'rows' else Bag()
    xml = bag.to_xml(legacy_mode=True, catalog=catalog)
    assert xml_shape(xml) == xml_shape((DATA / f'{name}.xml').read_text())


def test_real_bag_parser_restores_values_types_and_labels(catalog):
    bag = Bag.from_xml((DATA / 'rows.xml').read_text(), legacy_mode=True, catalog=catalog)
    assert [node.label for node in bag] == ['r_0', 'r_1']
    for name, expected in VALUES.items():
        actual = bag.get_item('r_0.' + name)
        assert actual == expected
        assert type(actual) is type(expected)
    assert bag.get_item('r_1.code') == 'second'
    assert len(Bag.from_xml((DATA / 'empty.xml').read_text(), legacy_mode=True, catalog=catalog)) == 0


# Fixed SQL witness only: no generic generator, handler or compiler patch.
# Explicit node names/types follow the frozen serializer output above.
XML_SQL = '''SELECT xmlelement(NAME "GenRoBag",
    xmlelement(NAME r_0,
        xmlelement(NAME code, %(code)s::text),
        xmlelement(NAME empty, ''::text),
        xmlelement(NAME missing, xmlattributes('NN' AS "_T")),
        xmlelement(NAME integer, xmlattributes('L' AS "_T"), %(integer)s::bigint),
        xmlelement(NAME amount, xmlattributes('N' AS "_T"), %(amount)s::numeric),
        xmlelement(NAME real, xmlattributes('R' AS "_T"), %(real)s::double precision),
        xmlelement(NAME active, xmlattributes('B' AS "_T"), 'True'),
        xmlelement(NAME inactive, xmlattributes('B' AS "_T"), 'False'),
        xmlelement(NAME day, xmlattributes('D' AS "_T"), %(day)s::date),
        xmlelement(NAME clock, xmlattributes('H' AS "_T"), %(clock)s::time),
        xmlelement(NAME utc, xmlattributes('DHZ' AS "_T"), %(utc)s::text)),
    xmlelement(NAME r_1, xmlelement(NAME code, 'second')))::text'''


@pytest.mark.postgresql
def test_postgres_xml_constructors_match_bag_wire():
    import psycopg
    from tests.native_support import postgres_dsn
    values = dict(VALUES, utc=VALUES['utc'].isoformat())
    with psycopg.connect(postgres_dsn()) as connection:
        xml = connection.execute(XML_SQL, values).fetchone()[0]
    assert xml_shape(xml) == xml_shape((DATA / 'rows.xml').read_text())


@pytest.mark.postgresql
def test_postgres_generated_xml_roundtrips_through_bag(catalog):
    import psycopg
    from tests.native_support import postgres_dsn
    with psycopg.connect(postgres_dsn()) as connection:
        xml = connection.execute(XML_SQL, dict(VALUES, utc=VALUES['utc'].isoformat())).fetchone()[0]
    bag = Bag.from_xml(xml, legacy_mode=True, catalog=catalog)
    assert [node.label for node in bag] == ['r_0', 'r_1']
    for name, expected in VALUES.items():
        actual = bag.get_item('r_0.' + name)
        assert actual == expected and type(actual) is type(expected)
