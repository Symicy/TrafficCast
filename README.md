# TrafficCast — Predicția traficului rutier

TrafficCast este un prototip IoT pentru monitorizarea și predicția vitezei traficului rutier. Proiectul redă măsurători istorice ca un flux de date în timp aproape real, transmite valorile prin MQTT, stochează datele și predicțiile și le afișează într-un dashboard.

Componenta experimentală investighează efectul indisponibilității senzorilor asupra preciziei predicțiilor și măsoară în ce măsură completarea valorilor lipsă folosind informații de la senzorii învecinați poate reduce degradarea rezultatelor.

Aplicația va include și un **asistent conversațional AI**, care va răspunde în limba română la întrebări despre valorile măsurate, predicții și alerte. Asistentul va folosi instrumente controlate pentru a accesa datele aplicației, în loc să inventeze valori. Această funcționalitate este o extensie a aplicației; cercetarea principală rămâne evaluarea predicțiilor în condiții de indisponibilitate a senzorilor.

## Cuprins

- [Echipa](#echipa)
- [Scenariul IoT](#scenariul-iot)
- [Arhitectura sistemului](#arhitectura-sistemului)
- [Întrebarea de cercetare](#întrebarea-de-cercetare)
- [Ipoteze](#ipoteze)
- [Soluții de referință](#soluții-de-referință-baseline)
- [Abordarea propusă](#abordarea-propusă)
- [Asistent conversațional AI](#asistent-conversațional-ai)
- [Plan experimental](#plan-experimental)
- [Tehnologii propuse](#tehnologii-propuse)
- [Structura repository-ului](#structura-propusă-a-repository-ului)
- [Cum se rulează](#cum-se-rulează)
- [Rezultate](#rezultate)
- [Limitări](#limitări)
- [Bibliografie și resurse](#bibliografie-și-resurse)

## Echipa

- Student 1: Avram Darius        
- Student 2: Vancea Paul
- Student 3: Sima Alin

## Scenariul IoT

### Sistemul simulat

Proiectul simulează o rețea de drumuri monitorizată de senzori care măsoară viteza traficului. Un script de redare publică periodic măsurătorile istorice ca mesaje MQTT, ca și cum acestea ar proveni de la senzori activi. Datele sunt apoi validate, stocate și folosite pentru a genera predicții.

Nu este necesară conectarea la senzori rutieri fizici. Dacă Raspberry Pi este disponibil, acesta poate rula scriptul de redare; în timpul dezvoltării, aceeași componentă poate fi executată local.

### Setul de date

- **Set de date:** [PEMS-BAY — repository-ul DCRNN](https://github.com/liyaguang/DCRNN)
- **Sursa datelor:** sistemul Caltrans Performance Measurement System (PeMS)
- **Acoperire:** măsurători de viteză de la 325 de senzori rutieri din zona golfului San Francisco
- **Rezoluție temporală:** 5 minute
- **Perioadă:** aproximativ șase luni din anul 2017
- **Parametru principal:** viteza traficului

Setul original poate fi distribuit în formate precum HDF5. Datele vor fi citite direct sau convertite într-un format potrivit simulatorului, de exemplu CSV. Formatul final și pașii de descărcare vor fi documentați după verificarea fișierelor folosite efectiv.

### Scenarii simulate

În cadrul experimentelor vor fi introduse controlat următoarele situații:

- pierderi aleatorii ale unor măsurători;
- indisponibilitatea temporară a unor senzori;
- indisponibilitatea continuă a unui subset de senzori;
- completarea valorilor lipsă înainte de predicție.

Aceste situații vor fi injectate artificial și nu vor fi prezentate ca defecțiuni observate în setul de date original. Pot fi adăugate și scenarii sintetice de trafic, create prin reguli sau cu ajutorul unui model AI, dar acestea vor fi etichetate separat și evaluate separat de datele reale.

## Arhitectura sistemului

Fluxul principal propus este:

```text
Setul de date PEMS-BAY
        |
        v
Preprocesare și experimente ML (Python / Google Colab)
        |
        +--> Model antrenat, exportat pentru inferență

PEMS-BAY --> replay.py pe Raspberry Pi (sau local)
        |
        v
Broker MQTT — Mosquitto (Linux)
        |
        v
Consumator / procesare date și inferență
        |
        v
SQLite — măsurători, predicții și alerte
        |
        v
Dashboard — Streamlit
        |
        +--> Asistent AI — LLM cu tool calling prin MCP
                  |
                  +--> instrumente de citire a datelor, predicțiilor și metricilor
```

### Rolul componentelor

- **`replay.py`:** citește datele istorice și le publică în MQTT la o viteză configurabilă. Modul de demonstrație poate rula mai rapid decât timpul real, păstrând timestampurile originale pentru analiza temporală.
- **Mosquitto:** broker MQTT care distribuie mesajele publicate de simulator.
- **Consumatorul de mesaje:** verifică structura mesajelor, gestionează valorile lipsă, actualizează stocarea și solicită predicții.
- **SQLite:** stochează măsurătorile recepționate, predicțiile, starea senzorilor și rezultatele necesare dashboardului.
- **Google Colab:** mediu pentru explorarea datelor, antrenarea și evaluarea modelelor. Modelul antrenat va fi exportat și încărcat de aplicație; funcționarea sistemului nu ar trebui să depindă de o sesiune Colab activă.
- **Streamlit:** dashboard pentru valorile curente din fluxul simulat, predicții, alerte și comparații experimentale.
- **Agentul LLM:** interpretează întrebările în limbaj natural și apelează instrumente specializate prin MCP. Acesta explică rezultatele furnizate de aplicație, în loc să calculeze sau să inventeze valori numerice pe cont propriu.

## Întrebarea de cercetare

**RQ:** În ce măsură indisponibilitatea temporară sau prelungită a senzorilor afectează precizia predicției vitezei traficului pentru următoarele 15, 30 și 60 de minute și în ce măsură completarea valorilor lipsă folosind informații de la senzorii învecinați reduce această degradare?

## Ipoteze

- **H1:** Creșterea proporției senzorilor indisponibili conduce la creșterea erorii predicțiilor.
- **H2:** O metodă de completare care folosește informații de la senzorii învecinați reduce eroarea față de o metodă simplă de tip *forward fill* în cel puțin unele scenarii de indisponibilitate.
- **H3:** Eficiența completării bazate pe senzorii învecinați depinde de orizontul de predicție și de tipul indisponibilității.

Ipotezele vor fi verificate prin experimente. Rezultatele nu sunt presupuse dinainte.

## Soluții de referință (baseline)

Vor fi evaluate cel puțin următoarele metode:

1. **Persistență:** predicția pentru viitor este egală cu ultima viteză disponibilă. Este o referință simplă, ușor de reprodus.
2. **Model ML cu completare simplă:** un model Random Forest antrenat pe ferestre temporale, folosind *forward fill* pentru valorile lipsă.
3. **Model ML cu completare spațio-temporală:** un model comparabil care folosește istoricul temporal și, dacă metadatele disponibile permit, măsurătorile unor senzori învecinați.

Comparația va păstra aceeași împărțire temporală a datelor și aceleași scenarii de indisponibilitate pentru metodele testate.

## Abordarea propusă

Modelul va estima viteza traficului la trei orizonturi de predicție:

- **15 minute:** 3 pași temporali;
- **30 de minute:** 6 pași temporali;
- **60 de minute:** 12 pași temporali.

Un pas temporal corespunde unei măsurători la fiecare cinci minute. Ca model ML inițial se propune **Random Forest Regressor**, comparat cu metoda de persistență. Caracteristicile pot include istoricul recent al vitezei pentru senzorul țintă, măsurători de la senzorii învecinați și caracteristici temporale precum ora zilei și ziua săptămânii.

Pentru a păstra experimentul controlabil, se va începe cu un subset de senzori reprezentativi. Extinderea la întreaga rețea va depinde de timpul și resursele disponibile. Se va analiza separat efectul modelului de predicție și efectul metodei de completare a valorilor lipsă, pentru a evita atribuirea unei îmbunătățiri unei singure componente fără dovezi.

## Asistent conversațional AI

Asistentul va fi integrat în dashboard ca interfață în limba română pentru explorarea rezultatelor TrafficCast. El nu va fi un chatbot general, ci un asistent care răspunde pe baza datelor și funcțiilor disponibile în aplicație.

### Exemple de întrebări

- „Care senzori au cele mai mari scăderi estimate în următoarele 30 de minute?”
- „Cum s-a modificat eroarea predicției când 20% dintre senzori au devenit indisponibili?”
- „Ce senzori nu au mai transmis date?”
- „Explică diferența dintre metoda de persistență și Random Forest.”
- „Care sunt limitele predicției afișate?”

### Funcționare propusă

- Un LLM de dimensiune redusă va interpreta întrebarea utilizatorului și va formula un răspuns în română.
- Prin **tool calling** și **MCP**, modelul va putea apela instrumente predefinite, precum citirea ultimelor măsurători, obținerea predicțiilor pentru un anumit orizont, identificarea senzorilor indisponibili și citirea metricilor experimentale.
- Instrumentele vor returna valori calculate de aplicație din baza de date sau din modelul de predicție. LLM-ul va explica rezultatul primit.
- Accesul asistentului va fi inițial doar pentru citire; nu va modifica datele și nu va schimba parametrii experimentelor.

Modelul LLM poate fi rulat local, de exemplu prin Ollama, sau accesat printr-un API, în funcție de resurse și de rezultatele testelor inițiale. Acest model este diferit de modelul ML de predicție a vitezei: primul interpretează întrebări și explică rezultate, iar al doilea estimează valorile numerice ale traficului.

Asistentul este o componentă suplimentară a aplicației. Dacă timpul este limitat, implementarea lui va începe după funcționarea fluxului MQTT, a predicțiilor și a dashboardului.

## Plan experimental

### 1. Pregătirea datelor

- Descărcarea setului PEMS-BAY și documentarea versiunii și a fișierelor folosite.
- Verificarea timestampurilor, a formatului, a valorilor lipsă și a distribuției vitezelor.
- Construirea ferestrelor de intrare din istoricul recent și a țintelor la 15, 30 și 60 de minute.
- Împărțirea datelor în seturi de antrenare, validare și testare în ordine **cronologică**, fără amestecarea aleatorie a observațiilor succesive.
- Alegerea senzorilor învecinați pe baza metadatelor disponibile; dacă relațiile spațiale nu pot fi stabilite fiabil, această parte va fi redusă sau înlocuită cu o metodă temporală documentată.

### 2. Scenarii de testare

1. **Scenariu normal:** măsurătorile disponibile sunt folosite, iar valorile lipsă originale sunt tratate într-un mod documentat.
2. **Pierderi aleatorii:** se elimină artificial o proporție configurabilă din măsurători.
3. **Indisponibilitate la nivel de senzor:** un subset de senzori nu transmite date pe o anumită perioadă.
4. **Completare comparativă:** aceleași scenarii se testează cu *forward fill* și cu metoda bazată pe senzorii învecinați.

Proporțiile inițiale de indisponibilitate pot fi 10%, 20% și 30% dintre senzori. Durata episoadelor și semințele aleatorii vor fi configurate și documentate, astfel încât scenariile să poată fi reproduse.

### 3. Variabile controlate

- aceleași perioade de antrenare, validare și testare;
- aceiași senzori și aceleași orizonturi în comparațiile directe;
- aceleași măști de valori lipsă pentru metodele comparate;
- aceleași setări de preprocesare și aceeași procedură de evaluare;
- aceeași configurație hardware și software pentru măsurarea timpului de execuție;
- aceleași semințe aleatorii acolo unde se folosesc operații aleatorii.

Completarea valorilor, normalizarea și orice alt pas care învață parametri din date vor fi ajustate folosind doar setul de antrenare, pentru a preveni scurgerea de informații din setul de test.

### 4. Metrici de evaluare

**Predicția traficului:**

- **MAE** — eroarea absolută medie;
- **RMSE** — rădăcina erorii pătratice medii;
- **degradarea relativă a erorii** față de scenariul normal;
- rezultate separate pentru orizonturile de 15, 30 și 60 de minute.

**Funcționarea sistemului, dacă poate fi măsurată reproductibil:**

- latența de generare a predicțiilor;
- volumul mesajelor transmise prin MQTT;
- utilizarea CPU și RAM;
- latența răspunsurilor asistentului AI și corectitudinea instrumentelor apelate, pentru un set fix de întrebări de test.

MAE și RMSE vor fi raportate în unitatea folosită de setul de date. Dacă valorile sunt convertite în km/h pentru afișare, conversia va fi documentată și aplicată consecvent.

### 5. Analiza rezultatelor

Rezultatele vor fi prezentate prin tabele și grafice care compară metodele și scenariile. Se va urmări modificarea erorii în raport cu proporția și durata indisponibilității senzorilor și cu orizontul de predicție. Concluziile vor preciza în ce condiții abordarea propusă ajută și unde avantajul nu este semnificativ.

Dacă este evaluat asistentul conversațional, se va folosi un set fix de întrebări cu răspunsuri verificabile. Rezultatele acestui test vor fi raportate separat de experimentul principal de predicție.

## Tehnologii propuse

- **Limbaj și preprocesare:** Python, pandas, NumPy
- **Redarea datelor:** Python (`replay.py`), Raspberry Pi sau mediu local de dezvoltare
- **Comunicare IoT:** MQTT, Mosquitto
- **Machine Learning:** scikit-learn
- **Antrenare și analiză:** Google Colab, Jupyter Notebook
- **Stocare:** SQLite
- **Dashboard:** Streamlit
- **Asistent conversațional:** LLM local prin Ollama sau API; tool calling și MCP
- **Controlul versiunilor:** Git
- **Orchestrare opțională:** Docker Compose, dacă simplifică pornirea serviciilor

Tehnologiile pot fi simplificate în funcție de timpul disponibil. Prioritatea este un experiment reproductibil, nu folosirea unui număr cât mai mare de instrumente.

## Structura propusă a repository-ului

```text
TrafficCast/
├── data/
│   ├── raw/                  # Datele originale; fișierele mari nu se comit în Git
│   └── processed/            # Date preprocesate
├── notebooks/                # Analiză și experimente în Python / Colab
├── models/                   # Artefacte ML exportate; nu se versionază fișierele mari
├── src/
│   ├── simulator/            # replay.py și redarea măsurătorilor
│   ├── mqtt/                 # Publicare, consum și validare de mesaje
│   ├── preprocessing/        # Ferestre temporale și tratarea valorilor lipsă
│   ├── prediction/           # Baseline, model ML și inferență
│   ├── experiments/          # Scenarii de indisponibilitate și evaluare
│   ├── assistant_mcp/        # Instrumente MCP pentru asistentul AI
│   └── dashboard/            # Interfața Streamlit
├── results/
│   ├── figures/              # Grafice generate de experimente
│   └── tables/               # Tabele cu metrici
├── tests/                    # Teste automate
├── .env.example
├── requirements.txt
└── README.md
```

Structura este orientativă și poate fi modificată pe parcursul implementării. Datele brute, cheile API și artefactele mari nu trebuie încărcate în repository.

## Cum se rulează

Comenzile exacte vor fi completate după implementarea și testarea primei versiuni. Fluxul de reproducere planificat este:

1. Instalarea dependențelor Python.
2. Descărcarea setului PEMS-BAY și pregătirea fișierelor locale.
3. Preprocesarea datelor și antrenarea/evaluarea inițială a modelelor.
4. Exportarea modelului selectat pentru utilizare de către aplicație.
5. Pornirea brokerului Mosquitto și a simulatorului `replay.py`.
6. Pornirea consumatorului MQTT, a stocării și a componentei de predicție.
7. Pornirea dashboardului Streamlit și verificarea măsurătorilor și predicțiilor.
8. Opțional, configurarea LLM-ului și pornirea serverului MCP pentru asistentul conversațional.
9. Executarea scenariilor experimentale și generarea tabelelor și graficelor.

Această secțiune descrie fluxul planificat, nu comenzi pentru o implementare deja finalizată.

## Rezultate

**De completat după rularea experimentelor.** Secțiunea va include:

- MAE și RMSE pentru toate orizonturile de predicție;
- comparația dintre metoda de persistență și modelele ML;
- comparația dintre metodele de completare a valorilor lipsă;
- grafice ale erorii în funcție de proporția și durata indisponibilității senzorilor;
- măsurători operaționale, dacă sunt colectate;
- interpretarea rezultatelor în raport cu ipotezele H1–H3.

Nu vor fi introduse rezultate estimate sau generate înainte de executarea experimentelor.

## Limitări

- Datele provin dintr-o anumită regiune și din anul 2017; performanțele nu sunt garantate pentru alte orașe sau condiții actuale.
- Indisponibilitatea senzorilor este simulată și nu reproduce toate cauzele și efectele unei defecțiuni reale.
- Redarea datelor istorice ca flux nu echivalează cu testarea pe senzori fizici în trafic real.
- Dacă experimentele folosesc doar un subset de senzori, concluziile se referă în primul rând la acel subset.
- Predicția vitezei nu reprezintă, prin ea însăși, o predicție a accidentelor sau o estimare directă a timpului de călătorie.
- Utilitatea informațiilor de la senzorii învecinați depinde de disponibilitatea unor metadate sau relații spațiale adecvate.
- Răspunsurile asistentului AI depind de calitatea instrumentelor și de datele disponibile. Pentru evitarea răspunsurilor nesusținute, valorile numerice trebuie preluate din instrumentele aplicației și nu inventate de LLM.
- Datele generate artificial, dacă vor fi folosite, vor fi delimitate de setul real și nu vor înlocui testarea principală pe date reale.

## Bibliografie și resurse

1. **PEMS-BAY / DCRNN:** [Repository-ul proiectului DCRNN](https://github.com/liyaguang/DCRNN)
2. Li, Y. et al., **„Diffusion Convolutional Recurrent Neural Network: Data-Driven Traffic Forecasting”**, ICLR 2018: [arXiv:1707.01926](https://arxiv.org/abs/1707.01926)
3. **Caltrans Performance Measurement System (PeMS):** [Caltrans PeMS](https://dot.ca.gov/programs/traffic-operations/mpr/pems-source)
4. **MCP — Model Context Protocol:** [Documentația oficială](https://modelcontextprotocol.io/)

---

**Stadiu:** propunere inițială. Întrebarea de cercetare, scenariile și tehnologiile pot fi ajustate în funcție de cerințele cadrului didactic și de analiza inițială a setului de date.
