# 73 — Proxyclass legacy: composizione, binding e limiti

14 ottobre 2026. Indagine richiesta per capire il meccanismo esistente prima
di decidere namespace e personalizzazione della tabella Asqueel. Nessuna
modifica a renderer, compilatore, runtime o grammatica. Nessuna decisione
architetturale acquisita.

## Risultato essenziale

Le proxyclass legacy erano classi reali, poi istanziate sotto un nome del
proprietario. I loro metodi ricevevano **il proxy come self**. Il proxy web
recuperava dal proprietario gli attributi mancanti tramite __getattr__:
questo facilitava l'accesso a db, servizi e metodi della pagina, ma non rendeva
identici i due oggetti né delegava le assegnazioni.

L'idea discussa per Asqueel — logic.calculate_tax restituisce un metodo
logic_calculate_tax legato alla tabella — avrebbe invece **la tabella come
self**. Il namespace potrebbe apparire simile, ma il contratto è diverso.

## Fonti e ambiti distinti

Riferimento principale: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`, snapshot
`/tmp/asqueel-formula-baseline/legacy` già impiegato nei confronti precedenti.
Percorsi relativi a quel checkout:

| Sorgente | Ruolo |
| --- | --- |
| gnrpy/gnr/core/gnrlang.py:91 | BaseProxy generico: conserva solo main |
| gnrpy/gnr/core/gnrlang.py:386 | classMixin: compone la classe del namespace |
| gnrpy/gnr/core/gnrlang.py:503 | serializedFuncName: qualifica il nome RPC |
| gnrpy/gnr/core/gnrlang.py:529 | instanceMixin: istanzia i namespace e applica i metodi ordinari |
| gnrpy/gnr/web/gnrwebpage_proxy/gnrbaseproxy.py:10 | GnrBaseProxy: page, fallback, init ed eventi |
| gnrpy/gnr/web/gnrbaseclasses.py:39 | page_proxy e dichiarazione delle dipendenze |
| gnrpy/gnr/web/gnrwsgisite_proxy/gnrresourceloader.py:474 | sostituzione di _CURRENT_PROXY_ nelle dipendenze |
| gnrpy/gnr/web/gnrwebpage.py:299 | instantiateProxies delle pagine |
| gnrpy/gnr/web/gnrwebpage.py:1200 | risoluzione del namespace per i metodi pubblici |
| gnrpy/gnr/app/gnrapp.py:687 | composizione dell'oggetto intermedio dei metodi tabella |
| gnrpy/gnr/sql/gnrsqlmodel/obj.py:48 | applicazione finale dei mixin all'oggetto operativo |

Esiste anche un'altra classe chiamata BaseProxy in gnr/web/gnrbaseclasses.py:
non è la base usata di default da classMixin. La base generica è quella di
gnrlang; le pagine impostano esplicitamente proxy_class = GnrBaseProxy.

## 1. Come viene scelto il namespace

classMixin legge prima `proxy_name`; nel riferimento attuale, se manca o è
falsy, accetta anche `proxy`:

```python
class Component:
    proxy = 'logic'

    def calculate_tax(self, amount):
        ...
```

`proxy = True` ricava il nome dalla classe in minuscolo. La forma importata
`'modulo:Classe AS logic'` assegna proxy_name alla classe sorgente e richiede
la presenza del marcatore is_proxy. Il decoratore web @page_proxy mette quel
marcatore: **da solo non seleziona un namespace**. Questo comportamento è
riprodotto nelle sonde; non va dedotto dal nome del decoratore.

Queste sono sintassi osservate nel legacy, non aggiunte alla grammatica Asqueel.

## 2. Composizione della classe

Quando il namespace è logic, classMixin cerca `logic_proxyclass` sulla classe
destinazione. Se non esiste, clona la base `target.proxy_class`, oppure il
BaseProxy generico. Copia quindi i metodi nella classe del proxy, anziché nella
classe principale. Non rende la classe sorgente una base Python del proxy:
è composizione tramite copia dei membri, non normale ereditarietà multipla.

Contributi successivi allo stesso namespace vengono applicati alla stessa
proxyclass. Quando un metodo viene sostituito nella classe, il precedente
viene conservato come `nome_`. I metodi ricevono anche attributi di provenienza
e proxy_name, usati per l'indirizzamento delle chiamate pubbliche.

Dopo classMixin esiste la classe `logic_proxyclass`, ma non ancora l'oggetto
`logic`. L'istanza viene creata nel passaggio successivo.

## 3. Creazione degli oggetti

instanceMixin trova gli attributi del sorgente che terminano con _proxyclass e,
per ciascuno, esegue sostanzialmente:

```python
owner.logic = Source.logic_proxyclass(owner)
```

Per i metodi ordinari, invece, continua a usare MethodType(method, owner).
I due percorsi sono distinti: **un metodo ordinario riceve owner come self;
un metodo della proxyclass riceve owner.logic**.

Le pagine dispongono anche di instantiateProxies, che crea i namespace dalle
proxyclass raccolte sulla classe della pagina. Viene richiamato durante la
costruzione della pagina; la sonda usa quel metodo originale senza avviare
un server o una sessione web.

## 4. Due basi con comportamenti diversi

| Aspetto | BaseProxy generico | GnrBaseProxy web |
| --- | --- | --- |
| Proprietario | self.main | self.page |
| self nei metodi locali | Proxy | Proxy |
| Attributo mancante | AttributeError | getattr(self.page, name) |
| Assegnazione self.x | Sul proxy | Sul proxy |
| Inizializzazione | Salva main | Salva page, registra event_*, chiama init |

Per il proxy web il fallback è:

```python
def __getattr__(self, name):
    return getattr(self.page, name)
