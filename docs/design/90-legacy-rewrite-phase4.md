# 90 — Fase 4: options, filtri, star, macro e bagItemColumn

15 ottobre 2026. **Raccordo implementato e verificato.** Approvato esplicitamente
il riuso della correzione esistente di `#IN_RANGE`: confronti tipizzati prima dei
controlli NULL per consentire il binding PostgreSQL degli estremi assenti.

Riferimenti: [piano 86](86-legacy-compiler-logical-phases.md),
[fase 3](89-legacy-rewrite-phase3.md), [options 65](65-native-options-and-star.md),
[macro 64](64-compiler-macros.md), [Bag 69](69-native-bag-items.md).

## Raccordo e ordine legacy

Il flusso di `compiledQuery` resta riconoscibile:

1. Riconoscimento delle operazioni verso molti prima di interpretare gli argomenti.
   Nessun handler `many_*`; nessuna JOIN verso molti, riga esplosa o DISTINCT implicito.
2. Normalizzazione delle proiezioni; `*` legge le colonne fisiche dell'albero,
   seguite dalle virtuali statiche. `bagFields=False` esclude le fisiche X, non
   le virtuali statiche X. Una virtuale non supportata non viene scartata.
3. Le clausole di raggruppamento determinano il contesto aggregato. `group_by='*'`
   segnala aggregazione senza produrre GROUP BY, come nel legacy. La SELECT figlia
   continua a ignorare l'ordine di tabella; la root legge l'ordine dichiarato
   quando manca un ordine esplicito. Si conserva il bypass nativo `order_by=''`.
4. Espansione di IN_RANGE e PERIOD nel WHERE. Poi composizione AND nell'ordine
   legacy: WHERE del chiamante, partition, cancellazione logica, draft.
5. Embed dei parametri che indicano campi, raccolta dei riferimenti di tutte le
   clausole, risoluzione ricorsiva di campi/formule/relazioni, template substitution.
6. Assemblaggio con l'adapter, una sola preparazione finale di SQL e kwargs.

Gli algoritmi di riferimento sono `compiledQuery`, `expandInRange`,
`expandPeriod` e `getFieldAlias` in `fa35e5ad`; `starColumns` e
`static_virtual_columns` in `gnrsqlmodel/table.py`; l'helper `bagItemFormula`.
Conservati i riferimenti ai branch degli studi 65 e 69; **106 hash AST verificati**
contro la ricognizione del piano. Non importati scanner, ottimizzazioni JOIN,
nuove sintassi macro, set operator o query concatenate.

### Options e filtri

Si leggono i marcatori esistenti di sys_fields, senza inferire comportamenti dai
nomi delle colonne. Cancellazione logica: IS NULL; draft: IS NOT TRUE. La
traduzione SQLite di quest'ultimo resta quella dell'adapter legacy già verificato
in R3 (IS NULL oppure !=1). I filtri riguardano la tabella della SELECT, non le
sue JOIN. Le SELECT figlie conservano i default legacy e gli override espliciti.

La partition nativa mantiene la decisione del rapporto 65: solo valore corrente
scalare già risolto dal render; None opzionale non filtra, None obbligatorio dà
un errore, zero/False/stringa vuota sono valori presenti; ignorePartition bypassa.
I campi alias attraversano il ramo relations. Le altre options restano conservate
nel modello; non acquistano nuovi hook. Il contratto esplicito x_partition già
esistente resta distinto, senza dedurre chiavi di ambiente per le options native.

`excludeLogicalDeleted='mark'` aggiunge `_isdeleted` nel caso non aggregato;
non aggiunge la colonna quando DISTINCT/GROUP BY indicano aggregazione, come nel
legacy. DISTINCT esplicito, GROUP BY/HAVING e FOR UPDATE sono raccordati per le
SELECT supportate; le capacità e il SQL del dialetto restano agli adapter.

### Decisione sulla pkey automatica

L'utente ha chiesto uno switch comodo e ha espresso dubbi sull'aggiunta implicita
nel nuovo percorso. È disponibile la firma legacy:

```python
q = db.table('invc.invoice').query('$inv_number')  # solo le colonne richieste
q = db.table('invc.invoice').query('$inv_number', addPkeyColumn=True)
q = db.table('invc.invoice').query('$inv_number', addPkeyColumn=False)
```

**Default nuovo: False.** Con True viene aggiunta la pkey come `pkey`, salvo query
aggregata secondo le regole legacy. Il vecchio percorso conserva la sua API.
Non si introduce una option globale del DB né una configurazione persistente.
Il contratto congelato del default legacy non viene riscritto: si verifica che
il default nuovo non aggiunga la colonna e che lo switch True riproduca il SQL
legacy. La differenza di default è intenzionale ed esplicita.

### Macro

`#IN_RANGE` conserva la grammatica legacy a operandi semplici e i quattro casi
con estremi inclusivi. `#PERIOD` usa il decoder Toolbox esistente e conserva
uguaglianza/BETWEEN/intervalli aperti. `#THIS` e `#nome` per select_nome restano nel
percorso ricorsivo della fase 3. L'espansione usa le regex legacy: non si riporta
la protezione tramite scanner del vecchio compilatore Asqueel.

Il testo di PERIOD è consumato dalla compilazione, ma resta nei kwargs forniti
dal chiamante secondo il contratto R2 degli argomenti inutilizzati. Le date sono
binding separati con collisioni evitate; ripetizioni nella stessa SELECT riusano
i limiti, SELECT sorelle restano isolate. Ambiente workdate/locale nello snapshot,
nessuna mutazione dell'ambiente o dei parametri del chiamante.

