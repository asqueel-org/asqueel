"""Ported legacy formula tests on native package models and real databases.

Reference: GenroPy fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea,
gnrpy/tests/sql/test_compiler_coverage.py. Original assertions retained.
Only the relation output alias in one projection is made explicit.
Subquery-dependent cases remain listed as deferred in legacy-manifest.json.
"""
import pytest


class TestAliasColumn:

    def test_alias_matches_source_pg(self, db_pg):
        """aliasColumn value matches direct query on related table."""
        row = db_pg.table('invc.invoice').query(
            columns='$customer_id, $customer_name', limit=1
        ).fetch()[0]
        direct = db_pg.table('invc.customer').query(
            columns='$account_name',
            where='$id = :cid', cid=row['customer_id']
        ).fetch()[0]
        assert row['customer_name'] == direct['account_name']

    def test_alias_matches_source_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.invoice').query(
            columns='$customer_id, $customer_name', limit=1
        ).fetch()[0]
        direct = db_sqlite.table('invc.customer').query(
            columns='$account_name',
            where='$id = :cid', cid=row['customer_id']
        ).fetch()[0]
        assert row['customer_name'] == direct['account_name']

    def test_alias_two_levels_pg(self, db_pg):
        """invoice_row.customer_name traverses 2 joins."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $customer_name', limit=5
        ).fetch()
        assert len(rows) == 5
        assert all(
            isinstance(r['customer_name'], str) for r in rows
        )

    def test_alias_two_levels_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $customer_name', limit=5
        ).fetch()
        assert len(rows) == 5
        assert all(
            isinstance(r['customer_name'], str) for r in rows
        )

    def test_alias_three_levels_pg(self, db_pg):
        """invoice_row.customer_state traverses 3 joins."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $customer_state', limit=5
        ).fetch()
        assert len(rows) == 5
        assert all(r['customer_state'] for r in rows)

    def test_alias_three_levels_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $customer_state', limit=5
        ).fetch()
        assert len(rows) == 5
        assert all(r['customer_state'] for r in rows)

    def test_deep_alias_customer_region_pg(self, db_pg):
        """invoice_row.customer_region: 4+ joins deep."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $customer_region', limit=5
        ).fetch()
        assert len(rows) == 5
        assert all(r['customer_region'] for r in rows)

    def test_deep_alias_customer_region_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $customer_region', limit=5
        ).fetch()
        assert len(rows) == 5
        assert all(r['customer_region'] for r in rows)

    def test_region_name_cross_validate_pg(self, db_pg):
        """customer.region_name matches direct region query."""
        row = db_pg.table('invc.customer').query(
            columns='$state, $region_name',
            where='$region_name IS NOT NULL', limit=1
        ).fetch()[0]
        state_row = db_pg.table('invc.state').query(
            columns='$region_code',
            where='$code = :s', s=row['state']
        ).fetch()[0]
        region_row = db_pg.table('invc.region').query(
            columns='$name',
            where='$code = :rc', rc=state_row['region_code']
        ).fetch()[0]
        assert row['region_name'] == region_row['name']

    def test_region_name_cross_validate_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.customer').query(
            columns='$state, $region_name',
            where='$region_name IS NOT NULL', limit=1
        ).fetch()[0]
        state_row = db_sqlite.table('invc.state').query(
            columns='$region_code',
            where='$code = :s', s=row['state']
        ).fetch()[0]
        region_row = db_sqlite.table('invc.region').query(
            columns='$name',
            where='$code = :rc', rc=state_row['region_code']
        ).fetch()[0]
        assert row['region_name'] == region_row['name']

class TestFormulaSql:

    def test_line_total_pg(self, db_pg):
        """line_total = quantity * unit_price."""
        row = db_pg.table('invc.invoice_row').query(
            columns='$quantity, $unit_price, $line_total',
            where='$quantity IS NOT NULL AND $unit_price IS NOT NULL',
            limit=1
        ).fetch()[0]
        expected = float(row['quantity']) * float(row['unit_price'])
        assert abs(float(row['line_total']) - expected) < 0.01

    def test_line_total_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.invoice_row').query(
            columns='$quantity, $unit_price, $line_total',
            where='$quantity IS NOT NULL AND $unit_price IS NOT NULL',
            limit=1
        ).fetch()[0]
        expected = float(row['quantity']) * float(row['unit_price'])
        assert abs(float(row['line_total']) - expected) < 0.01

    def test_concatenation_full_address_pg(self, db_pg):
        """full_address = street_address || ', ' || suburb."""
        row = db_pg.table('invc.customer').query(
            columns='$street_address, $suburb, $full_address',
            where=('$street_address IS NOT NULL'
                   ' AND $suburb IS NOT NULL'),
            limit=1
        ).fetch()[0]
        expected = f"{row['street_address']}, {row['suburb']}"
        assert row['full_address'] == expected

    def test_concatenation_full_address_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.customer').query(
            columns='$street_address, $suburb, $full_address',
            where=('$street_address IS NOT NULL'
                   ' AND $suburb IS NOT NULL'),
            limit=1
        ).fetch()[0]
        expected = f"{row['street_address']}, {row['suburb']}"
        assert row['full_address'] == expected

    def test_code_and_desc_pg(self, db_pg):
        """product.code_and_desc = code || ' - ' || description."""
        row = db_pg.table('invc.product').query(
            columns='$code, $description, $code_and_desc',
            where='$code IS NOT NULL AND $description IS NOT NULL',
            limit=1
        ).fetch()[0]
        expected = f"{row['code']} - {row['description']}"
        assert row['code_and_desc'] == expected

    def test_code_and_desc_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.product').query(
            columns='$code, $description, $code_and_desc',
            where='$code IS NOT NULL AND $description IS NOT NULL',
            limit=1
        ).fetch()[0]
        expected = f"{row['code']} - {row['description']}"
        assert row['code_and_desc'] == expected

class TestCaseWhen:

    def test_value_category_pg(self, db_pg):
        """invoice.value_category returns valid categories."""
        rows = db_pg.table('invc.invoice').query(
            columns='$total, $value_category', limit=20
        ).fetch()
        valid = {'High', 'Medium', 'Low'}
        for r in rows:
            assert r['value_category'] in valid
            total = float(r['total'] or 0)
            if total > 1000:
                assert r['value_category'] == 'High'
            elif total > 100:
                assert r['value_category'] == 'Medium'
            else:
                assert r['value_category'] == 'Low'

    def test_value_category_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$total, $value_category', limit=20
        ).fetch()
        valid = {'High', 'Medium', 'Low'}
        for r in rows:
            assert r['value_category'] in valid

    def test_size_category_pg(self, db_pg):
        """invoice_row.size_category uses CASE with IN."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$quantity, $size_category', limit=20
        ).fetch()
        valid = {'Small', 'Medium', 'Large'}
        for r in rows:
            assert r['size_category'] in valid

    def test_size_category_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$quantity, $size_category', limit=20
        ).fetch()
        valid = {'Small', 'Medium', 'Large'}
        for r in rows:
            assert r['size_category'] in valid

    def test_price_range_pg(self, db_pg):
        """product.price_range categorization."""
        rows = db_pg.table('invc.product').query(
            columns='$unit_price, $price_range', limit=20
        ).fetch()
        valid = {'Premium', 'Mid', 'Budget'}
        for r in rows:
            assert r['price_range'] in valid

    def test_price_range_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.product').query(
            columns='$unit_price, $price_range', limit=20
        ).fetch()
        valid = {'Premium', 'Mid', 'Budget'}
        for r in rows:
            assert r['price_range'] in valid

    def test_nested_case_invoice_status_pg(self, db_pg):
        """invoice.invoice_status nested CASE."""
        rows = db_pg.table('invc.invoice').query(
            columns='$total, $gross_total, $invoice_status', limit=20
        ).fetch()
        valid = {'Draft', 'Empty', 'Large', 'Medium', 'Small'}
        for r in rows:
            assert r['invoice_status'] in valid

    def test_nested_case_invoice_status_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$total, $gross_total, $invoice_status', limit=20
        ).fetch()
        valid = {'Draft', 'Empty', 'Large', 'Medium', 'Small'}
        for r in rows:
            assert r['invoice_status'] in valid

    def test_product_note_with_relation_pg(self, db_pg):
        """invoice_row.product_note references @product_id."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $product_note', limit=10
        ).fetch()
        valid = {'Premium', 'Standard'}
        for r in rows:
            assert r['product_note'] in valid

    def test_product_note_with_relation_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $product_note', limit=10
        ).fetch()
        valid = {'Premium', 'Standard'}
        for r in rows:
            assert r['product_note'] in valid

    def test_pricing_analysis_pg(self, db_pg):
        """invoice_row.pricing_analysis: CASE on effective_price."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $pricing_analysis', limit=20
        ).fetch()
        valid = {
            'No price', 'Above list', 'Discounted', 'At list price'
        }
        for r in rows:
            assert r['pricing_analysis'] in valid

    def test_pricing_analysis_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $pricing_analysis', limit=20
        ).fetch()
        valid = {
            'No price', 'Above list', 'Discounted', 'At list price'
        }
        for r in rows:
            assert r['pricing_analysis'] in valid

