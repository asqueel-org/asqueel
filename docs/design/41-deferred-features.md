# 41 — Funzionalità rinviate

Aggiornato il **12 ottobre 2026**. Registro dei rinvii esplicitamente decisi
durante la definizione del core. Il rinvio non è una rimozione definitiva.
Le funzionalità ancora da discutere o da implementare non entrano in questo
elenco automaticamente: restano nei rispettivi contratti e piani.

## R-01 — `toolColumn`

**Decisione:** omessa per ora dalla grammatica obiettivo e dal lavoro corrente
sul modello, su indicazione dell'utente del 12 ottobre 2026.

**Funzione nel legacy:** colonna virtuale che costruisce un collegamento a uno
strumento associato al record. Una formula SQL genera HTML con un URL della
forma `<external_host>/_tools/<tool>?record_pointer=<record_pointer>`:
un elemento `<a>` con testo o icona, oppure `<img>` per `dtype='P'`.

**Riferimenti verificati:** repository GenroPy,
`gnrpy/gnr/sql/gnrsqlmodel/model.py`, metodo `toolColumn`, e
`gnrpy/gnr/sql/gnrsqlmodel/helpers.py`, funzione `toolFormula`.
La [revisione comparativa](../review/asqueel-vs-genropy-it.html) registra un
uso applicativo; la [proposta 0001](../proposals/0001-model-and-expressions.md)
ne riportava il contratto come aperto.

**Alla ripresa:** decidere se conservare la forma legacy o descrivere nel
modello il riferimento allo strumento e affidare l'HTML alla UI. Quest'ultima
è una possibilità discussa, non una soluzione approvata. Nessun adapter o
comportamento sostitutivo è stato deciso con questo rinvio.
