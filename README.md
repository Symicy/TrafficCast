# TrafficCast — Predicția cozilor la o intersecție semaforizată

## Echipa

- Student 1: Avram Darius        
- Student 2: Vancea Paul
- Student 3: Sima Alin

## Scenariul proiectului

TrafficCast simulează o intersecție rutieră semaforizată folosind **[SUMO](https://sumo.dlr.de/)** (Simulation of Urban MObility). Vehiculele, fluxurile de trafic, semafoarele și detectoarele sunt virtuale; nu este necesar hardware rutier real.

Pentru prima versiune se va modela o singură intersecție cu patru brațe și semaforizare cu timp fix. Detectoarele virtuale **E2** vor furniza indicatori precum viteza medie, ocuparea și lungimea cozilor. Ulterior, proiectul poate fi extins la două intersecții sau la semaforizare adaptivă.

## Arhitectura inițială

```text
SUMO — intersecție, vehicule, semafoare și detectoare E2
        |
        v
Export date simulate (CSV/Parquet)
        |
        v
replay.py — Raspberry Pi sau mediu local
        |
        v
MQTT — Mosquitto
        |
        v
Consumator de mesaje + inferență ML
        |
        v
SQLite — măsurători și predicții
        |
        v
Dashboard — Streamlit
```

SUMO va genera scenarii repetabile pentru antrenare și evaluare. Datele generate pot fi exportate din detectoare în CSV/Parquet și redate prin `replay.py`, în concordanță cu scheletul IoT al disciplinei. Ca extensie, Python poate citi direct simularea în execuție prin **TraCI** și publica măsurătorile prin MQTT, fără etapa de replay.

Modelul ML va fi antrenat offline în Python sau Google Colab, apoi exportat și încărcat de aplicație. Un asistent conversațional LLM cu tool calling/MCP poate fi adăugat ulterior pentru întrebări despre măsurători și predicții; nu este necesar pentru funcționarea versiunii inițiale.

## Scopul final

Realizarea unui prototip IoT care estimează lungimea cozilor la o intersecție simulată pentru următoarele **30–60 de secunde**, afișează valorile și predicțiile într-un dashboard și permite evaluarea preciziei atunci când unii detectori devin temporar indisponibili.

## Obiective

1. Construirea intersecției, a rutelor și a programului semafoarelor în SUMO, folosind NetEdit sau instrumentele de generare a rețelei.
2. Amplasarea detectoarelor E2 pe apropierile intersecției și colectarea indicatorilor de trafic.
3. Generarea mai multor scenarii controlate: trafic redus, moderat și intens, fluxuri dezechilibrate și semințe de simulare diferite.
4. Antrenarea și compararea unui model de bază cu un model ML, inițial **persistență** versus **Random Forest Regressor**.
5. Simularea pierderilor de date sau a indisponibilității unor detectoare și măsurarea efectului asupra erorii predicțiilor.
6. Transmiterea datelor prin MQTT, stocarea lor în SQLite și afișarea măsurătorilor, cozilor estimate și alertelor în dashboard.

## Întrebarea de cercetare

**Cât de precis poate fi estimată lungimea viitoare a cozilor la o intersecție semaforizată pe baza istoricului detectoarelor și a stării semaforului și în ce măsură indisponibilitatea detectorilor degradează predicția?**

Evaluarea va folosi MAE și RMSE. Seturile de antrenare, validare și test vor proveni din rulări separate ale simulatorului, pentru a verifica generalizarea la scenarii care nu au fost folosite la antrenare. Valorile de referință ale cozilor din SUMO vor fi păstrate separat de intrările disponibile modelului.

## Tehnologii propuse

- **Simulare trafic:** SUMO, SUMO-GUI, NetEdit
- **Integrare și procesare:** Python, TraCI, pandas, NumPy
- **Comunicare:** MQTT, Mosquitto
- **Machine Learning:** scikit-learn
- **Stocare:** SQLite
- **Dashboard:** Streamlit
- **Antrenare și analiză:** Jupyter Notebook / Google Colab

## Bibliografie

1. Eclipse SUMO, *Simulation of Urban MObility — documentație oficială*: https://sumo.dlr.de/docs/
2. Eclipse SUMO, *NetEdit — creare și editare a rețelelor*: https://sumo.dlr.de/docs/Netedit/index.html
3. Eclipse SUMO, *Lane-area Detectors (E2)*: https://sumo.dlr.de/docs/Simulation/Output/Lanearea_Detectors_(E2).html
4. Eclipse SUMO, *TraCI — interfață Python pentru simularea în execuție*: https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html
5. Eclipse SUMO, *Queue Output — măsurarea cozilor*: https://sumo.dlr.de/docs/Simulation/Output/QueueOutput.html
6. scikit-learn, *RandomForestRegressor*: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html
