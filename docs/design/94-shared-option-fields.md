# 94 — Composizione dei campi condivisi dalle options

15 ottobre 2026. **Verifica completata, nessuna modifica alla produzione.**
L'utente accetta le 12 differenze di ordine del rapporto 93: non sono difetti
da riallineare. Restano richiesti tipo, attributi, relazioni e assenza di duplicati.

## `invc.product_group._row_count`

Nel legacy `sysFields(hierarchical='code,_row_count', counter=True)` incontra
`_row_count` nel ciclo della gerarchia: `tbl.column(fld)` crea il nodo, poi
il blocco counter richiama `tbl.column('_row_count', dtype='L', ...)` e completa
lo stesso campo. I derivati gerarchici rimangono testuali.

Nel percorso nativo `auto_counter` produce prima il campo numerico; `hierarchical`
legge quel campo e aggiunge i derivati. I risultati confrontati con l'oracolo
legacy sono:

| Elemento | Risultato verificato |
| --- | --- |
| `_row_count` | Un solo campo `L`, `counter=True`, `_sysfield=True`, gruppo `zzz`, etichetta `!![en]Counter`. |
| `hierarchical__row_count` | Campo `T`, `hierarchical_field_of='_row_count'`, attributi legacy conservati. |
| `_parent_h__row_count` | Campo `T`, attributi legacy conservati. |
| `_h_count`, `_parent_h_count` | Campi `T`, come nel legacy. |
| `_h_sortcol` | Stessa formula `COALESCE($_h_count,$code)` e stessi attributi del legacy. |
| Tabella | `hierarchical='code,_row_count,pkey'`, `counter=True`, `order_by='$_h_sortcol'`. |
| Relazione di `parent_id` | Stesso joiner legacy, una sola dichiarazione e una sola voce diretta nel ramo relations. |

Il ramo gerarchico non aggiunge `setRowCounter` né `_counter_fkey`: sono proprietà
del contatore ordinario e rimangono assenti, come nel legacy. Il contatore stesso
non acquisisce una relazione inventata: il collegamento della gerarchia è su
`parent_id`.

## Altri campi condivisi

La lettura strumentata delle espansioni delle 74 ricette individua 15 campi
fisici condivisi fra options o fra options e dichiarazioni, in otto tabelle:

- `adm.htag`: `code`, `description`, `id`.
- `adm.htmltemplate`: `id`.
- `adm.htmltemplate_atc`: `id`.
- `adm.menu`: `id`, `label`.
- `adm.user`: `id`.
- `invc.product_group`: `_row_count`, `code`, `id`.
- `invc.product_type`: `description`, `id`.
- `sys.widget`: `id`, `name`.

Per ciascuno i test confrontano gli attributi legacy, il tipo effettivo, l'identità
dell'oggetto nei diversi accessi e l'unicità della dichiarazione fisica.
Gli attributi `validate_*` vengono confrontati con `column.validations`, i flag
legacy con il namespace già esistente `x_legacy_*`, `readOnly` con `read_only`.

`adm.htmltemplate_atc.id` è il caso di doppia emissione: prima `sys_fields`, poi
il blocco allegati. Le due chiamate aggiornano lo stesso nodo della source
privata. Restano tipo `A`, size `22`, `read_only`, `_sendback` e generazione
`legacy22`, insieme a etichetta `Id` e gruppo `_`, come nel legacy.
La relazione di `maintable_id` conserva il joiner legacy e non viene duplicata.

Il confronto non pretende identità del dizionario grezzo: il tipo può essere
dedotto dalla size, alcuni default booleani sono espliciti, `virtual_column`
è rappresentato dalla classe dell'oggetto. Il legacy conserva inoltre
`_owner_package` su `sys.widget.id/name`: è provenienza di costruzione, assente
nel modello nativo. `adm.user.id` riceve `indexed=True` dalla risoluzione delle
weak relations già esistente (`resolve_source_references`); il contenuto fisico
del JSON migration resta uguale al riferimento. Queste differenze sono visibili
nel confronto allegato e non derivano dalla composizione delle options.

## Verifiche

**366 test passati**, inclusi **19 nuovi contratti**. Suite eseguite:
`test_shared_option_fields`, `test_invoice`, `test_options_first`,
`test_native_option_expansion`, `test_migration`.

La copertura comprende tutti i 74 modelli, il registro delle 144 relazioni
ordinarie, JSON migration e applicazione/introspezione PostgreSQL. La source
originale resta invariata. Nessun cambiamento a renderer, espansioni o compilatore;
aggiunti soltanto test e documentazione. Ruff passa sul nuovo file di test.

Evidenze: [confronto dei campi](evidence/shared-option-fields/comparison.json)
e [risultati dei test](evidence/shared-option-fields/tests.log).
