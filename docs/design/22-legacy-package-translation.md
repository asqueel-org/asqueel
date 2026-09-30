# 22 — Package legacy e dichiarazioni Python del modello

Attività collaterale richiesta dall'utente. Stato: requisito registrato e prima
ipotesi di progetto; nessuna sintassi pubblica di importazione o collocazione
fisica della configurazione è decisa. La priorità principale rimane il nucleo DB.

## Chiarimento: package come sottoapplicazione

Il package Genropy è una sottoapplicazione che contribuisce a SQL, GUI e altri
ambiti. Un contributo SQL non esaurisce quindi il concetto di package. Asqueel
deve offrire un punto di composizione che il futuro livello applicativo possa
usare per collegare la parte SQL di una sottoapplicazione, senza richiedere al
nucleo DB di conoscere GUI o altri servizi.

Proposta dell'utente: nella configurazione, raggiunto l'elemento `db`, poter
importare opzionalmente contributi forniti da package. Questi usano le grammatiche
esistenti per dichiarare schemi, tabelle, colonne e gli altri elementi SQL.
Le dichiarazioni dirette del DB e quelle importate devono partecipare alla
stessa costruzione del modello. Il contributo può essere fornito da un normale
modulo Python autonomo o dalla parte SQL di una sottoapplicazione più ampia.

La direzione da esplorare è quindi **DB → contributi SQL importati → grammatica
del modello**, non una nuova identità obbligatoria fra package e schema SQL.
La scelta del punto di ingresso Python, della sintassi nella grammatica e delle
regole di composizione resta da verificare con il prototipo.

## Obiettivo

Prendere un package del vecchio Genropy e produrre una dichiarazione Python
leggibile e modificabile del modello SQL nuovo, accompagnata da un rapporto
delle parti tradotte, delle dipendenze e delle parti ancora da adattare.
L'output richiesto è sorgente dichiarativo riutilizzabile, non soltanto un
modello risolto in memoria o una fotografia dello schema PostgreSQL.

L'importatore presente in `src/asqueel/importers.py` riguarda il catalogo
PostgreSQL. Recupera struttura fisica; non equivale a tradurre un package con
nomi logici, formule, relazioni e metadati. Il lavoro si collega a F2 e anticipa
una parte di F9, senza anticipare l'intera integrazione applicativa di F8/F9.

## Ipotesi di equivalente Pythonico, da verificare

La parte SQL di una sottoapplicazione, oppure un modulo Python autonomo, può
fornire un contributo al modello:
identità logica, dichiarazioni di tabelle, dipendenze e, dove supportati,
comportamenti Python delle tabelle. La configurazione del DB seleziona i
contributi opzionali; il livello applicativo potrà coordinarne la selezione con
quella delle altre parti della sottoapplicazione. Come completarli o
sovrascriverli rimane una regola di composizione da definire.

Tenere distinti tre concetti durante l'analisi:

- **Distribuzione/import Python:** come il codice è installato e importato.
- **Contributo al modello:** namespace logico, tabelle, relazioni e dipendenze.
- **Configurazione dell'applicazione:** selezione e composizione dei contributi,
  override e collegamento alle connessioni effettive.

Non assumere una corrispondenza obbligatoria uno-a-uno fra package Python,
package Genropy, schema SQL e database. Il mapping di namespace, schema fisico e
prefissi deve restare esplicito. La configurazione in cascata e le grammatiche
già presenti sono il punto di partenza; non introdurre un secondo sistema di
configurazione senza una necessità dimostrata.

## Composizione SQL iniziale

L'esempio `examples/two_schemas` usa import espliciti degli schemi nella ricetta
DB e delle tabelle in ciascuno schema. Ogni tabella collega una classe `Model`
a una classe `Logic` tramite l'attributo esistente `x_table_class`. Le due
classi possono stare nello stesso modulo o in moduli differenti. La discovery
nelle cartelle è rinviata. Queste classi dichiarative sono convenzioni
nell'esempio, non nuove classi base obbligatorie del framework.

La [consegna 23](23-cli-and-named-configurations.md) implementa sezione
`connection`, registro locale per nome, CLI e REPL. La collocazione del modello
SQL di una sottoapplicazione completa resta distinta e aperta.

## Prima verticale

1. Scegliere un package legacy piccolo ma rappresentativo e fissarne revisione,
   dipendenze e contesto necessario alla costruzione del modello.
2. Censire cosa proviene da dichiarazioni locali, helper, mixin, altri package
   e override dell'applicazione. Distinguere il package autonomo dal modello
   effettivo di un'applicazione che lo usa.
3. Confrontare estrazione statica e costruzione controllata del modello legacy:
   la prima può perdere dichiarazioni dinamiche, la seconda richiede dipendenze
   e può eseguire codice applicativo. Scegliere sulla base del campione; non
   promettere una traduzione generale tramite semplice parsing del sorgente.
4. Generare una dichiarazione attraverso la grammatica nativa esistente,
   conservando provenienza, nomi logici/fisici, chiavi, tipi, relazioni e metadati
   supportati. Segnalare formule, hook, helper e riferimenti esterni non tradotti
   senza eliminarli silenziosamente o produrre implementazioni fittizie.
5. Caricare il sorgente generato nel nuovo Asqueel e confrontare il modello
   risolto con il riferimento; compilare query rappresentative e verificarle su
   un PostgreSQL isolato. Nessuna migrazione o modifica dei dati di origine.

## Decisioni da maturare con il prototipo

- Forma pubblica del contributo: modulo, funzione dichiarativa, classe o altro
  punto di ingresso coerente con i builder esistenti.
- Sintassi degli import opzionali sull'elemento `db` e contesto passato al
  contributo; uso della stessa grammatica delle dichiarazioni locali.
- Posizione della configurazione e collegamento tra identità del package,
  namespace del modello e configurazione applicativa.
- Dichiarazione delle dipendenze, ordine di composizione e conflitti/override.
- Rappresentazione delle estensioni a tabelle appartenenti ad altri package.
- Separazione tra struttura traducibile e metodi/hook che richiedono porting.
- Strategia di rigenerazione che non sovrascriva modifiche manuali all'output.

## Criterio di uscita della prima verticale

Un package reale produce sorgente Python caricabile, senza dipendenza runtime
da Genropy per la parte tradotta; generazione deterministica a parità di input;
confronto strutturale e query verificati; rapporto puntuale dei limiti e delle
dipendenze irrisolte. Le scelte di packaging/configurazione sono esplicitate e
discusse prima di diventare API pubblica. Non si dichiara tradotto l'intero
package se restano comportamenti applicativi non convertiti.
