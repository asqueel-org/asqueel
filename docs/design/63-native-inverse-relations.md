# 63 — Relazioni inverse ordinarie e child_count

14 ottobre 2026. Raccordo della navigazione inversa per le cinque formule
rimaste bloccate dopo il [rapporto 62](62-native-method-formulas.md).
Nessuna nuova sintassi, nessuna modifica alle formule o al modello generato.

## Legacy e branch sperimentali

Riferimenti congelati nell'[inventario](evidence/formula-baseline/inventory.json).

| Riferimento | Algoritmo verificato | Raccordo |
| --- | --- | --- |
| Legacy `fa35e5a`, `gnr/app/gnrdbo.py:392–393` | child_count = sottoquery COUNT(*) con `@_children.parent_id=#THIS.id` | Dichiarazione nativa invariata, stessa correlazione |
| Legacy, `gnrsqldata/compiler.py:540–568,659–667` | Riuso del JOIN per percorso/alias; inversione one/many; LEFT JOIN; rilevazione delle righe moltiplicate | Stesso albero dei JOIN già usato da Asqueel, con le coppie di chiavi invertite dal modello |
| v2 `68f35b9`, righe 663–679 | Joiner separato, orientamento one/many invariato | Nessun secondo algoritmo di JOIN |
| v2, righe 286–297,621–634; v4 `38d210c`, righe 591–640 | Intercettazione dei percorsi many e conversione in sottoquery aggregate | Non adottata: cambia forma/cardinalità dei risultati e appartiene agli esperimenti già rimandati |
| v4, righe 977–997 | Riuso alias e orientamento one/many nel percorso JOIN | Conservati attraverso il percorso comune esistente |

Il legacy gestisce anche `_explodingRows`, DISTINCT implicito quando distinct
è None/vuoto e aggregazione dei valori figli nel runtime. Questi comportamenti
non sono una conseguenza automatica dell'abilitazione del JOIN. Il contratto
Asqueel già esistente mantiene DISTINCT esplicito, conteggio delle righe SQL e
assenza di aggregazione Python. Il raccordo dei default impliciti legacy resta
separato, come indicato nella checklist; non viene dichiarata equivalenza del
runtime legacy sulle collection.

## Modifica del compilatore

Il modello contiene già `Relation(kind='inverse')`, con chiavi sorgente e
destinazione scambiate da `_resolve_inverse_relations`. `_Context.related`
ora accetta questo tipo e verifica l'unicità sul **lato sorgente** della
relazione inversa. Sul lato destinazione possono esserci più righe.
Per le relazioni forward resta il controllo sul target.

Rimangono gli stessi algoritmi di allocazione degli alias, uguaglianza delle
coppie di chiavi, riuso dei JOIN, espansione delle formule e binding. Nessun
nuovo mangler o percorso speciale per le gerarchie. Chiavi fisiche composte
continuano a produrre condizioni AND; chiavi mancanti o non uniche sul lato
one rimangono errori. virtualRelation e JOIN nelle scritture restano esclusi.

Una sottoquery gerarchica mantiene il JOIN nel suo scope e conta i figli
diretti; non moltiplica le righe della SELECT esterna. Una proiezione diretta
`@_children.id` restituisce invece le righe del LEFT JOIN. Se non ci sono figli,
il valore proiettato è NULL. `COUNT(@_children.id)` con GROUP BY restituisce
zero; un COUNT(*) sul solo LEFT JOIN avrebbe invece semantica diversa.
La formula legacy contiene il filtro correlato: non è stata riscritta.

## Verifiche

- Quattro test portati da `test_compiler_coverage.py`: due di navigazione
  one-to-many e due di riuso dello stesso percorso. Prima: **4 fallimenti**
  per navigazione inversa non supportata. Dopo: **4 superati**. Le asserzioni
  sono invariate; solo i due test fast-path esplicitano gli alias del risultato.
  Il loro controllo sui valori non prova l'aggregazione runtime legacy.
- Provenienza, hash AST e riferimenti con corpi identici:
  `tests/native_formulas/legacy-inverse-relations-manifest.json`.
  I test `TestDistinctExploding` non sono dichiarati portati: riguardano
  DISTINCT implicito, colonne nascoste e conteggio delle pkey.
- **17 verifiche di compilazione**: nessuna connessione/esecuzione, riuso fra
  SELECT/WHERE/ORDER/GROUP/HAVING, alias, percorsi inversi seguiti da forward,
  più relazioni verso la stessa tabella, scope delle sottoquery, formule con
  locali omonimi, chiavi composte e errori espliciti.
- **20 verifiche sui dati**, PostgreSQL e SQLite: tutte e cinque le tabelle
  native, senza cambiare la source o le formule. Radici, fratelli, nipoti,
  foglie, riferimenti a un genitore assente e autorelazioni. Confronto con
  conteggi calcolati dai record, filtri/ordinamenti, COUNT su GROUP BY,
  figli NULL, moltiplicazione delle righe, DISTINCT e count espliciti.

Le cinque formule sbloccate sono `child_count` su **sys.widget, adm.htag,
adm.menu, invc.product_group, invc.product_type**. La sonda dei 74 modelli
passa da 455 a **460/462 formulaColumn**; gli alias restano **45/46**.
Restano una formula con `#PREF`, una con `env_user_id` assente nella sonda e
l'alias su virtualRelation, oltre alle altre famiglie ancora aperte.
Il successo della sonda non certifica tutti i risultati del modello nativo.

Esiti della suite e controlli statici nelle
[evidenze](evidence/native-inverse-relations/results.json); dettaglio delle
colonne nel [censimento](evidence/native-inverse-relations/coverage.json).
Suite completa: **1633 superati, 9 saltati**; Ruff, mypy e Sphinx verificati.