class TestCoalesce:

    def test_display_total_pg(self, db_pg):
        """display_total = COALESCE(gross_total, total, 0)."""
        rows = db_pg.table('invc.invoice').query(
            columns='$total, $gross_total, $display_total', limit=10
        ).fetch()
        for r in rows:
            assert r['display_total'] is not None

    def test_display_total_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$total, $gross_total, $display_total', limit=10
        ).fetch()
        for r in rows:
            assert r['display_total'] is not None

    def test_effective_price_pg(self, db_pg):
        """effective_price = COALESCE(unit_price, product.unit_price)."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$unit_price, $effective_price', limit=10
        ).fetch()
        for r in rows:
            if r['unit_price'] is not None:
                assert (float(r['effective_price'])
                        == float(r['unit_price']))

    def test_effective_price_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$unit_price, $effective_price', limit=10
        ).fetch()
        for r in rows:
            if r['unit_price'] is not None:
                assert (float(r['effective_price'])
                        == float(r['unit_price']))

    def test_display_name_pg(self, db_pg):
        """display_name never returns None."""
        rows = db_pg.table('invc.customer').query(
            columns='$display_name', limit=10
        ).fetch()
        assert all(r['display_name'] for r in rows)

    def test_display_name_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(
            columns='$display_name', limit=10
        ).fetch()
        assert all(r['display_name'] for r in rows)

class TestReplace:

    def test_description_clean_pg(self, db_pg):
        """REPLACE($description, ' ', '-')."""
        rows = db_pg.table('invc.product').query(
            columns='$description, $description_clean',
            where='$description IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            expected = r['description'].replace(' ', '-')
            assert r['description_clean'] == expected

    def test_description_clean_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.product').query(
            columns='$description, $description_clean',
            where='$description IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            expected = r['description'].replace(' ', '-')
            assert r['description_clean'] == expected

class TestUpperTrim:

    def test_note_type_clean_pg(self, db_pg):
        rows = db_pg.table('invc.invoice_note').query(
            columns='$note_type, $note_type_clean', limit=10
        ).fetch()
        for r in rows:
            if r['note_type']:
                assert r['note_type_clean'] == (
                    r['note_type'].strip().upper()
                )

    def test_note_type_clean_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_note').query(
            columns='$note_type, $note_type_clean', limit=10
        ).fetch()
        for r in rows:
            if r['note_type']:
                assert r['note_type_clean'] == (
                    r['note_type'].strip().upper()
                )

class TestLikeFormula:

    def test_is_warning_pg(self, db_pg):
        """is_warning: note_type LIKE 'WARN%'."""
        rows = db_pg.table('invc.invoice_note').query(
            columns='$note_type, $is_warning', limit=20
        ).fetch()
        for r in rows:
            if r['note_type'] and r['note_type'].startswith('WARN'):
                assert r['is_warning'] is True

    def test_is_warning_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_note').query(
            columns='$note_type, $is_warning', limit=20
        ).fetch()
        for r in rows:
            if r['note_type'] and r['note_type'].startswith('WARN'):
                assert bool(r['is_warning'])

    def test_number_series_pg(self, db_pg):
        """CASE WHEN $inv_number LIKE 'A%' => Series A etc."""
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $number_series', limit=20
        ).fetch()
        valid = {'Series A', 'Series B', 'Other'}
        for r in rows:
            assert r['number_series'] in valid

    def test_number_series_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$inv_number, $number_series', limit=20
        ).fetch()
        valid = {'Series A', 'Series B', 'Other'}
        for r in rows:
            assert r['number_series'] in valid

class TestMathFunctions:

    def test_price_rounded_pg(self, db_pg):
        """ROUND(unit_price, 0)."""
        rows = db_pg.table('invc.product').query(
            columns='$unit_price, $price_rounded',
            where='$unit_price IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            diff = abs(
                float(r['price_rounded'])
                - round(float(r['unit_price']))
            )
            assert diff < 1.0

    def test_price_rounded_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.product').query(
            columns='$unit_price, $price_rounded',
            where='$unit_price IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            diff = abs(
                float(r['price_rounded'])
                - round(float(r['unit_price']))
            )
            assert diff < 1.0

    def test_rounded_total_pg(self, db_pg):
        rows = db_pg.table('invc.invoice_row').query(
            columns='$line_total, $rounded_total',
            where='$line_total IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert r['rounded_total'] is not None

    def test_rounded_total_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$line_total, $rounded_total',
            where='$line_total IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert r['rounded_total'] is not None

    def test_abs_discount_pg(self, db_pg):
        """ABS(unit_price - product.unit_price) >= 0."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $abs_discount',
            where='$abs_discount IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert float(r['abs_discount']) >= 0

    def test_abs_discount_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $abs_discount',
            where='$abs_discount IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert float(r['abs_discount']) >= 0