`#ENV`, TSQUERY/TSRANK/TSHEADLINE/VECQUERY/VECRANK, BAG/BAGCOLS restano da valutare;
#PREF è rinviato. Non sono abilitati implicitamente dalla richiesta di portare
le macro già implementate.

**Correzione approvata — NULL parametrizzato su PostgreSQL:** i test preesistenti
verificano `#IN_RANGE($total,:low,:high)` anche con low/high None, perché il legacy
prevede un estremo aperto. Con l'ordine originale e binding psycopg PostgreSQL
segnala `AmbiguousParameter: could not determine data type of parameter $1`
(oppure $2): il parametro compare in IS NULL prima del confronto numerico.

L'utente ha approvato il riuso della correzione del compilatore Asqueel precedente:
anteporre i confronti numerici, conservando i quattro casi e la logica SQL a tre
valori. L'helper puro `_in_range` è ora condiviso in `_legacy_sql`, senza modifiche
al suo algoritmo. Il contratto confronta la clausola corretta separatamente;
l'oracolo legacy resta invariato. I test reali verificano entrambi gli estremi
presenti, uno assente, entrambi assenti e valore NULL su entrambi i dialetti.
**59 prove mirate macro passano**, incluse le tre prove PostgreSQL prima fallite.

### bagItemColumn

Riutilizzati il traduttore del percorso già portato e `dialect.bag_item_formula`:
`#n` diventa XPath `*[n+1]`, `?attributo` seleziona un attributo, altrimenti text();
si legge il primo risultato XPath e si applicano i cast del legacy corrente.
Il traduttore puro è condiviso in `_legacy_sql`, mantenendo il suo import nel
compilatore precedente. Nessuna modifica al suo algoritmo.

SQL e var_calculated_path vengono generati nella copia locale degli attributi
alla compilazione, non nel modello. Scope ordinari di formula per alias,
dipendenze, JOIN e sottoquery. PostgreSQL mantiene tipi, NULL ed errori XML/cast;
SQLite continua a rifiutare XPath. Nessuna emulazione o conversione Python nuova.

## Verifiche e limiti del confronto

Regressione finale: **4.801 passati, 21 skip, 2 xfail** (149,66 secondi).
I due xfail sono esclusivamente il confronto stretto dell'ordine di star descritto
sotto. Nessun fallimento inatteso. Ruff e Sphinx con warning come errori passano;
mypy conserva i due errori preesistenti in dialects/postgres.py (righe 127 e 367),
nessun nuovo errore nei file del raccordo.

- **148 test di visibilità**: tutte le 74 tabelle native su PostgreSQL e SQLite,
  con righe draft NULL/False/True e tombstone presente/assente; default, bypass e mark.
- **20 corpi legacy** riusati per options/partition/mark/star e bagItemColumn;
  **9 prove Bag PostgreSQL** riusate per valori, tipi, NULL, attributi, posizioni,
  relazioni, sottoquery, GROUP/HAVING, DISTINCT e errori di esecuzione.
- **78 prove mirate di compilazione**: options, star/Bag, periodi, scope, pkey;
  operazioni I/O dei driver impedite. Non sono test di fetch sul nuovo percorso.
- Censimento senza I/O: 74/74 proiezioni fisiche per dialetto; `*` con bagFields
  False e True su 73/74. L'unico blocco è adm.htmltemplate_atc per pyColumn statiche
  rinviate. Le 3 bagItemColumn native compilano su PostgreSQL e vengono rifiutate
  esplicitamente su SQLite.
- Confronto 498 richieste: 342 compilabili sul nuovo albero; 334 SQL/kwargs
  equivalenti, 2 con ordine IN_RANGE corretto come approvato,
  2 con identità dei locali diversa (id legacy), 2 con pkey di default
  volutamente assente, 2 con ordine delle colonne `*` diverso per l'albero nativo.
  Le 156 richieste restanti coinvolgono funzionalità verso molti rinviate o il
  terminale count ancora assente, non handler introdotti in questa fase.
- JSON migration dei 74 modelli invariato; renderer e driver invariati.
  Nessun cambio del compilatore predefinito, commit, release o push.

Il terminale count e i wildcard con prefisso/percorso restano da raccordare sul
nuovo percorso; la presente consegna non ne certifica il supporto.

### Differenza preesistente nell'ordine di star

L'albero nativo colloca le colonne aggiunte da sys_fields dopo quelle dichiarate;
lo snapshot XML legacy di customer le contiene prima. Il compilatore applica lo
stesso algoritmo starColumns, cioè segue l'ordine delle colonne del modello.
Non viene introdotto un ordinamento speciale nel compilatore né modificato il
renderer in questo incremento. Due contratti SQL stretti rimangono xfail per
questa differenza; l'esecuzione verifica comunque gli stessi nomi e valori per
nome. L'ordine di posizione non viene dichiarato equivalente al vecchio XML.

### Adattamenti delle fixture

I corpi legacy sono riusati tramite terminali esclusivamente di test: compilano
con il nuovo albero ed eseguono il CompiledQuery su una connessione separata.
Il count di controllo conta le righe ottenute; non certifica né implementa un
nuovo count compiler o fetch. Le prove di visibilità leggono i marcatori del
nuovo albero e usano `$nome`, non la vecchia estensione `$"nome"` eliminata in R1.
I test SQLite controllano la preparazione IS NOT TRUE dell'adapter effettivo.

Evidenze: [censimento](evidence/legacy-rewrite-phase4/native-census.json),
[invarianti](evidence/legacy-rewrite-phase4/invariants.json),
[confronto](evidence/legacy-rewrite-phase4/legacy-comparison.json),
[regressione](evidence/legacy-rewrite-phase4/full-suite-final.log).
