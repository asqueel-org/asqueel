"""One corpus, identical requests and fixture data for GenroPy and Asqueel.

Rows below are independent expectations, not outputs copied from either engine.
Cases sourced from existing tests are identified; edge probes are explicit.
"""
from decimal import Decimal

FIELDS = [('id','L'),('amount','N'),('unit_price','N'),('quantity','L'),
          ('title','T'),('year','L'),('customer_id','L'),('città','T'),('odd name','T')]
ROWS = [(1,10,10,2,'Alpha',2005,1,'Roma','one'),
        (2,20,20,25,"O'Reilly",2006,2,'Milano','two'),
        (3,None,None,3,'$unit_price',2005,1,'Torino','three'),
        (4,0,0,0,r'\$unit_price',2007,None,'Napoli','four')]
CUSTOMERS = [(1,'First'),(2,'Second')]
CASES = []


def add(name, columns='$id', where=None, params=None, expected=None,
        dialects=('sqlite','postgresql'), origin='edge probe', **options):
    CASES.append(dict(name=name, columns=columns, where=where, params=params or {},
                      expected=expected, dialects=dialects, origin=origin,
                      options={'order_by':'$id', **options}))


add('physical', '$id,$title', expected=[[r[0],r[4]] for r in ROWS],
    origin='legacy TestPhysicalColumns; fixture adapted')
add('sqlparams_year', '$title', '$year=:y', {'y':2005}, [['Alpha'],['$unit_price']],
    origin='legacy h_query_surface_test.test_test_method; exact clauses, fixture adapted')
add('case', 'CASE WHEN $amount >= :threshold THEN 1 ELSE 0 END AS category',
    params={'threshold':Decimal('15')}, expected=[[0],[1],[0],[0]],
    origin='shared minimal SELECT probe, split to isolate CASE')
add('coalesce', 'COALESCE($amount,0) AS amount', expected=[[10],[20],[0],[0]],
    origin='shared minimal SELECT probe')
add('cast', 'CAST($id AS text) AS id_text', expected=[['1'],['2'],['3'],['4']],
    origin='Asqueel test_cast_as_is_not_projection_alias; exact projection')
add('alias_lower', '$id as code', expected=[[1],[2],[3],[4]])
add('alias_mixed', '$id As code', expected=[[1],[2],[3],[4]])
add('expression_no_alias', '$amount * 2', expected=[[20],[40],[None],[0]],
    origin='legacy automatic expression alias vs Asqueel explicit-AS requirement')
add('duplicate_alias', '$id AS value,$quantity AS value', expected=None,
    origin='Asqueel duplicate-alias guard; no universal expected result')
add('literal_comma', "'a,b' AS value", expected=[['a,b']]*4)
add('literal_as', "' AS ' AS value", expected=[[' AS ']]*4)
add('literal_field', "'$id' AS value", expected=[['$id']]*4)
add('literal_unknown_field', "'$missing' AS value", expected=[['$missing']]*4)
add('literal_relation', "'@customer_id.name' AS value", expected=[['@customer_id.name']]*4)
add('literal_unknown_relation', "'@missing.name' AS value", expected=[['@missing.name']]*4)
add('literal_param', "':id' AS value", expected=[[':id']]*4)
add('literal_param_and_binding', "':id' AS value", '$id=:id', {'id':1}, [[':id']])
add('literal_colon_escape', r"'\:id' AS value", expected=[[r'\:id']]*4,
    origin='legacy execute escaped-colon convention; SQL-literal expectation shown separately')
add('literal_dollars', "'$$' AS value", expected=[['$$']]*4)
add('literal_quotes', "'O''Reilly $id' AS value", expected=[["O'Reilly $id"]]*4)
add('literal_percent', "'10%' AS value", expected=[['10%']]*4)
add('like_percent', '$id', "$title LIKE 'Al%'", expected=[[1]])
add('bound_quote', '$id', '$title=:title', {'title':"O'Reilly"}, [[2]])
add('bound_literal_field', '$id', '$title=:title', {'title':'$unit_price'}, [[3]],
    origin='overlaps intentional legacy embedFieldPars; literal-value oracle only')
add('bound_escaped_field', '$id', '$title=:title', {'title':r'\$unit_price'}, [[4]],
    origin='legacy execute escaped-prefix convention; literal-value oracle only')
add('embed_column_gt', '$id', '$quantity > :threshold', {'threshold':'$unit_price'}, [[2]],
    origin='legacy TestEmbedFieldPars.test_column_param_pg/sqlite; same predicate, explicit id instead of count')
add('embed_column_le', '$id', '$quantity <= :threshold', {'threshold':'$unit_price'}, [[1],[4]],
    origin='legacy TestEmbedFieldPars.test_column_param_pg/sqlite; same predicate, explicit id instead of count')
add('embed_relation', '$id', '$customer_id = :target', {'target':'@customer_id.id'}, [[1],[2],[3]],
    origin='legacy TestEmbedFieldPars relation convention; fixture adapted')
add('line_comment', '$id', '$id=:id -- $missing :unused @missing.name\n', {'id':1}, [[1]])
add('block_comment', '$id', '$id=:id /* $missing :unused @missing.name */', {'id':1}, [[1]])
add('comment_known_field', '$id', '$id=:id /* $id */', {'id':1}, [[1]])
add('comment_parameter', '$id', '$id=:id /* :unused */', {'id':1}, [[1]])
add('comment_no_newline', '$id', '$id=:id -- comment', {'id':1}, [[1]])
add('comment_nested', '$id', '$id=:id /* first /* nested :unused */ end */', {'id':1}, [[1]],
    dialects=('postgresql',))