class TestFormulaChain:

    def test_line_vat_pg(self, db_pg):
        """line_vat = line_total * vat_rate."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$line_total, $vat_rate, $line_vat',
            where=('$line_total IS NOT NULL'
                   ' AND $vat_rate IS NOT NULL'), limit=5
        ).fetch()
        for r in rows:
            expected = float(r['line_total']) * float(r['vat_rate'])
            assert abs(float(r['line_vat']) - expected) < 0.01

    def test_line_vat_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$line_total, $vat_rate, $line_vat',
            where=('$line_total IS NOT NULL'
                   ' AND $vat_rate IS NOT NULL'), limit=5
        ).fetch()
        for r in rows:
            expected = float(r['line_total']) * float(r['vat_rate'])
            assert abs(float(r['line_vat']) - expected) < 0.01

    def test_line_gross_pg(self, db_pg):
        """line_gross = line_total + line_vat."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$line_total, $line_vat, $line_gross',
            where=('$line_total IS NOT NULL'
                   ' AND $line_vat IS NOT NULL'), limit=5
        ).fetch()
        for r in rows:
            expected = (float(r['line_total'])
                        + float(r['line_vat']))
            assert abs(float(r['line_gross']) - expected) < 0.01

    def test_line_gross_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$line_total, $line_vat, $line_gross',
            where=('$line_total IS NOT NULL'
                   ' AND $line_vat IS NOT NULL'), limit=5
        ).fetch()
        for r in rows:
            expected = (float(r['line_total'])
                        + float(r['line_vat']))
            assert abs(float(r['line_gross']) - expected) < 0.01