```

Quindi self.db può funzionare perché db viene dalla pagina. Ma ci sono due
binding differenti nelle chiamate:

```text
self.metodo_del_proxy()   → self del metodo chiamato = proxy
self.metodo_della_pagina() → self del metodo chiamato = pagina
```

Nel secondo caso getattr restituisce il metodo già legato alla pagina.
L'oggetto non viene trasformato nel proprietario e non c'è un fallback globale
fra namespace: viene consultata specificamente la pagina, quando il lookup
locale del proxy fallisce.

## 5. Letture e scritture non sono simmetriche

Caso riprodotto sulle classi originali:

```python
page.counter = 0
# Nel metodo del proxy:
self.counter += 1

assert page.counter == 0
assert page.logic.counter == 1
```

La lettura iniziale trova counter sulla pagina; l'assegnazione crea counter sul
proxy. Da quel momento prevale il valore locale. Non esiste __setattr__ che
inoltri automaticamente la scrittura.

Con un oggetto mutabile recuperato dalla pagina, invece, si modifica proprio
quell'oggetto condiviso: `self.shared['changed'] = True` cambia il dizionario
page.shared. Questo comportamento è verificato separatamente e non significa
che tutto lo stato del proxy sia condiviso.

## 6. Esempio reale ritrovato ed eseguito

La pagina `projects/gnrcore/packages/test15/webpages/tools/dynamic_proxy.py`
richiede:

```python
py_requires = 'test_proxy:Leonard AS leo'
```

Nelle risorse dello stesso package:

```python
@page_proxy(inherites='test_proxy:BigBangProxy')
class Leonard(BaseComponent):
    def makeBox(self, pane):
        pane.div('Hello everybody')
