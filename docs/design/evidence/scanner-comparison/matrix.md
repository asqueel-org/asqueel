# Matrice del confronto scanner/legacy

Corpus selezionato, non una misura della percentuale di compatibilità generale. Gli errori sono osservazioni: non vengono corretti per far passare la sonda.

SQL, kwargs, valori e tipi completi in [results.json](results.json).

| Caso | Dialetto | Legacy | Asqueel | Confronto |
| --- | --- | --- | --- | --- |
| `physical` | sqlite | esegue | esegue | stessi valori e colonne |
| `sqlparams_year` | sqlite | esegue | esegue | stessi valori e colonne |
| `case` | sqlite | esegue | esegue | stessi valori e colonne |
| `coalesce` | sqlite | esegue | esegue | stessi valori e colonne |
| `cast` | sqlite | esegue | esegue | stessi valori e colonne |
| `alias_lower` | sqlite | esegue | esegue | stessi valori e colonne |
| `alias_mixed` | sqlite | errore esecuzione: OperationalError | esegue | esegue solo Asqueel |
| `expression_no_alias` | sqlite | esegue | errore compilazione: ValueError | esegue solo legacy |
| `duplicate_alias` | sqlite | esegue | errore compilazione: ValueError | esegue solo legacy |
| `literal_comma` | sqlite | esegue | esegue | stessi valori e colonne |
| `literal_as` | sqlite | esegue | esegue | stessi valori e colonne |
| `literal_field` | sqlite | esegue | esegue | valori o colonne differenti |
| `literal_unknown_field` | sqlite | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `literal_relation` | sqlite | esegue | esegue | valori o colonne differenti |
| `literal_unknown_relation` | sqlite | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `literal_param` | sqlite | esegue | esegue | stessi valori e colonne |
| `literal_param_and_binding` | sqlite | esegue | esegue | stessi valori e colonne |
| `literal_colon_escape` | sqlite | esegue | esegue | valori o colonne differenti |
| `literal_dollars` | sqlite | esegue | esegue | valori o colonne differenti |
| `literal_quotes` | sqlite | esegue | esegue | valori o colonne differenti |
| `literal_percent` | sqlite | esegue | esegue | stessi valori e colonne |
| `like_percent` | sqlite | esegue | esegue | stessi valori e colonne |
| `bound_quote` | sqlite | esegue | esegue | stessi valori e colonne |
| `bound_literal_field` | sqlite | esegue | esegue | valori o colonne differenti |
| `bound_escaped_field` | sqlite | esegue | esegue | valori o colonne differenti |
| `embed_column_gt` | sqlite | esegue | esegue | valori o colonne differenti |
| `embed_column_le` | sqlite | esegue | esegue | valori o colonne differenti |
| `embed_relation` | sqlite | esegue | esegue | valori o colonne differenti |
| `line_comment` | sqlite | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `block_comment` | sqlite | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `comment_known_field` | sqlite | esegue | esegue | stessi valori e colonne |
| `comment_parameter` | sqlite | esegue | esegue | stessi valori e colonne |
| `comment_no_newline` | sqlite | errore esecuzione: OperationalError | esegue | esegue solo Asqueel |
| `macro_in_literal` | sqlite | esegue | esegue | valori o colonne differenti |
| `in_range` | sqlite | esegue | esegue | stessi valori e colonne |
| `relation` | sqlite | esegue | esegue | stessi valori e colonne |
| `relation_repeated` | sqlite | esegue | esegue | stessi valori e colonne |
| `repeated_bind` | sqlite | esegue | esegue | stessi valori e colonne |
| `prefix_params` | sqlite | esegue | esegue | stessi valori e colonne |
| `null_binding` | sqlite | esegue | esegue | stessi valori e colonne |
| `numeric_binding` | sqlite | esegue | esegue | stessi valori e colonne |
| `in_list` | sqlite | esegue | esegue | stessi valori e colonne |
| `not_in_list` | sqlite | esegue | esegue | stessi valori e colonne |
| `in_empty` | sqlite | esegue | esegue | stessi valori e colonne |
| `not_in_empty_null` | sqlite | esegue | esegue | stessi valori e colonne |
| `collection_collision` | sqlite | esegue | esegue | valori o colonne differenti |
| `unused_param` | sqlite | esegue | esegue | stessi valori e colonne |
| `missing_param` | sqlite | errore esecuzione: ProgrammingError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `unicode_field` | sqlite | errore esecuzione: ProgrammingError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `quoted_logical_field` | sqlite | errore esecuzione: OperationalError | esegue | esegue solo Asqueel |
| `quoted_alias` | sqlite | esegue | esegue | stessi valori e colonne |
| `escaped_alias` | sqlite | esegue | esegue | stessi valori e colonne |
| `unicode_param` | sqlite | esegue | errore compilazione: ValueError | esegue solo legacy |
| `adjacent_field_operator` | sqlite | esegue | esegue | stessi valori e colonne |
| `literal_regexp` | sqlite | esegue | esegue | stessi valori e colonne |
| `sqlite_literal_ilike` | sqlite | esegue | esegue | valori o colonne differenti |
| `literal_semicolon` | sqlite | esegue | esegue | stessi valori e colonne |
| `unknown_field` | sqlite | errore compilazione: GnrSqlMissingField | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `unclosed_string` | sqlite | errore compilazione: ValueError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `unclosed_comment` | sqlite | errore esecuzione: OperationalError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `statement_separator` | sqlite | compila; non eseguito | errore compilazione: UnsupportedFeatureError | solo compilazione, perimetro statement |
| `sqlite_ilike_operator` | sqlite | esegue | errore esecuzione: OperationalError | esegue solo legacy |
| `collection_current_collision` | sqlite | esegue | esegue | stessi valori e colonne |
| `physical` | postgresql | esegue | esegue | stessi valori e colonne |
| `sqlparams_year` | postgresql | esegue | esegue | stessi valori e colonne |
| `case` | postgresql | esegue | esegue | stessi valori e colonne |
| `coalesce` | postgresql | esegue | esegue | stessi valori e colonne |
| `cast` | postgresql | esegue | esegue | stessi valori e colonne |
| `alias_lower` | postgresql | esegue | esegue | stessi valori e colonne |
| `alias_mixed` | postgresql | errore esecuzione: SyntaxError | esegue | esegue solo Asqueel |
| `expression_no_alias` | postgresql | esegue | errore compilazione: ValueError | esegue solo legacy |
| `duplicate_alias` | postgresql | esegue | errore compilazione: ValueError | esegue solo legacy |
| `literal_comma` | postgresql | esegue | esegue | stessi valori e colonne |
| `literal_as` | postgresql | esegue | esegue | stessi valori e colonne |
| `literal_field` | postgresql | esegue | esegue | valori o colonne differenti |
| `literal_unknown_field` | postgresql | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `literal_relation` | postgresql | esegue | esegue | valori o colonne differenti |
| `literal_unknown_relation` | postgresql | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `literal_param` | postgresql | errore esecuzione: KeyError | esegue | esegue solo Asqueel |
| `literal_param_and_binding` | postgresql | esegue | esegue | valori o colonne differenti |
| `literal_colon_escape` | postgresql | esegue | esegue | valori o colonne differenti |
| `literal_dollars` | postgresql | esegue | esegue | valori o colonne differenti |
| `literal_quotes` | postgresql | esegue | esegue | valori o colonne differenti |
| `literal_percent` | postgresql | errore esecuzione: TypeError | esegue | esegue solo Asqueel |
| `like_percent` | postgresql | errore esecuzione: TypeError | esegue | esegue solo Asqueel |
| `bound_quote` | postgresql | esegue | esegue | stessi valori e colonne |
| `bound_literal_field` | postgresql | errore esecuzione: UndefinedFunction | esegue | esegue solo Asqueel |
| `bound_escaped_field` | postgresql | esegue | esegue | valori o colonne differenti |
| `embed_column_gt` | postgresql | esegue | errore esecuzione: InvalidTextRepresentation | esegue solo legacy |
| `embed_column_le` | postgresql | esegue | errore esecuzione: InvalidTextRepresentation | esegue solo legacy |
| `embed_relation` | postgresql | esegue | errore esecuzione: InvalidTextRepresentation | esegue solo legacy |
| `line_comment` | postgresql | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `block_comment` | postgresql | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `comment_known_field` | postgresql | esegue | esegue | stessi valori e colonne |
| `comment_parameter` | postgresql | errore esecuzione: KeyError | esegue | esegue solo Asqueel |
| `comment_no_newline` | postgresql | errore esecuzione: SyntaxError | esegue | esegue solo Asqueel |
| `comment_nested` | postgresql | errore esecuzione: KeyError | esegue | esegue solo Asqueel |
| `macro_in_literal` | postgresql | errore esecuzione: KeyError | esegue | esegue solo Asqueel |
| `in_range` | postgresql | esegue | esegue | stessi valori e colonne |
| `relation` | postgresql | esegue | esegue | stessi valori e colonne |
| `relation_repeated` | postgresql | esegue | esegue | stessi valori e colonne |
| `repeated_bind` | postgresql | esegue | esegue | stessi valori e colonne |
| `prefix_params` | postgresql | esegue | esegue | stessi valori e colonne |
| `null_binding` | postgresql | esegue | esegue | stessi valori e colonne |
| `numeric_binding` | postgresql | esegue | esegue | stessi valori e colonne |
| `in_list` | postgresql | esegue | esegue | stessi valori e colonne |
| `not_in_list` | postgresql | esegue | esegue | stessi valori e colonne |
| `in_empty` | postgresql | esegue | esegue | stessi valori e colonne |
| `not_in_empty_null` | postgresql | esegue | esegue | stessi valori e colonne |
| `collection_collision` | postgresql | esegue | esegue | stessi valori e colonne |
| `unused_param` | postgresql | esegue | esegue | stessi valori e colonne |
| `missing_param` | postgresql | errore esecuzione: KeyError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `unicode_field` | postgresql | errore esecuzione: SyntaxError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `quoted_logical_field` | postgresql | errore esecuzione: SyntaxError | esegue | esegue solo Asqueel |
| `quoted_alias` | postgresql | esegue | esegue | stessi valori e colonne |
| `escaped_alias` | postgresql | esegue | esegue | stessi valori e colonne |
| `unicode_param` | postgresql | esegue | errore compilazione: ValueError | esegue solo legacy |
| `cast_colon` | postgresql | esegue | esegue | stessi valori e colonne |
| `dollar_quote` | postgresql | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `tagged_dollar_quote` | postgresql | errore compilazione: GnrSqlMissingField | esegue | esegue solo Asqueel |
| `escape_string` | postgresql | errore compilazione: ValueError | esegue | esegue solo Asqueel |
| `adjacent_field_operator` | postgresql | esegue | esegue | stessi valori e colonne |
| `literal_regexp` | postgresql | esegue | esegue | valori o colonne differenti |
| `literal_semicolon` | postgresql | esegue | esegue | stessi valori e colonne |
| `unknown_field` | postgresql | errore compilazione: GnrSqlMissingField | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `unclosed_string` | postgresql | errore compilazione: ValueError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `unclosed_comment` | postgresql | errore esecuzione: SyntaxError | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `unclosed_dollar` | postgresql | errore compilazione: GnrSqlMissingField | errore compilazione: ValueError | entrambi falliscono; vedere fase e causa |
| `statement_separator` | postgresql | compila; non eseguito | errore compilazione: UnsupportedFeatureError | solo compilazione, perimetro statement |
| `regexp_operator` | postgresql | esegue | errore esecuzione: SyntaxError | esegue solo legacy |
| `legacy_percent_escape` | postgresql | esegue | esegue | valori o colonne differenti |
| `collection_current_collision` | postgresql | esegue | esegue | stessi valori e colonne |
