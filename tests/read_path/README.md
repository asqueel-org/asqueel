# Verifica del percorso unico delle letture

Dalla radice del repository:

```sh
PYTHONPATH=src python -m pytest @tests/read_path/pytest.args --no-cov
```

Servono le dipendenze dev pubblicate e PostgreSQL locale, configurabile con
`ASQUEEL_TEST_DSN` o `GNR_TEST_PG_*` come nelle altre suite. SQLite usa i database
temporanei dei test. Nessun repository migration locale è necessario.

Il file args raccoglie tutta `tests` e separa esplicitamente i test che dipendono
dalle scritture, ancora di competenza dell'altra sessione. Non è la verifica della
release integrata e non cambia la raccolta pytest predefinita. Dopo il raccordo
scritture va eseguita l'intera suite senza queste esclusioni.

I test DML nei file misti restano invariati. Le asserzioni legacy originali sulle
formule sono nei moduli `tests/native_formulas/legacy_*.py` e vengono invocate
attraverso le fixture del percorso unico; gli oracoli JSON restano invariati.

Vedere `docs/design/98-single-read-path.md` per la mappa della copertura e
`docs/design/97-read-write-contracts.md` per i contratti condivisi.