class TestVarParameters:

    def test_status_label_pg(self, db_pg):
        """var_ params provide default values in CASE."""
        rows = db_pg.table('invc.invoice').query(
            columns='$total, $status_label', limit=20
        ).fetch()
        valid = {
            'Premium Invoice', 'Standard Invoice', 'Basic Invoice'
        }
        for r in rows:
            assert r['status_label'] in valid

    def test_status_label_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$total, $status_label', limit=20
        ).fetch()
        valid = {
            'Premium Invoice', 'Standard Invoice', 'Basic Invoice'
        }
        for r in rows:
            assert r['status_label'] in valid

class TestVarInList:

    def test_is_exempt_vat_pg(self, db_pg):
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $is_exempt_vat',
            limit=20
        ).fetch()
        assert len(rows) == 20
        for r in rows:
            assert r['is_exempt_vat'] in (True, False)

    def test_is_exempt_vat_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $is_exempt_vat',
            limit=20
        ).fetch()
        assert len(rows) == 20
        for r in rows:
            assert r['is_exempt_vat'] in (0, 1, True, False)

    def test_is_exempt_vat_cross_validate_pg(self, db_pg):
        """Verify exempt matches FRE/INP vat_type_code."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $is_exempt_vat, @product_id.vat_type_code AS _product_id_vat_type_code',
            limit=50
        ).fetch()
        for r in rows:
            vat_code = r['_product_id_vat_type_code']
            if vat_code in ('FRE', 'INP'):
                assert r['is_exempt_vat'] is True
            else:
                assert r['is_exempt_vat'] is False


class TestConcatFunction:

    def test_concat_code_desc_pg(self, db_pg):
        rows = db_pg.table('invc.product').query(
            columns='$code, $description, $concat_code_desc',
            where='$code IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert r['code'] in r['concat_code_desc']
            assert r['description'] in r['concat_code_desc']

    def test_concat_code_desc_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.product').query(
            columns='$code, $description, $concat_code_desc',
            where='$code IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert r['code'] in r['concat_code_desc']
            assert r['description'] in r['concat_code_desc']

    def test_contact_info_pg(self, db_pg):
        """CONCAT with COALESCE inside."""
        rows = db_pg.table('invc.customer').query(
            columns='$email, $phone, $contact_info', limit=5
        ).fetch()
        for r in rows:
            assert '|' in r['contact_info']

    def test_contact_info_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(
            columns='$email, $phone, $contact_info', limit=5
        ).fetch()
        for r in rows:
            assert '|' in r['contact_info']


class TestCast:

    def test_price_as_int_text_pg(self, db_pg):
        """Nested CAST: int then text."""
        rows = db_pg.table('invc.product').query(
            columns='$unit_price, $price_as_int_text',
            where='$unit_price IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert isinstance(r['price_as_int_text'], str)
            assert r['price_as_int_text'].lstrip('-').isdigit()

    def test_price_as_int_text_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.product').query(
            columns='$unit_price, $price_as_int_text',
            where='$unit_price IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert isinstance(r['price_as_int_text'], str)
            assert r['price_as_int_text'].lstrip('-').isdigit()

    def test_matches_list_price_pg(self, db_pg):
        """CAST(comparison AS boolean)."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$unit_price, $matches_list_price', limit=10
        ).fetch()
        for r in rows:
            assert r['matches_list_price'] in (True, False, None)

    def test_matches_list_price_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$unit_price, $matches_list_price', limit=10
        ).fetch()
        for r in rows:
            assert r['matches_list_price'] in (True, False, None)


