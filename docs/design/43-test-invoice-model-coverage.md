# 43 — Copertura della configurazione di test_invoice_pg

**Rettifica grammaticale del 13 ottobre 2026:** i riferimenti storici qui sotto
al contenitore `x_ui` non descrivono la grammatica corrente. Gli attributi
sono piatti, con eventuale prefisso; non si raggruppano in `metadata` o `x_ui`.
Vedere il documento 42 e l'esito della fase 1 nel documento 51.


**Aggiornamento del 13 ottobre:** la matrice qui sotto documenta la proposta
iniziale, in parte superata. Per il render usare la
[copertura verificata della fase 0](52-invoice-render-coverage.md), che applica
le decisioni successive: niente provider/behavior, normalize o pkey_from;
rinvii espliciti per system_records, release e funzioni virtuali. L'inventario
dei sorgenti resta valido e i suoi hash sono stati ricontrollati.

12 ottobre 2026. **Censimento statico e matrice della grammatica obiettivo**,
non certificazione del porting né verifica sul database. Completa la
[specifica 42](42-configuration-grammar.md).

Il [piano 44](44-core-release-plan.md) usa questo censimento come perimetro
obbligatorio e prevede un oracolo legacy completo prima di certificare la build.

## Perimetro verificato

Fonte: checkout GenroPy, `projects/test_invoice/instances/test_invoice_pg/instanceconfig.xml`.
Sono stati letti i riferimenti dei package, non copiati parametri di accesso.

| Package | Origine | File modello | Tabelle attese |
| --- | --- | ---: | ---: |
| sys | projects/gnrcore/packages/sys | 17 | 17 |
| adm | projects/gnrcore/packages/adm | 41 | 40 |
| invc | projects/test_invoice/packages/invc | 18 | 18 |
| Totale | | 76 | 75 |

`adm.required_packages()` richiede `gnrcore:sys`, già nell'istanza.
I 41 file adm includono `model/_packages/sys/task.py`, che contribuisce a
`sys.task` senza creare un'altra tabella. `adm.htmltemplate_atc` eredita la
configurazione da `AttachmentTable`: una ricerca delle sole chiamate
`pkg.table()` nei file applicativi la perderebbe.

L'[inventario JSON](evidence/test-invoice-model-inventory.json) registra per
file hash, basi, metodi e chiamate di configurazione con posizione e keyword.
È riproducibile senza importare GenroPy, avviare applicazioni o aprire DB:

```sh
python docs/design/evidence/inventory-test-invoice.py \
  /percorso/Genropy/genropy \
  /tmp/test-invoice-model-inventory.json
```

Lo [script](evidence/inventory-test-invoice.py) segue anche required_packages
quando è una dichiarazione statica; fallisce sulle dipendenze dinamiche anziché
indovinarle. Le righe sono posizioni nel checkout censito, identificate dagli hash.
Gli argomenti sono **testo AST**, non oggetti del modello risolto.

## Mappatura della superficie legacy

