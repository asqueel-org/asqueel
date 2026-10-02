# 39 — Analisi della chiave primaria nel legacy: `pkey`, `pkeyValue`, `newPkeyValue`

Stato: analisi, nessuna decisione presa. Serve a decidere come asqueel genera
la chiave primaria di un nuovo record (proposta 0001 §9).

Riferimenti: genropy `origin/develop` `5e7f02e8d774`, letto con `git show`.
Path relativi a `gnrpy/gnr/sql/` salvo indicazione. L'uso nelle applicazioni
viene dall'indice Sourcerer (`code_search_code`).

## 1. `table.pkey` e `table.pkeys`

- `pkey` è l'attributo di tabella `pkey` e nomina sempre una sola colonna
  (`gnrsqlmodel/table.py:212-213`).
- Senza `pkey` il modello scrive un log critico e restituisce `[]` per `pkeys`
  (`gnrsqlmodel/table.py:197-199`). Una `pkey` che nomina una colonna
  inesistente alza `AssertionError` (`:200-203`).
- `pkeys` restituisce le colonne membro quando la colonna pkey ha
  `composed_of`, cioè è una `compositeColumn`; altrimenti `[pkey]` (`:204-206`).
- `SqlTable.pkey` / `SqlTable.pkeys` delegano al modello
  (`gnrsqltable/columns.py:206-213`).
- Uso: `pkey` compare in 5219 file applicativi su 5720 (documento 38 §6.1).

## 2. `newPkeyValue(record=None)`

- `gnrsqltable/utils.py:75-80`: chiama solo `pkeyValue(record=record)`.
- È il punto che le tabelle ridefiniscono (sezione 5).

## 3. `pkeyValue(record=None)`

`gnrsqltable/utils.py:92-134`. Le regole si provano in quest'ordine; la prima
che si applica dà il valore.

1. **pkey composita** (`len(self.pkeys) > 1`): `compositeKey` restituisce il
   JSON tipizzato dei valori membro (`typeConverter.toTypedJSON`,
   `utils.py:81-90`).
2. **pkey numerica** (`dtype` `L`, `I`, `R`): `max($pkey)` con una query, più
   1 (`:105-109`).
3. **nessun record**: `getUuid()` (`:110-111`).
4. **`pkey_columns`** (attributo di tabella): i valori delle colonne
   indicate, uniti da `pkey_columns_joiner` (default `_`); i valori `None`
   sono saltati (`:112-118`).
5. **`__syscode`** nel record: la pkey dichiarata da `sysRecord_<code>()`, se
   c'è; altrimenti il codice completato con `_` fino a `size` quando `size` è
   fissa, oppure il codice così com'è (`:119-129`).
6. **pkey testuale** (`dtype` `T`, `A`, `C`) con `size` `'22'`, `':22'` o
   assente: `getUuid()` (`:130-134`).
- In ogni altro caso la funzione termina senza `return` e restituisce `None`.

`getUuid()` (`gnrpy/gnr/core/gnrlang.py:165-170`): UUID3 su `uuid1` e id del
thread, codificato base64 urlsafe, troncato a 22 caratteri, `-` sostituito da
`_`. Gli id contengono quindi `_` (documento 36 §7, `LIKE`).

## 4. Chi genera la pkey

| Punto | Riga | Comportamento |
|---|---|---|
| `checkPkey` all'insert | `gnrsql/write.py:153`; `gnrsqltable/record.py:620-631` | assegna solo se la pkey è `None` o `''`; se `newPkeyValue` restituisce `None` il record resta senza pkey |
| `newrecord(assignId=True)` | `gnrsqltable/record.py:161-178` | dopo i `defaultValues` e prima di `extendDefaultValues` |
| `insertMany` dell'adapter | `adapters/_gnrbaseadapter.py:826-829` | per ogni record senza pkey, prima dell'INSERT |
| import di record cluster | `gnrsqltable/serialization.py:138` | `record[pkey] or newPkeyValue(record)` |
| radice gerarchica collegata | `gnrpy/gnr/app/gnrdbo.py:591` | `newPkeyValue()` senza record |
| totalizzatori | `gnrpy/gnr/app/gnrdbo.py:2054`, `:2084` | `pkeyValue(tot_record)` come chiave del totale |
| contatori `adm.counter` | `projects/gnrcore/packages/adm/model/counter.py:181`, `:198` | chiave del contatore |
| allegati | `resources/common/gnrcomponents/attachmanager/attachmanager.py:188` | `newPkeyValue()` |
| verifica delle pkey dei sysrecord | `gnrsqltable/utils.py:64` | `pkeyValue(row)` confrontata con quella salvata |

