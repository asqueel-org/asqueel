"""Existing Bag value checks using the hierarchical compiler."""
import pytest

from tests.native_compiler.test_bag_items import source
from tests.native_formulas.test_bag_item_results import (
    db as execution_db,  # noqa: F401
    test_exact_text_numeric_attribute_position_and_first_match as test_exact_text_numeric_attribute_position_and_first_match,
    test_typed_values_use_postgres_casts_and_existing_driver_codecs as test_typed_values_use_postgres_casts_and_existing_driver_codecs,
    test_null_missing_and_empty_elements_stay_null as test_null_missing_and_empty_elements_stay_null,
    test_alias_dependencies_and_correlated_subquery_keep_values as test_alias_dependencies_and_correlated_subquery_keep_values,
    test_where_order_group_and_distinct_count_use_extraction as test_where_order_group_and_distinct_count_use_extraction,
    test_bad_xml_and_bad_cast_remain_database_errors as test_bad_xml_and_bad_cast_remain_database_errors,
)
from tests.native_formulas.tree_execution import TreeExecution
from tests.object_tree.test_phase4_options import tree_database


@pytest.fixture(scope='module')
def db(request):
    executor = request.getfixturevalue('execution_db')
    config = source()
    config.source['db'].packages().package('app', sqlschema=executor.model.table('app.item').sqlschema)
    tree = tree_database(config)
    try:
        yield TreeExecution(tree, executor, package='app')
        assert not tree._connections
    finally:
        tree.closeConnection()