| Costruzione / attributi osservati | Rappresentazione nella grammatica 42 |
| --- | --- |
| config_attributes package, sqlschema, sqlprefix, comment, name_* | Oggetto package con mapping fisico e metadati; `_syspackage` in metadata.genropy |
| custom_type_money, custom_type_perc | `pkg.options().type('money', dtype='N', size='14,2', ...)` e perc N `5,2`; format in x_ui |
| registerMacros / addMacro UPPERCASE | Macro registrata sul DB/package con handler e firma, non sostituzione testuale accettata dal client |
| pkg.table, pkey, column, dtype, size, notnull, unique, indexed | Tabella e colonne fisiche tipizzate; bool legacy `y` normalizzati dal bridge |
| name_long/short/plural, rowcaption, caption_field, newrecord_caption, lookup, tabletype | Metadati comuni e di tabella; espressioni validate dove previste |
| sysFields id/ins/upd/ldel/user_ins/draftField | `sys_fields`; draftField→draft. Profilo legacy esplicita user_upd=False e timestamp_type='DH' dove richiesto per conservare lo schema originario |
| sysFields hierarchical/counter/df/md5/sysrecords | Options distinte hierarchical, auto_counter, dynamic_fields, record_hash, system_records |
| pkey_columns, pkey_columns_joiner | `pkey_from`, preservando separatore e trattamento None; non PK multicolonna |
| pkeyValue in adm.user_config | Behavior registrato con new_pkey_value |
| compositeColumn, unique e relation a composite | Oggetto composite, UNIQUE/FK fisiche ordinate, identità JSON strutturata |
| relation mode=foreignkey | relation fisica; default on_update_sql cascade esplicito |
| relation senza foreignkey, anche su formula | weak_relation; nessun vincolo SQL inventato |
| relation_name, one_group, many_group, one_one, deferred | Inverse e metadati; asserzione cardinalità senza UNIQUE implicito; deferrable + initially_deferred |
| onDelete/onDelete_sql/onDuplicate | Azioni applicative e SQL separate; duplicazione con policy esplicita |
| joinColumn + cnd su invoice.discount_tier_id | virtualRelation con pairing sorgente/target e aliasColumn dell'id; inversa dichiarata separatamente |
| aliasTable customer su invoice_row | virtualRelation su percorso @invoice_id.@customer_id |
| aliasColumn con static e dtype | Percorso con override e inclusione predefinita esplicita |
| formulaColumn, sql_formula, select, exists | Espressione/sottoquery/exists; sorgente unica e correlazioni #THIS |
| select_*, var_* | subqueries e parameters; select/where/group_by/having/distinct/order_by/limit conservati |
| subQueryColumn query dict, mode json/xml o omessa | Query tipizzata; mode scalar/json/xml |
| pyColumn py_method, required_columns | Riferimento registrato e dipendenze; template_name/template_localized in contratto metadata.genropy del provider template |
| bagItemColumn bagcolumn/itempath | Estrazione Bag/XML tipizzata |
| default, defaultFrom, sql_value | default applicativo, default_from, calcolo persistito; separati da sqldefault/generated_expression |
| validate_notnull/len/nodup/notnull_error | Sezione validation e messaggi per regola |
| validate_case='U' | normalize(case='upper'); L→lower, T→title se presenti |
| values | Elenco valori/etichette normalizzato; controllo e UI distinti |
| readOnly, unmodifiable | read_only, unmodifiable; semantica applicativa esplicita |
| encrypted X/R/Q | encryption con provider registrato, nessuna chiave nel modello |
| group, group_* | colgroup ordinato e appartenenza al gruppo; sottogruppi conservati |
| subtable condition | Subset logico filtrato, senza DDL |
| partition_state, partition_customer_state | options.partition con field/path e contesto invc_state; non partizione SQL |
| hierarchical_caption_field, sysRecord_masterfield | Parametri caption_field di hierarchical e masterfield di system_records |
| audit, multi_tenant, retention_policy, broadcast, archivable, checkpref | Options comportamentali tipizzate con provider, non metadata passivi |
| subfields | col.dynamic_fields(source=...) |
| _addClass, cell_format, format, _sendback, batch_assign | x_ui; batch_assign conserva regole UI ma autorizzazione resta server |
| _sysfield, legacy_name | metadata.genropy (provenienza/classificazione); legacy_name non autorizza automaticamente rename DDL |
| noTestForMerge | Contratto del provider applicativo di merge, metadata.genropy; non disabilita i controlli di composizione del core |
| trigger_on*, defaultValues, counter_inv_number | behavior e numbering; binding simbolico con ordine del ciclo scritture |
| sysRecord_*, _release_* rilevati dai mixin | system_records/release espliciti; nessuna esecuzione durante render |
| db.adapter.string_agg, cicli Python e helper nel config_db | L'host produce source dichiarativa concreta prima del render; non serializza chiamate o codice Python |

I namespace metadata dei provider sono anch'essi validati quando hanno un
consumatore: template_name o noTestForMerge non devono essere accettati e poi
ignorati da un'applicazione che promette il comportamento legacy. I metadati UI
restano leggibili anche senza un frontend installato.