## 5. Override nelle applicazioni (Sourcerer)

Query `def newPkeyValue` (9 moduli) e `def pkeyValue` (7 moduli), una pagina
ciascuna.

- `newPkeyValue`, 4 applicativi e 1 nel framework:
  - codice da un contatore: `erpy:model/unita_industriale.py:30`
    (`assignCounterColumn(field='codice')`, poi `record['codice']`);
  - pkey fissa per una tabella con un solo record:
    `icond:model/studio.py:61` (`'STUDIO'.ljust(22, '_')`);
  - `_` sostituito da `z` per gli import bancari:
    `erpylight:model/disposizione.py:73`, `disposizione_riga.py:68`;
  - codice casuale ripetuto finché non esiste: `genropy:model/authorization.py:72`.
- `pkeyValue`, 1 applicativo e 1 nel framework:
  - anno di lavoro: `erpy:model/plafond_esportatore.py:15`;
  - chiave costruita da gruppo, utente e tabella:
    `genropy:model/user_config.py:31`.
- `pkey_columns`: 25 file in 11 repository (documento 38 §6.1).

## 6. Difetti

- **`max + 1` senza lock** (`utils.py:105-109`): due insert concorrenti su una
  pkey numerica ottengono lo stesso valore; il secondo fallisce sul vincolo di
  chiave.
- **`insertMany` con pkey numerica** (`_gnrbaseadapter.py:826-829`): il ciclo
  calcola la pkey di tutti i record prima dell'INSERT, quindi ogni record legge
  lo stesso massimo e riceve lo stesso valore. Dedotto dalla lettura del
  codice, non eseguito.
- **`pkey_columns` salta i `None`** (`utils.py:114-118`): `('A', None, 'B')` e
  `('A', 'B', None)` danno la stessa chiave `A_B`.
- **Il valore del joiner nei dati non è controllato**: con joiner `_`, i valori
  `('A_B', 'C')` e `('A', 'B_C')` danno la stessa chiave.
- **Esito silenzioso**: una pkey testuale con `size` diversa da 22 (per esempio
  un codice `size=':10'`) senza `pkey_columns` né `__syscode` restituisce
  `None`; `checkPkey` lascia il record senza pkey e l'errore arriva dal
  database.
- **La regola 3 precede le regole 4 e 5**: `newPkeyValue()` senza record su una
  tabella con `pkey_columns` restituisce un UUID, non la chiave composta.
- **`size` letta in due modi**: `pkeycol.getAttr('size')` alla regola 5,
  `pkeycol.attributes.get('size')` alla regola 6.

## 7. asqueel oggi (`main`)

- `insert` (`src/asqueel/writes.py:69-86`) esegue l'INSERT con i valori
  passati e sovrappone al record i valori restituiti da `RETURNING`
  (`_overlay_returned`); non genera la pkey.
- La pkey può essere composta da più colonne (`table.model.pkey` è una tupla,
  `application_table.py:226-236`); la proposta 0001 §2.4 la riporta a una
  sola colonna, fisica o `compositeColumn`.
- La grammatica ha il dtype `serial` (`src/asqueel/elements.py`, `DTYPE`).

## 8. Funzioni da progettare, in sintesi

Ricavate dalle sezioni precedenti. Nessuna decisione presa.

1. Pkey generata per i tipi più comuni: UUID di 22 caratteri (testo), numero
   progressivo (numerica), valore della `compositeColumn`.
2. Pkey derivata da altre colonne (`pkey_columns`).
3. Pkey dei record di sistema (`__syscode`).
4. Punto di estensione per la tabella (oggi `newPkeyValue`), usato da 4
   applicazioni.
5. Numerazione progressiva sicura in concorrenza e nei batch.
6. Errore esplicito quando nessuna regola si applica.
7. Legame con `sys_fields` (proposta 0001 §2.6, funzione «generated primary
   key») e con `auto_counter`.
