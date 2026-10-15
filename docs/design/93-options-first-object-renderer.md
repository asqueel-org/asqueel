# 93 — Options prima delle dichiarazioni nel renderer a oggetti

15 ottobre 2026. Decisione dell'utente: il renderer elabora prima le options,
poi gli altri elementi. È un consumo logico della sezione options, senza
modificare la source originale e senza ordinamenti nel compilatore.

## Implementazione

Il percorso `objects_tree` chiede a `prepare_source` l'espansione delle options
prima delle dichiarazioni ordinarie. La preparazione lavora già su una copia
privata: la source originale, inclusi attributi e ordine, resta invariata.

Si riusano gli algoritmi di `model_expansion`, compreso l'ordine dei passaggi
locali e delle dipendenze fra tabelle. Durante l'emissione ogni campo prodotto
da un'opzione viene inserito nella posizione successiva del primo passaggio,
prima delle colonne esplicite ancora da consumare. Se il campo era dichiarato
esplicitamente, si compone lo stesso nodo conservando attributi, validazioni e
relazioni: non viene emesso una seconda volta. Ulteriori contributi allo stesso
campo non ne cambiano nuovamente la posizione.

La walk di `RendererBase` resta invariata e gli oggetti continuano a nascere in
`finalize`. Nei frammenti il nodo options viene estratto dalla sequenza ordinaria
e conservato per primo. Le sue dichiarazioni restano consultabili sull'oggetto;
i loro effetti strutturali sono già stati applicati nella preparazione e non
vengono rieseguiti durante la walk o la costruzione degli oggetti.

La source completa resta disponibile durante la preparazione per controllare
conflitti, tipi e dipendenze fra tabelle. Non si tenta di ricostruire la cronologia
delle chiamate del builder: la precedenza delle options è la regola concordata.
Il percorso precedente mantiene il proprio ordine. Nessun file del compilatore
è stato modificato in questo incremento.

## Risultato sui 74 modelli

Il [confronto riproducibile](probes/options_first_order.py) legge l'XML legacy
congelato e confronta le colonne fisiche di ogni tabella con gli oggetti nativi.
[Risultati completi](evidence/options-first/order.json):

- Source originale invariata. Su 74/74 tabelle l’insieme delle colonne fisiche
  è identico al legacy e gli oggetti conservano l’ordine della source espansa.
- 62/74 tabelle con ordine fisico identico al legacy; prima erano 7/74.
- 12/74 con differenze residue interne alle espansioni già esistenti.
- `invc.customer`: campi di sistema prima di `account_name`, come nel legacy.
  I due contratti SQL `star` su SQLite e PostgreSQL passano senza modificare
  l'oracolo; rimossi i due `xfail`.

Le differenze residue non vengono nascoste da nuovi `xfail` né considerate
equivalenti per l'accesso alle righe per posizione:

| Tabelle | Origine della differenza residua |
| --- | --- |
| `adm.group`, `adm.group_helpdoc`, `adm.htmltemplate_atc`, `adm.language`, `adm.shortcut`, `invc.invoice_row` | Nel legacy il contatore è dichiarato prima dei campi utente. L'espansione nativa esistente termina `sys_fields`, poi elabora `auto_counter`. |
| `adm.user` | Il legacy dichiara `__rec_md5` prima dei campi utente; il blocco nativo `record_hash` segue `sys_fields`. |
| `sys.widget`, `adm.htag`, `adm.menu`, `invc.product_group`, `invc.product_type` | Il legacy espande la gerarchia dentro `sysFields`, prima di contatori/campi utente, dichiarando anche il campo base (`name`, `code`, ecc.). Il percorso nativo esistente espande la gerarchia dopo le options locali e legge il campo base esplicito. |

Riferimento legacy: `gnr/app/gnrdbo.py`, `sysFields` (blocchi md5, hierarchical,
counter, audit, user_ins/user_upd). Il presente incremento cambia la precedenza
rispetto alle dichiarazioni ordinarie, non la sequenza interna di questi blocchi.
**Decisione successiva dell'utente:** le 12 differenze d'ordine sono accettate,
senza riallineamento. Si verifica invece la composizione dei campi condivisi:
tipo, attributi e relazioni, senza duplicazioni. Esito nel
[rapporto 94](94-shared-option-fields.md).

## Verifiche

I test coprono options dichiarate prima, fra o dopo le colonne; dichiarazioni
esplicite che arricchiscono un campo generato; options disabilitate; applicazione
una sola volta per render; conservazione delle options; dipendenze e relazioni
degli allegati. Su tutte le 74 tabelle verificano ordine ripetibile, precedenza
dei nuovi campi sulle colonne ordinarie e ordine relativo delle dichiarazioni
ordinarie invariato. I test migration confrontano il contenuto JSON completo
con legacy e percorso precedente, inclusa applicazione/introspezione PostgreSQL.

**Regressione complessiva: 5.228 passati, 21 skip, nessun xfail**, eseguita in
due gruppi disgiunti: 2.427 test dell’albero e 2.801 degli altri percorsi.
I 79 contratti dedicati all’ordine sono stati verificati anche separatamente.
Ruff passa sui file cambiati; mypy passa sui tre file sorgente cambiati.
Sphinx e il controllo whitespace del diff passano.

I log di verifica sono in [evidence/options-first](evidence/options-first/verification.json).