class TestGreatest:

    def test_price_floor_pg(self, db_pg):
        """GREATEST(unit_price, 10): always >= 10."""
        rows = db_pg.table('invc.product').query(
            columns='$unit_price, $price_floor',
            where='$unit_price IS NOT NULL', limit=10
        ).fetch()
        for r in rows:
            assert float(r['price_floor']) >= 10

    def test_price_floor_sqlite(self, db_sqlite):
        """GREATEST not available on SQLite."""
        pytest.skip('GREATEST function not supported on SQLite')


class TestWindowFunctions:

    def test_prev_quantity_pg(self, db_pg):
        """LAG returns NULL for first row, integer for others."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$invoice_id, $prev_quantity, $_row_count',
            order_by='$invoice_id, $_row_count', limit=20
        ).fetch()
        assert len(rows) > 0
        has_null = any(r['prev_quantity'] is None for r in rows)
        has_value = any(r['prev_quantity'] is not None for r in rows)
        assert has_null or has_value

    def test_prev_quantity_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$invoice_id, $prev_quantity, $_row_count',
            order_by='$invoice_id, $_row_count', limit=20
        ).fetch()
        assert len(rows) > 0


class TestBooleanFormulas:

    def test_is_expensive_pg(self, db_pg):
        """is_expensive = line_total > 1000."""
        rows = db_pg.table('invc.invoice_row').query(
            columns='$line_total, $is_expensive',
            where='$line_total IS NOT NULL', limit=20
        ).fetch()
        for r in rows:
            lt = float(r['line_total'])
            if lt > 1000:
                assert r['is_expensive'] is True

    def test_is_expensive_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$line_total, $is_expensive',
            where='$line_total IS NOT NULL', limit=20
        ).fetch()
        for r in rows:
            lt = float(r['line_total'])
            if lt > 1000:
                assert bool(r['is_expensive'])

    def test_needs_review_pg(self, db_pg):
        """needs_review = is_expensive OR (qty>50 AND price<1)."""
        rows = db_pg.table('invc.invoice_row').query(
            columns=(
                '$line_total, $quantity, $unit_price, $needs_review'
            ),
            where='$needs_review = TRUE', limit=5
        ).fetch()
        for r in rows:
            lt = float(r['line_total'] or 0)
            q = int(r['quantity'] or 0)
            p = float(r['unit_price'] or 0)
            assert lt > 1000 or (q > 50 and p < 1)

    def test_needs_review_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns=(
                '$line_total, $quantity, $unit_price, $needs_review'
            ),
            where='$needs_review = TRUE', limit=5
        ).fetch()
        for r in rows:
            lt = float(r['line_total'] or 0)
            q = int(r['quantity'] or 0)
            p = float(r['unit_price'] or 0)
            assert lt > 1000 or (q > 50 and p < 1)


class TestPostgresOnly:

    def test_code_normalized_pg(self, db_pg):
        """regexp_replace: remove non-alphanumeric, lowercase."""
        rows = db_pg.table('invc.product').query(
            columns='$code, $code_normalized',
            where='$code IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert r['code_normalized'] is not None
            assert r['code_normalized'] == (
                r['code_normalized'].lower()
            )

    def test_code_clean_pg(self, db_pg):
        """translate: replace chars."""
        rows = db_pg.table('invc.product').query(
            columns='$code, $code_clean',
            where='$code IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert r['code_clean'] is not None

    def test_code_prefix_std_pg(self, db_pg):
        """substring($code FROM 1 FOR 3)."""
        rows = db_pg.table('invc.product').query(
            columns='$code, $code_prefix_std',
            where='$code IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert r['code_prefix_std'] == r['code'][:3]

    def test_anno_pg(self, db_pg):
        """EXTRACT(YEAR FROM $date)."""
        rows = db_pg.table('invc.invoice').query(
            columns='$date, $anno', limit=5
        ).fetch()
        for r in rows:
            year_val = int(float(r['anno']))
            assert 2000 <= year_val <= 2030

    def test_periodo_pg(self, db_pg):
        """TO_CHAR($date, 'YYYY-MM')."""
        rows = db_pg.table('invc.invoice').query(
            columns='$date, $periodo', limit=5
        ).fetch()
        for r in rows:
            assert len(r['periodo']) == 7
            assert '-' in r['periodo']

    def test_days_since_invoice_pg(self, db_pg):
        """date_part('day', now() - $date)."""
        rows = db_pg.table('invc.invoice').query(
            columns='$date, $days_since_invoice', limit=5
        ).fetch()
        for r in rows:
            assert float(r['days_since_invoice']) >= 0

    def test_invoice_month_pg(self, db_pg):
        """date_trunc('month', $date)."""
        rows = db_pg.table('invc.invoice').query(
            columns='$date, $invoice_month', limit=5
        ).fetch()
        for r in rows:
            assert r['invoice_month'] is not None

    def test_created_date_pg(self, db_pg):
        """date_trunc('day', $__ins_ts)."""
        rows = db_pg.table('invc.invoice_note').query(
            columns='$note_text, $created_date', limit=5
        ).fetch()
        for r in rows:
            assert r['created_date'] is not None

    def test_week_start_pg(self, db_pg):
        """INTERVAL + MOD + EXTRACT(DOW)."""
        rows = db_pg.table('invc.invoice').query(
            columns='$date, $week_start', limit=5
        ).fetch()
        for r in rows:
            assert r['week_start'] is not None

    def test_postcode_padded_pg(self, db_pg):
        """LPAD($postcode, 5, '0')."""
        rows = db_pg.table('invc.customer').query(
            columns='$postcode, $postcode_padded',
            where='$postcode IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert len(r['postcode_padded']) == 5

    def test_account_code_pg(self, db_pg):
        """LPAD(CAST($id AS TEXT), 8, '0')."""
        rows = db_pg.table('invc.customer').query(
            columns='$id, $account_code', limit=5
        ).fetch()
        for r in rows:
            assert len(r['account_code']) == 8


class TestWhereOrderBy:

    def test_where_alias_pg(self, db_pg):
        rows = db_pg.table('invc.customer').query(
            columns='$account_name, $state_name',
            where='$state_name IS NOT NULL',
            order_by='$state_name', limit=5
        ).fetch()
        assert len(rows) == 5
        names = [r['state_name'] for r in rows]
        assert names == sorted(names)

    def test_where_alias_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(
            columns='$account_name, $state_name',
            where='$state_name IS NOT NULL',
            order_by='$state_name', limit=5
        ).fetch()
        assert len(rows) == 5
        names = [r['state_name'] for r in rows]
        assert names == sorted(names)

    def test_order_by_formula_pg(self, db_pg):
        rows = db_pg.table('invc.invoice_row').query(
            columns='$id, $line_total',
            where='$line_total IS NOT NULL',
            order_by='$line_total DESC', limit=5
        ).fetch()
        vals = [float(r['line_total']) for r in rows]
        assert vals == sorted(vals, reverse=True)

    def test_order_by_formula_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_row').query(
            columns='$id, $line_total',
            where='$line_total IS NOT NULL',
            order_by='$line_total DESC', limit=5
        ).fetch()
        vals = [float(r['line_total']) for r in rows]
        assert vals == sorted(vals, reverse=True)


class TestIntervalArithmetic:

    def test_due_date_pg(self, db_pg):
        from datetime import date, datetime
        rows = db_pg.table('invc.invoice').query(
            columns='$date, $due_date',
            limit=10
        ).fetch()
        assert len(rows) == 10
        for r in rows:
            if r['date'] and r['due_date']:
                inv_date = r['date']
                due = r['due_date']
                if isinstance(inv_date, datetime):
                    inv_date = inv_date.date()
                if isinstance(due, datetime):
                    due = due.date()
                if isinstance(inv_date, date) and isinstance(due, date):
                    assert (due - inv_date).days == 30

    @pytest.mark.skipif(True, reason='INTERVAL not supported on SQLite')
    def test_due_date_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$date, $due_date',
            limit=10
        ).fetch()
        assert len(rows) == 10


class TestCastDate:

    def test_created_same_day_pg(self, db_pg):
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $created_same_day',
            limit=10
        ).fetch()
        assert len(rows) == 10
        for r in rows:
            assert r['created_same_day'] in (True, False)

    def test_created_same_day_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$inv_number, $created_same_day',
            limit=10
        ).fetch()
        assert len(rows) == 10


class TestEnvWorkdate:

    def test_is_recent_pg(self, db_pg):
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $date, $is_recent',
            limit=20
        ).fetch()
        assert len(rows) == 20
        for r in rows:
            assert r['is_recent'] in (True, False)

    @pytest.mark.skipif(True, reason='INTERVAL not supported on SQLite')
    def test_is_recent_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$inv_number, $date, $is_recent',
            limit=20
        ).fetch()
        assert len(rows) == 20


class TestRtrim:

    def test_rtrim_pg(self, db_pg):
        rows = db_pg.table('invc.invoice_note').query(
            columns='$note_text, $note_text_rtrim',
            limit=10
        ).fetch()
        assert len(rows) == 10
        for r in rows:
            if r['note_text']:
                assert r['note_text_rtrim'] == r['note_text'].rstrip()

    def test_rtrim_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice_note').query(
            columns='$note_text, $note_text_rtrim',
            limit=10
        ).fetch()
        assert len(rows) == 10
        for r in rows:
            if r['note_text']:
                assert r['note_text_rtrim'] == r['note_text'].rstrip()
