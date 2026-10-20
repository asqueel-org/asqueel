"""Legacy GnrNamedList assertions against the published Toolbox port."""
import pytest
from genro_toolbox import NamedList


def test_GnrNamedList():
    gnl = NamedList(dict(name=0, surname=1),
                          ["Arthur", "Dent"])

    assert gnl['name'] == "Arthur"
    assert gnl.keys() == ['name','surname']
    for x in gnl.iteritems():
        assert x[0] in ("name", "surname")
        assert x[1] in ("Arthur", "Dent")

    i = gnl.items()
    assert ('name', 'Arthur') in i
    assert ('surname', 'Dent') in i
    assert ('name', 'Ford') not in i
    assert ('surname', 'Prefect') not in i

    assert "name" in gnl
    assert "surname" in gnl
    assert "planet" not in gnl

    assert gnl.has_key("name")
    assert gnl.has_key("surname")
    assert not gnl.has_key("planet")

    assert gnl.get("name") == "Arthur"
    assert gnl.get("planet", "Earth") == "Earth"

    assert "name=" in str(gnl)
    assert "surname=" in str(gnl)
    assert "name=" in repr(gnl)
    assert "surname=" in repr(gnl)


    gnl['planet'] = "Earth"
    assert gnl.get('planet') == "Earth"


    with pytest.raises(IndexError) as excinfo:
        gnl[12] = "goober"
    assert str(excinfo.value) == "list assignment index out of range"

    with pytest.raises(IndexError) as excinfo:
        gnl[122]
    assert str(excinfo.value) == "list index out of range"


    gnl = NamedList(dict(name=0, surname=1))


def test_GnrNamedList_extractMethods():
    """Test extractItems and extractValues methods"""
    index = {'name': 0, 'age': 1, 'city': 2}
    row = NamedList(index, ['Alice', 30, 'NYC'])

    # extractItems with specific columns
    items = row.extractItems(['name', 'city'])
    assert items == [('name', 'Alice'), ('city', 'NYC')]

    # extractItems with all columns
    all_items = row.extractItems(None)
    assert len(all_items) == 3
    assert ('name', 'Alice') in all_items

    # extractValues with specific columns
    values = row.extractValues(['age', 'name'])
    assert values == [30, 'Alice']

    # extractValues with all columns
    all_values = row.extractValues(None)
    assert len(all_values) == 3
    assert 'Alice' in all_values


def test_GnrNamedList_dynamic_columns():
    """Test dynamic column addition"""
    index = {'name': 0, 'age': 1}
    row = NamedList(index, ['Alice', 30])

    # Add new column
    row['city'] = 'NYC'
    assert row['city'] == 'NYC'
    assert 'city' in row
    assert row._index['city'] == 2

    # Update existing column
    row['age'] = 31
    assert row['age'] == 31

    # Add another new column
    row['country'] = 'USA'
    assert row['country'] == 'USA'
    assert len(row._index) == 4


def test_GnrNamedList_iteritems():
    """Test iteritems method"""
    index = {'name': 0, 'age': 1, 'city': 2}
    row = NamedList(index, ['Alice', 30, 'NYC'])

    items_list = list(row.iteritems())
    assert len(items_list) == 3
    assert ('name', 'Alice') in items_list
    assert ('age', 30) in items_list
    assert ('city', 'NYC') in items_list


def test_GnrNamedList_values():
    """Test values method"""
    index = {'name': 0, 'age': 1}
    row = NamedList(index, ['Alice', 30])

    values = row.values()
    assert isinstance(values, tuple)
    assert len(values) == 2
    assert 'Alice' in values
    assert 30 in values


def test_GnrNamedList_sql_adapter_compatibility():
    """Test GnrNamedList works correctly when used by SQL adapter (gnrdict_row)"""
    # Simulate how gnrdict_row creates GnrNamedList
    index = {'id': 0, 'name': 1, 'email': 2}
    values = [1, 'John Doe', 'john@example.com']

    row = NamedList(index, values=values)

    # Test numeric access (as list)
    assert row[0] == 1
    assert row[1] == 'John Doe'
    assert row[2] == 'john@example.com'

    # Test named access (as dict)
    assert row['id'] == 1
    assert row['name'] == 'John Doe'
    assert row['email'] == 'john@example.com'

    # Test slice access (critical for SQL adapter)
    assert row[:] == [1, 'John Doe', 'john@example.com']
    assert row[0:2] == [1, 'John Doe']
    assert row[1:] == ['John Doe', 'john@example.com']

    # Test negative indexing
    assert row[-1] == 'john@example.com'
    assert row[-2] == 'John Doe'

    # Test iteration
    result = list(row)
    assert result == [1, 'John Doe', 'john@example.com']

    # Test len
    assert len(row) == 3


def test_GnrNamedList_sql_adapter_with_duplicates():
    """Test GnrNamedList with duplicate column names (from reader with duplicates)"""
    # Simulate reader that renamed duplicate columns
    index = {'id': 0, 'value': 1, 'value[2]': 2, 'value[3]': 3}
    values = [1, 10, 20, 30]

    row = NamedList(index, values=values)

    # Test all columns are accessible
    assert row['id'] == 1
    assert row['value'] == 10
    assert row['value[2]'] == 20
    assert row['value[3]'] == 30

    # Test numeric access still works
    assert row[0] == 1
    assert row[1] == 10
    assert row[2] == 20
    assert row[3] == 30

    # Test slice access
    assert row[:] == [1, 10, 20, 30]
    assert row[1:] == [10, 20, 30]


def test_GnrNamedList_mixed_access_patterns():
    """Test GnrNamedList with various access patterns used in production code"""
    index = {'transaction_id': 0, 'user_name': 1, 'amount': 2}
    values = ['TX123', 'Alice', 100.50]

    row = NamedList(index, values=values)

    # Common patterns used in tableImporterCheck and related code

    # Pattern 1: Iterate and access by name
    for item in row:
        assert item is not None

    # Pattern 2: Convert to dict
    row_dict = dict(row)
    assert 'transaction_id' in row_dict or 0 in row_dict

    # Pattern 3: Slice and process
    subset = row[1:]
    assert len(subset) == 2
    assert subset[0] == 'Alice'

    # Pattern 4: Check membership (for index)
    assert 'transaction_id' in row._index
    assert 'user_name' in row._index

    # Pattern 5: Enumerate
    for i, value in enumerate(row):
        assert row[i] == value
