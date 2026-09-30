# Allineamento al remoto e all'ecosistema — 29 settembre 2026

Aggiornamento successivo: il [rapporto V1 nativo](native-v1-delivery.md) verifica
il migratore pubblicato su PyPI 0.1.0 e supera i precedenti expected failure.
Il testo seguente conserva la baseline storica, non lo stato corrente.

## Base e perimetro

Questo intervento parte da `origin/main` a `64e53af`, che contiene la pipeline
SQL canonica del 24 agosto. Il precedente branch `codex/ecosystem-alignment`
partiva dal checkout arretrato `cdfddce`: rimane conservato, ma non viene
integrato e le sue analisi non descrivono lo stato corrente del remoto.

Sono preservati grammatica unica, validatori, proiezione migration, reader,
emitter Python, catalogo e collezioni esplicite. Non vengono ripristinati
LegacySqlBuilder, i package legacy/modern o i loro esempi.

## Correzioni

- Catalogo: sostituita l'API Bag rimossa `walk()` con la query pubblica
  `query("#p,#n", deep=True, iter=True)`, conservando ordine e percorsi.
- Documentazione: lettura delle docstring tramite `inspect.getdoc` della
  funzione dichiarativa, mantenendo descrizioni dei parametri e distinzione
  fra piano fisico e semantico sotto Builders 0.27. Il documento generato
  precedente torna a coincidere senza perdere testo o riscriverlo a vuoto.
- Packaging: Python minimo 3.11, Builders >=0.27.0, Bag >=0.27.0 dichiarato
  direttamente perché importato dal package; reference della grammatica
  inclusa nel wheel e disponibile anche fuori dal checkout.
- Renderer DDL diretto ancora non implementato: mode SQL esplicito e relativo
  test negativo. La proiezione migration resta il percorso operativo.
- Profili completi e riproducibili, script per testare il wheel fuori dal
  checkout, CI e controllo separato del runtime senza migratore.

## Versioni verificate

Builders 0.27.0, Bag 0.27.0, TYTX 0.16.0, Toolbox 0.14.0; Routes 0.30.0 e ASGI
0.46.3 nei profili dedicati. Python 3.11, 3.12 e 3.13. Il migratore opzionale,
non pubblicato su PyPI, è installato dal commit pubblico completo
`e64fa00b22b304263f515765bb44e5b74d9e9534`, fissato nei profili di test.

## Verifiche locali

| Verifica | Risultato |
|---|---|
| Wheel, core Python 3.11 / 3.12 / 3.13 | 117 passati, 1 xfail upstream, 6 PostgreSQL esclusi per ciascun ambiente |
| Wheel con Routes, Python 3.12 | 117 passati, 1 xfail upstream, 6 PostgreSQL esclusi |
| Wheel con ASGI + Routes, Python 3.12 | 117 passati, 1 xfail upstream, 6 PostgreSQL esclusi |
| Wheel, suite completa su PostgreSQL 17 dedicato | 122 passati, 2 xfail upstream |
| Core senza migratore installato | Costruzione, validazione, emissione Python e ricostruzione riuscite |
| Ruff, mypy, check delle dipendenze | Superati |
| sdist → wheel, py.typed e reference inclusi | Superati |

Copertura misurata: 97%. La matrice locale è stata eseguita su macOS con
ambienti separati, non sul Python globale. I test PostgreSQL hanno usato
un'istanza temporanea sulla porta 55439, distinta da eventuali database locali.
La CI configura una propria istanza PostgreSQL 17 su Ubuntu.

## Due limiti esterni ancora reali

Prima di classificare le regressioni note, la suite completa dava 119 passati
e 2 falliti; i tre nuovi casi di regressione portano i passati a 122.
I fallimenti sono nel migratore pubblico, non sono stati corretti qui:

1. nome fisico dell'indice e introspezione DESC (`asqueel-migration#8`);
2. quoting degli identificatori: manca `writer.quote_identifier`.

I test originali continuano a eseguire le proprie asserzioni. Sono xfail strict
solo per il SHA pubblico fissato e solo quando tipo e messaggio dell'eccezione
corrispondono al difetto riprodotto. Altri errori falliscono normalmente;
un passaggio inatteso è un errore. Un altro commit o un checkout editable del
migratore non riceve queste aspettative. `pytest --runxfail` le disattiva.

Non è quindi certificata la correttezza degli indici nei due casi sopra. Non
sono stati introdotti workaround nel codice SQL né modificate le implementazioni
dei writer. La chiusura definitiva richiede le correzioni upstream descritte in
[delivery.md](delivery.md), poi l'aggiornamento del pin e la rimozione degli xfail.

Routes/ASGI sono verificati per coinstallazione, import e suite SQL; non si
estende questo risultato al comportamento di un server ASGI.