## Espansioni da non perdere

Riferimento: `gnrpy/gnr/app/gnrdbo.py`, `GnrDboTable.sysFields` e helper.
Oltre ai campi chiesti esplicitamente dai singoli file:

- `__record_pointer` viene aggiunto anche con id=False; usa la vera pkey.
- SysFields aggiunge virtuali di protezione e invalidità, rileva sysRecord_*
  e release; le dipendenze dal contesto e dai metodi diventano binding espliciti.
- Gerarchie aggiungono parent FK, percorsi, colonne parent, formule e, con
  contatore, `_h_count`, `_parent_h_count`, `_h_sortcol`.
- Dynamic fields aggiunge `df_fields`, `df_fbcolumns`, `df_custom_templates`,
  `df_colswidth`. `audit='lazy'` aggiunge anche `__version`.
- `AttachmentTable.config_db` genera id/sys_fields/counter, filepath e relativi
  metadati, external_url, description, mimetype, text_content, info,
  is_foreign_document, maintable_id con FK, adapted_url e pyColumn per URL/file.
  Aggiorna anche il master `adm.htmltemplate`. Le varianti atc_types/atc_download
  dipendono dai mixin effettivi e non vanno indovinate.
- `sys` e `adm` hanno riferimenti incrociati: prima costruire tutte le
  dichiarazioni, poi risolvere le relazioni; non richiedere ordine topologico
  impossibile alle singole chiamate column.

## Registro di ogni modello

Nella colonna finale sono evidenziate le costruzioni speciali osservate;
«base» comprende tabella, colonne, metadati e sysFields dove dichiarato.
Per ogni riga restano da provare build, proiezione DDL e comportamento.