```

BigBangProxy fornisce fakeLaugh. Il decoratore converte inherites in una
dipendenza `... AS _CURRENT_PROXY_`; il resource loader sostituisce il segnaposto
con leo, facendo confluire i contributi nella stessa proxyclass.

La sonda importa le vere risorse, usa classMixin, il vero iteratore delle
dipendenze e GnrWebPage.instantiateProxies. Solo currentSite è sostituito con
un contesto locale minimo e pane è un registratore di chiamate:

```python
page.leo.makeBox(pane)  # produce Hello everybody
page.leo.fakeLaugh()   # produce AH AH AH
```

Verificato anche serializedFuncName(page.leo.callPenny) == 'leo.callPenny'.
Non è stata eseguita una richiesta HTTP/RPC: è verificata la composizione
locale e il nome serializzato, non l'intera infrastruttura web.

Sheldon, nello stesso file di esempio, usa self.db dentro il proxy: è coerente
con il fallback del proxy web. Quel metodo eseguirebbe una query e non è stato
eseguito nella sonda offline.

## 7. Quanto era utilizzato sulle tabelle

Nel checkout esaminato gli esempi espliciti di page_proxy sono componenti web;
non sono state trovate dichiarazioni SQL equivalenti nei modelli dei package.
Il censimento dei 75 oggetti tabella di test_invoice_pg non contiene membri
*_proxyclass. L'assenza del suffisso su un'istanza, da sola, non dimostra
l'assenza di un proxy già istanziato: il dato va letto insieme al censimento
delle dichiarazioni e al percorso di composizione.

Il supporto generico può comunque funzionare su una tabella: la sonda registra
con db.tableMixin una classe già composta con logic_proxyclass e avvia il vero
modello GnrSqlDb. La tabella risultante ha table.logic.main is table, ma
**table.logic.query non esiste**, perché il BaseProxy generico non delega i
nomi mancanti. Bisogna usare table.logic.main.query oppure una base specifica.

C'è un limite importante nel normale percorso applicativo a due stadi:

1. GnrPackage.loadTableMixinDict applica instanceMixin a un GnrMixinObj
   intermedio;
2. quel mixin viene registrato nel modello;
3. DbModelObj.init lo applica alla SqlTable definitiva.

Se il primo passaggio riceve una classe con logic_proxyclass, crea logic
sull'oggetto intermedio e non conserva la classe sotto logic_proxyclass.
Il secondo instanceMixin, normalmente callable-only, non copia l'istanza logic.
La sonda riproduce entrambi i passaggi con GnrMixinObj e il vero startup della
tabella: logic è presente sull'intermedio e assente sulla tabella finale.
Questo è un limite dimostrato del percorso, non la prova di un guasto osservato
in un'applicazione che lo usava; nei modelli esaminati non è stato trovato tale uso.

Non confondere questa famiglia con `hierarchicalHandler` e `xtd`: SqlTable li
istanzia esplicitamente quando sono configurati. Conservano tblobj e db; XTDHandler
ha un proprio fallback verso la tabella estesa, non verso la tabella principale.
Sono oggetti specializzati, non prodotti del meccanismo *_proxyclass.

## 8. Altri due limiti riprodotti

- **Ricomposizione sull'istanza:** un secondo instanceMixin che porta una
  proxyclass con lo stesso nome sostituisce il proxy con una nuova istanza.
  Non fonde automaticamente i metodi dei due proxy e non preserva lo stato
  locale. La composizione dei contributi va fatta a livello di proxyclass.
- **Metadati RPC condivisi:** applicando la stessa classe sorgente con due nomi
  AS diversi, i metodi restano legati ai due proxy corretti, ma la funzione
  sottostante è condivisa. Il suo proxy_name viene sovrascritto dall'ultima
  composizione: la sonda serializza il metodo del primo proxy con il secondo
  nome. Non è stata introdotta una correzione.

Sono limiti dell'implementazione osservata, non requisiti da riprodurre in Asqueel.

## 9. Test e confronto con i branch

**16 verifiche superate:** quattro test originali TestClassMixinProxy e dodici
sonde aggiuntive, tutte eseguite contro i moduli originali. Sono assert sul
comportamento effettivo, inclusi i limiti sopra, non test di una reimplementazione.
SQL e connessioni di rete sono bloccati nelle sonde. Un warning di deprecazione
legacy getReader, nessun fallimento.

- [Sonde](probes/test_legacy_proxyclasses.py)
- [Output dei test](evidence/proxyclasses/tests.log)
- [Comando, fonti e risultati](evidence/proxyclasses/verification.json)

Confrontati staticamente anche compound, v2, v3, v3_merged, v4, simplify e next.
BaseProxy è identico negli otto snapshot. I corpi di instanceMixin differiscono
solo per le guardie della Bag nativa nel riferimento recente. classMixin aggiunge
in legacy/next il recupero di proxy e proxy=True oltre a proxy_name; nei sei
snapshot sperimentali più vecchi quel fallback manca. Le guardie Bag distinguono
legacy da next. La costruzione del proxy e il binding di self non cambiano.
[Impronte AST](evidence/proxyclasses/branch-algorithms.json). Non sono state
rieseguite le intere suite né queste sedici prove su tutti i branch.

## Implicazione per la discussione Asqueel

Il legacy offre un precedente utile per raggruppare e comporre contributi sotto
un namespace, ma il proxy web con fallback non realizza la richiesta di mantenere
self sulla tabella. Riutilizzarlo integralmente porterebbe identità e stato
separati, assegnazioni locali e i limiti di composizione verificati.

La proposta discussa resta distinta: un namespace che restituisce metodi legati
alla tabella può mantenere il medesimo self, senza dipendere dal fallback della
pagina. Qui non vengono implementati proxy, prefissi, registri o nuove regole di
override: il risultato dell'indagine serve a scegliere esplicitamente tali regole.