add('macro_in_literal', "'#IN_RANGE($id,:lo,:hi)' AS value", expected=[['#IN_RANGE($id,:lo,:hi)']]*4)
add('in_range', '$id', '#IN_RANGE($amount,:lo,:hi)', {'lo':0,'hi':15}, [[1],[4]],
    origin='legacy TestExpandInRange / Asqueel test_query_macros; fixture adapted')
add('relation', '$id,@customer_id.name AS customer', expected=[[1,'First'],[2,'Second'],[3,'First'],[4,None]],
    origin='ordinary existing relation, no modification of relation algorithms')
add('relation_repeated', '@customer_id.name AS customer', '@customer_id.name=:name',
    {'name':'First'}, [['First'],['First']], order_by='@customer_id.name,$id')
add('repeated_bind', '$id', '$id=:id OR $quantity=:id', {'id':2}, [[1],[2]])
add('prefix_params', '$id', '$id=:id OR $id=:id2', {'id':1,'id2':2}, [[1],[2]])
add('null_binding', '$id', '$amount >= :value OR :value IS NULL', {'value':None}, [[1],[2],[3],[4]])
add('numeric_binding', '$id', '$amount >= :value', {'value':Decimal('15')}, [[2]])
add('in_list', '$id', '$id IN :ids', {'ids':[1,3]}, [[1],[3]])
add('not_in_list', '$id', '$id NOT IN :ids', {'ids':[1,3]}, [[2],[4]])
add('in_empty', '$id', '$id IN :ids', {'ids':[]}, [])
add('not_in_empty_null', '$id', '$amount NOT IN :ids', {'ids':[]}, [[1],[2],[3],[4]])
add('collection_collision', '$id', '$id IN :ids AND $id <> :ids0', {'ids':[1,2],'ids0':3}, [[1],[2]])
add('unused_param', '$id', '$id=:id', {'id':1,'unused':99}, [[1]])
add('missing_param', '$id', '$id=:missing', expected=None)
add('unicode_field', '$città AS city', expected=[[r[7]] for r in ROWS])
add('quoted_logical_field', '$"odd name" AS label', expected=[[r[8]] for r in ROWS])
add('quoted_alias', '$id AS "display name"', expected=[[1],[2],[3],[4]])
add('escaped_alias', '$id AS "a""b"', expected=[[1],[2],[3],[4]],
    origin='Asqueel quoted alias test')
add('unicode_param', '$id', '$id=:codicè', {'codicè':1}, [[1]])
add('cast_colon', '$id::text AS id_text', '$id=:id::integer', {'id':1}, [['1']], dialects=('postgresql',))
add('dollar_quote', '$$:id $missing$$ AS value', expected=[[':id $missing']]*4, dialects=('postgresql',))
add('tagged_dollar_quote', '$tag$:id $missing$tag$ AS value', expected=[[':id $missing']]*4, dialects=('postgresql',))
add('escape_string', r"E'a\'b :fake' AS value", expected=[["a'b :fake"]]*4, dialects=('postgresql',),
    origin='Asqueel test_escape_string_and_quoted_alias; alias simplified for isolation')
add('adjacent_field_operator', '$amount+$id AS value', expected=[[11],[22],[None],[4]])
add('literal_regexp', "'REGEXP' AS value", expected=[['REGEXP']]*4)
add('sqlite_literal_ilike', "'ILIKE' AS value", expected=[['ILIKE']]*4, dialects=('sqlite',))
add('literal_semicolon', "'; SELECT' AS value", expected=[['; SELECT']]*4)
add('unknown_field', '$missing', expected=None)
add('unclosed_string', "'unclosed AS value", expected=None)
add('unclosed_comment', '$id', '$id=1 /* open', expected=None)
add('unclosed_dollar', '$tag$unclosed AS value', expected=None, dialects=('postgresql',))
# No execution for a multi-statement boundary probe, regardless of compiler output.
add('statement_separator', '$id', '$id=1; SELECT 2', expected=None, execute=False)
# Counterparts to the literal-preservation cases: the legacy adaptations also
# implement actual operator and escaping conventions that cannot simply vanish.
add('regexp_operator', '$id', '$title REGEXP :pattern', {'pattern':'^Al'}, [[1]],
    dialects=('postgresql',), origin='legacy PostgreSQL prepareSqlText REGEXP -> ~* convention')
add('sqlite_ilike_operator', '$id', '$title ILIKE :pattern', {'pattern':'al%'}, [[1]],
    dialects=('sqlite',), origin='legacy SQLite prepareSqlText ILIKE -> LIKE convention')
add('legacy_percent_escape', "'10%%' AS value", expected=[['10%']]*4,
    dialects=('postgresql',), origin='legacy psycopg percent escaping convention, not raw SQL literal oracle')

add('collection_current_collision', '$id', '$id IN :ids AND $id <> :ids_0',
    {'ids':[1,2],'ids_0':3}, [[1],[2]],
    origin='Asqueel collection-name collision; identical request on legacy')
