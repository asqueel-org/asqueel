# R0 — Matrice dei 71 casi e delle 132 osservazioni

Generata da `freeze_legacy_contracts.py`. Le osservazioni sono quelle del rapporto 78.
Nessuna nuova esecuzione SQL. `expected` nel corpus resta un oracolo della sonda:
non prevale sul legacy, soprattutto per stringhe/escape e parametri simbolici.
Le voci compatibili riguardano il contratto indicato; D3 resta trasversale ai kwargs.

| Caso | Contratto | Stato | Fase | Decisioni | Dialetti |
| --- | --- | --- | --- | --- | --- |
| `physical` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `sqlparams_year` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `case` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `coalesce` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `cast` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `literal_comma` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `literal_as` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `adjacent_field_operator` | C01 | compatibilita_confermata | R1 | — | sqlite, postgresql |
| `alias_lower` | C02 | compatibilita_confermata | R2 | — | sqlite, postgresql |
| `quoted_alias` | C02 | compatibilita_confermata | R2 | — | sqlite, postgresql |
| `escaped_alias` | C02 | compatibilita_confermata | R2 | — | sqlite, postgresql |
| `expression_no_alias` | C02 | recupero_legacy | R2 | — | sqlite, postgresql |
| `duplicate_alias` | C02 | recupero_legacy | R2 | — | sqlite, postgresql |
| `alias_mixed` | C02 | decisione_aperta | R2 | M4 | sqlite, postgresql |
| `embed_column_gt` | C03 | recupero_legacy | R2 | — | sqlite, postgresql |
| `embed_column_le` | C03 | recupero_legacy | R2 | — | sqlite, postgresql |
| `bound_literal_field` | C03 | recupero_legacy | R2 | — | sqlite, postgresql |
| `bound_escaped_field` | C04 | recupero_legacy | R2/R3 | — | sqlite, postgresql |
| `unicode_param` | C04 | recupero_legacy | R2/R3 | — | sqlite, postgresql |
| `bound_quote` | C04 | compatibilita_confermata | R2/R3 | — | sqlite, postgresql |
| `repeated_bind` | C04 | compatibilita_confermata | R2/R3 | — | sqlite, postgresql |
| `prefix_params` | C04 | compatibilita_confermata | R2/R3 | — | sqlite, postgresql |
| `null_binding` | C04 | compatibilita_confermata | R2/R3 | — | sqlite, postgresql |
| `numeric_binding` | C04 | compatibilita_confermata | R2/R3 | — | sqlite, postgresql |
| `cast_colon` | C04 | compatibilita_confermata | R2/R3 | — | postgresql |
| `literal_field` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_unknown_field` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_relation` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_unknown_relation` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_param` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_param_and_binding` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_colon_escape` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_dollars` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_quotes` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_percent` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `like_percent` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `macro_in_literal` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `literal_regexp` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite, postgresql |
| `sqlite_literal_ilike` | C05 | decisione_aperta | R1/R2/R3 | M3 | sqlite |
| `legacy_percent_escape` | C05 | decisione_aperta | R1/R2/R3 | M3 | postgresql |
| `line_comment` | C06 | decisione_aperta | R1/R3 | M2 | sqlite, postgresql |
| `block_comment` | C06 | decisione_aperta | R1/R3 | M2 | sqlite, postgresql |
| `comment_known_field` | C06 | decisione_aperta | R1/R3 | M2 | sqlite, postgresql |
| `comment_parameter` | C06 | decisione_aperta | R1/R3 | M2 | sqlite, postgresql |
| `comment_no_newline` | C06 | decisione_aperta | R1/R3 | M2 | sqlite, postgresql |
| `comment_nested` | C06 | decisione_aperta | R1/R3 | M2 | postgresql |
| `in_list` | C07 | compatibilita_confermata | R3 | — | sqlite, postgresql |
| `not_in_list` | C07 | compatibilita_confermata | R3 | — | sqlite, postgresql |
| `in_empty` | C07 | compatibilita_confermata | R3 | — | sqlite, postgresql |
| `not_in_empty_null` | C07 | compatibilita_confermata | R3 | — | sqlite, postgresql |
| `collection_current_collision` | C07 | compatibilita_confermata | R3 | — | sqlite, postgresql |
| `collection_collision` | C07 | decisione_aperta | R3 | M1 | sqlite, postgresql |
| `regexp_operator` | C08 | recupero_legacy | R3 | — | postgresql |
| `sqlite_ilike_operator` | C08 | recupero_legacy | R3 | — | sqlite |
| `embed_relation` | C09 | dipendenza_successiva | R5 | — | sqlite, postgresql |
| `relation` | C09 | dipendenza_successiva | R5 | — | sqlite, postgresql |
| `relation_repeated` | C09 | dipendenza_successiva | R5 | — | sqlite, postgresql |
| `in_range` | C09 | dipendenza_successiva | R5 | — | sqlite, postgresql |
| `unknown_field` | C10 | compatibilita_confermata | decisione prima del raccordo | — | sqlite, postgresql |
| `missing_param` | C10 | decisione_aperta | decisione prima del raccordo | M5 | sqlite, postgresql |
| `unicode_field` | C10 | limite_comune | decisione prima del raccordo | — | sqlite, postgresql |
| `quoted_logical_field` | C10 | decisione_aperta | decisione prima del raccordo | D1 | sqlite, postgresql |
| `dollar_quote` | C05 | decisione_aperta | R1/R2/R3 | D2, M3 | postgresql |
| `tagged_dollar_quote` | C05 | decisione_aperta | R1/R2/R3 | D2, M3 | postgresql |
| `escape_string` | C05 | decisione_aperta | R1/R2/R3 | D2, M3 | postgresql |
| `unclosed_string` | C10 | decisione_aperta | decisione prima del raccordo | D4 | sqlite, postgresql |
| `unclosed_comment` | C10 | decisione_aperta | decisione prima del raccordo | D4 | sqlite, postgresql |
| `unclosed_dollar` | C10 | decisione_aperta | decisione prima del raccordo | D2, D4 | postgresql |
| `statement_separator` | C10 | decisione_aperta | decisione prima del raccordo | D5 | sqlite, postgresql |
| `literal_semicolon` | C05 | compatibilita_confermata | R1/R2/R3 | — | sqlite, postgresql |
| `unused_param` | C11 | decisione_aperta | R0 decisione/R3 | D3 | sqlite, postgresql |

I dettagli completi di richieste, risultati, errori, tipi e kwargs sono in
[contracts.json](contracts.json); il SQL originale in
[results.json](../scanner-comparison/results.json).

Le 19 definizioni legacy sono congelate in [legacy-tests.json](legacy-tests.json),
con presenza/hash per gli otto snapshot. Non sono 19 nuovi test eseguiti.
