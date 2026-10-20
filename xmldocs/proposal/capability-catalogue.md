<!-- generated from capability-catalogue.xml by xmldocs: do not edit, edit the XML -->

## Catalogo delle capability dei dialetti
*Proposal · proposal/capability-catalogue · 2026-10-20 · draft*

### Problem

I dialetti SQL non offrono le stesse funzioni. PostgreSQL ha RETURNING, `FOR UPDATE` con le sue varianti, `jsonb_agg`, `xmlagg`, `tsvector`, gli indici gin, gli schemi e `LISTEN`/`NOTIFY`. SQLite ne ha una parte.

Quando un utente chiede una funzione che il dialetto non ha, deve ricevere un errore. L'errore deve nominare la funzione mancante. Non deve essere un errore generico del driver o un `KeyError`.

Serve quindi un elenco delle capability. Ogni dialetto dichiara quelle che ha. Questo documento propone l'elenco e il modo di usarlo. Va discusso prima dell'implementazione.

### Current state

#### GenroPy

Fonte: il ramo `origin/develop` della repo genropy al commit `5c72f3fbd7` del 2026-10-19. I file citati sono sotto `gnrpy/gnr/`.

- `READ` `sql/__init__.py:14` · 2026-10-20 — GenroPy definisce l'enum `AdapterCapabilities` con quattro valori: `MIGRATIONS`, `VECTOR`, `SCHEMAS`, `ADMINISTER`.
- `READ` `sql/adapters/_gnrbaseadapter.py:343` · 2026-10-20 — L'adapter base offre due metodi di classe: `has_capability(capability)` e `not_capable(capability)`. Leggono l'insieme `CAPABILITIES` della classe, vuoto nell'adapter base.

*Capability dichiarate dagli adapter GenroPy*

| Adapter | CAPABILITIES | Fonte |
|---|---|---|
| PostgreSQL | `MIGRATIONS`, `VECTOR`, `SCHEMAS` | `sql/adapters/_gnrbasepostgresadapter.py:114` |
| SQLite | `SCHEMAS` | `sql/adapters/gnrsqlite.py:56` |
| MySQL | `SCHEMAS` | `sql/adapters/gnrmysql.py:64` |
| SQL Server | `SCHEMAS` | `sql/adapters/gnrmssql.py:115` |

- `READ` `db/cli/gnrmigrate.py:199` · 2026-10-20 — Il comando di migrazione controlla `MIGRATIONS` e termina con un errore se l'adapter non la dichiara.
- `READ` `sql/gnrsqlmodel/table.py:176` · 2026-10-20 — Il nome SQL completo di una table usa lo schema solo se l'adapter dichiara `SCHEMAS`.

Nessun adapter dichiara `ADMINISTER`, e nessun codice sotto `gnrpy/gnr/` la legge.

- `READ` `sql/adapters/gnrsqlite.py:61` · 2026-10-20 — GenroPy ha anche capability fuori dall'enum: l'attributo di classe `allowAlterColumn`, `True` nell'adapter base e `False` in SQLite, letto da `sql/gnrsqlutils.py:319`.

Le altre differenze tra dialetti non hanno una capability. Un adapter che non implementa un metodo solleva `AdapterMethodNotImplemented`, che non nomina la funzione chiesta dall'utente.

### Proposed solution

Il catalogo elenca le capability per tema. Ogni dialetto dichiara l'insieme delle capability che ha. Quando una richiesta usa una capability che il dialetto non dichiara, asqueel solleva un errore che nomina la capability. L'errore arriva prima di inviare SQL al database.

Il catalogo parte dai quattro valori GenroPy e li conserva con lo stesso nome. Aggiunge una capability per ogni funzione di dialetto dei temi qui sotto.

#### Query

- RETURNING su INSERT, UPDATE e DELETE.
- `FOR UPDATE` e le sue varianti: `NOWAIT`, `SKIP LOCKED`, `FOR SHARE`, `FOR NO KEY UPDATE`, `FOR KEY SHARE`.
- Aggregati JSON (`jsonb_agg`, `json_agg`) e XML (`xmlagg`).
- Ricerca full-text con colonne `tsvector`.
- Vettori: corrisponde a `VECTOR` di GenroPy.

#### Schema

- Schemi SQL: corrisponde a `SCHEMAS` di GenroPy.
- ALTER COLUMN: corrisponde a `allowAlterColumn` di GenroPy.
- Foreign key deferrable.
- Metodi di indice oltre al default, per esempio gin. Una colonna TSV con indice gin è rifiutata sui dialetti che non dichiarano le due capability.

#### Migrazione

- Migrazione del database: corrisponde a `MIGRATIONS` di GenroPy.

#### Amministrazione

- Operazioni di amministrazione del database: corrisponde a `ADMINISTER` di GenroPy. L'elenco delle operazioni coperte è da definire, perché in GenroPy la capability non ha usi.

#### Notifiche

- `LISTEN` e `NOTIFY` di PostgreSQL. GenroPy le espone come `listen` e `notify` dell'adapter (`_gnrbaseadapter.py:381`, `:429`). Nel catalogo sono una capability dell'adapter PostgreSQL.

- **must** — Ogni funzione che dipende dal dialetto appartiene a una capability del catalogo.
- **must** — Una richiesta che usa una capability non dichiarata dal dialetto solleva un errore che nomina la capability. L'errore non è mai un `KeyError` o un errore del driver.
- **must** — I quattro nomi GenroPy restano: `MIGRATIONS`, `VECTOR`, `SCHEMAS`, `ADMINISTER`.
- **should** — Una capability copre una funzione che l'utente può chiedere, non un dettaglio interno del compilatore.

### Decisions

- **dn-granularity** `open` — Quanto è fine una capability?
   1. **Una capability per tema**: Esempio: una sola capability per tutte le varianti di `FOR UPDATE`. L'elenco è corto. Un dialetto che ha solo una parte del tema non si può descrivere.
   2. **Una capability per funzione**: Esempio: `FOR UPDATE NOWAIT` e `FOR UPDATE SKIP LOCKED` sono due capability. L'errore nomina esattamente la funzione chiesta. L'elenco è lungo.
- **dn-declaration** `open` — Come dichiara un dialetto le sue capability?
   1. **Un insieme sulla classe dell'adapter**: Come GenroPy: un attributo di classe `CAPABILITIES` con i valori di un enum. Gli attributi separati come `allowAlterColumn` entrano nell'enum.
   2. **Una dichiarazione nella configurazione del dialetto**: L'elenco sta in un file di configurazione del dialetto, letto all'avvio. Un dialetto nuovo si aggiunge senza scrivere una classe.
- **dn-error** `open` — Come nomina la capability l'errore?
   1. **Una classe di errore dedicata**: Un'eccezione con due campi: la capability e il dialetto. Il messaggio dice, per esempio, che SQLite non ha `FOR UPDATE`.
   2. **Un errore generico di funzione non supportata**: Un solo errore per tutte le funzioni non supportate; il suo messaggio nomina la capability. Nessuna classe dedicata.

### Consequences

Ogni dialetto deve dichiarare tutte le capability del catalogo che ha. Una capability dimenticata produce un rifiuto su una funzione che il dialetto avrebbe.

Il catalogo serve anche alla proposta di traduzione con sqlglot: le funzioni che sqlglot non sa tradurre restano capability del dialetto.

### Related documents

- `proposal/sqlglot-transpilation` — Traduzione dei dialetti con sqlglot