| Modello / contributo | File nel package | Costruzioni da verificare |
| --- | --- | --- |
| sys.batch_log | `batch_log.py` | formule |
| sys.calendar | `calendar.py` | Python, formule |
| sys.dataretention | `dataretention.py` | base |
| sys.dbchange | `dbchange.py` | base |
| sys.error | `error.py` | formule, retention_policy |
| sys.external_token | `external_token.py` | Python |
| sys.external_token_use | `external_token_use.py` | base |
| sys.externalcall_log | `externalcall_log.py` | base |
| sys.locked_record | `locked_record.py` | indice esplicito |
| sys.service | `service.py` | hook, pkey_columns |
| sys.shared_object | `shared_object.py` | base |
| sys.shorturl | `shorturl.py` | pkey_columns |
| sys.task | `task.py` | formule, hook |
| sys.task_execution | `task_execution.py` | alias, formule, retention_policy |
| sys.task_result | `task_result.py` | base |
| sys.upgrade | `upgrade.py` | pkey_columns |
| sys.widget | `widget.py` | audit, df, hierarchical |
| adm → sys.task | `_packages/sys/task.py` | FK adm.user |
| adm.access_group | `access_group.py` | base |
| adm.api_token | `api_token.py` | formule |
| adm.api_token_tag | `api_token_tag.py` | alias |
| adm.audit | `audit.py` | base |
| adm.authorization | `authorization.py` | hook |
| adm.backup | `backup.py` | formule, hook |
| adm.ckstyle | `ckstyle.py` | formule |
| adm.connection | `connection.py` | alias, checkpref, hook |
| adm.counter | `counter.py` | multi_tenant, pkey_columns |
| adm.day | `day.py` | base |
| adm.group | `group.py` | counter, formule |
| adm.group_helpdoc | `group_helpdoc.py` | alias, counter |
| adm.helpdoc | `helpdoc.py` | base |
| adm.htag | `htag.py` | counter, formule, hierarchical, sysrecords |
| adm.htmltemplate | `htmltemplate.py` | hook |
| adm.htmltemplate_atc | `htmltemplate_atc.py` | AttachmentTable ereditata |
| adm.install_checklist | `install_checklist.py` | hook |
| adm.language | `language.py` | counter, system records da metodi |
| adm.letterhead_type | `letterhead_type.py` | base |
| adm.menu | `menu.py` | alias, counter, hierarchical |
| adm.menu_page | `menu_page.py` | base |
| adm.notification | `notification.py` | formule, hook |
| adm.pkginfo | `pkginfo.py` | base |
| adm.preference | `preference.py` | hook |
| adm.record_tag | `record_tag.py` | base |
| adm.sent_email | `sent_email.py` | base |
| adm.served_page | `served_page.py` | checkpref |
| adm.shortcut | `shortcut.py` | counter |
| adm.tblinfo | `tblinfo.py` | base |
| adm.tblinfo_item | `tblinfo_item.py` | pkey_columns |
| adm.user | `user.py` | Python, formule, hook, md5 |
| adm.user_access_group | `user_access_group.py` | base |
| adm.user_config | `user_config.py` | formule, generatore pkey Python, hook |
| adm.user_group | `user_group.py` | base |
| adm.user_notification | `user_notification.py` | base |
| adm.user_setting | `user_setting.py` | default da metodo, pkey_columns |
| adm.user_tag | `user_tag.py` | alias, formule, hook |
| adm.userobject | `userobject.py` | Python, archivable, broadcast, default da metodo, defaultFrom, formule, hook, sql_value |
| adm.week | `week.py` | formule |
| adm.xgroup | `xgroup.py` | system records da metodi |
| invc.customer | `customer.py` | Python, alias, draftField, encrypted, formule, partition_state, subtable |
| invc.customer_type | `customer_type.py` | base |
| invc.discount_tier | `discount_tier.py` | base |
| invc.invoice | `invoice.py` | alias, default da metodo, formule, join condizionale, numbering, partition_customer_state, sottoquery |
| invc.invoice_note | `invoice_note.py` | formule |
| invc.invoice_row | `invoice_row.py` | alias, alias di relazione, counter, formule, hook |
| invc.payment_type | `payment_type.py` | base |
| invc.postcode | `postcode.py` | base |
| invc.price_year | `price_year.py` | alias, composite, formule |
| invc.price_year_note | `price_year_note.py` | alias, composite |
| invc.product | `product.py` | Bag/XML, Python, alias, formule, subfields |
| invc.product_group | `product_group.py` | counter, hierarchical |
| invc.product_type | `product_type.py` | counter, df, hierarchical |
| invc.region | `region.py` | base |
| invc.staff | `staff.py` | alias, formule |
| invc.staff_role | `staff_role.py` | base |
| invc.state | `state.py` | base |
| invc.vat_type | `vat_type.py` | base |

## Limiti della verifica e gate di accettazione

Il censimento include tutti i file model dei tre package dichiarati e il
contributo inter-package; l'ispezione manuale ha aggiunto i casi ereditati da
gnrdbo. **Non è il dump di un'applicazione avviata:** condizioni, cicli, mixin,
plugin e risoluzione dei metodi possono aggiungere dichiarazioni. I conteggi
delle chiamate nell'AST non equivalgono al numero di colonne finali.

Per attestare la copertura reale occorre costruire il modello completo con il
medesimo insieme di contributi, espansioni e contesto del legacy e confrontarne
gli oggetti. Conservare uno snapshot senza segreti e registrare le differenze
deliberate: default user_upd, timestamp UTC, politica draft e ciclo RAW.
La compatibilità richiede un profilo esplicito dove questi nuovi default
divergono dal legacy, non modifiche DDL inattese sull'istanza esistente.

La prima verifica migrations deve quindi usare **tutti e tre i package** su
un DB temporaneo: validazione JSON normalized, diff esaminata, apply, introspection
e seconda diff vuota. Il JSON deve contenere anche le colonne generate dalle
options e le FK del contributo adm→sys.task. Una prova su sole tabelle invoice
non soddisfa il requisito dell'utente.

Le virtual relations richiedono inoltre casi dedicati oltre al corpus corrente:
qui sono rappresentate principalmente da joinColumn/aliasTable legacy, non da
chiamate native a virtualRelation. Servono test per parametri sorgente/ask,
inverse filtrate, cardinalità, ordinamento, limit, NULL e cicli.
