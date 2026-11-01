# TrafficCast — semafoare inteligente pentru fluidizarea traficului

## Echipa

- Student 1: Avram Darius
- Student 2: Vancea Paul
- Student 3: Sima Alin

## Scenariu IoT și scop

TrafficCast simulează în [SUMO](https://sumo.dlr.de/) o intersecție cu patru
brațe, două benzi pe sens și viraje. Are **16 senzori simulați**: 8 E2 pe
intrări pentru trafic și cozi, respectiv 8 E1 pe ieșiri pentru treceri și debite.
Sunt urmărite anomalii precum oprirea unui senzor, duplicate și mesaje lipsă.

Scopul final este fluidizarea traficului prin adaptarea semafoarelor.
**Etapa actuală: procesele senzor transmit date către gateway;
semafoarele urmează programul fix din SUMO.**

## Arhitectură

```text
SUMO → adaptor TraCI → 4 procese senzor → MQTT / Mosquitto → gateway → SQLite
                          N / E / S / W
```

Un singur adaptor distribuie citirile prin cozi locale. Procesele publică pe
topicuri separate; gateway-ul validează, deduplică și salvează. Un monitor
independent și jurnalele permit urmărirea mesajelor.
Detalii: [arhitectură](docs/arhitectura.md), [protocol](docs/protocol.md)
și [transmisie](docs/transmisie.md).

## Întrebare de cercetare

**RQ:** În ce condiții de cerere poate controlul bazat pe senzori să reducă
așteptarea și cozile față de semaforizarea fixă?

## Ipoteză

**H1:** Pentru cerere variabilă, controlul bazat pe măsurători reduce așteptarea
medie fără reducerea numărului de vehicule evacuate, comparativ cu programul fix.
Ipoteza va fi testată după integrarea controlului.

## Referință (baseline)

Programul fix SUMO: 30 s verde, 3 s galben și 2 s toate roșu pentru fiecare
axă, alternativ Nord/Sud și Est/Vest.

## Abordare propusă

Colectăm date reproductibile pe benzi, cu informații despre trafic, semafoare
și calitatea citirilor. Ulterior, un algoritm sau model ML, încă neales, va
putea folosi datele pentru decizii de semaforizare.

## Plan experimental

- **Date:** generate de SUMO în [7 profiluri de trafic](docs/experimente.md).
- **Variabile controlate:** rețea, cerere, seed și durată.
- **Evaluare curentă:** corespondența mesajelor citite, transmise și salvate.
- **Evaluare viitoare:** adaptiv versus fix; așteptare, cozi și vehicule evacuate.

## Tehnologii

- **Simulare:** SUMO / SUMO-GUI și TraCI.
- **Senzori și gateway:** Python >=3.11, multiprocessing.
- **Comunicație:** MQTT 3.1.1, QoS 1, Mosquitto și Eclipse Paho.
- **Stocare și teste:** SQLite, jurnale JSONL și pytest.

## Pornire

Instalare: **[ghid Windows/Linux](docs/pornire.md)**.
După configurare, din rădăcina proiectului, cu Mosquitto pornit:

Windows — PowerShell:

```powershell
.\.venv\Scripts\python.exe -m trafficcast demo --external-broker --gui --steps 120 --pace 1
```

Linux — Bash:

```bash
.venv/bin/python -m trafficcast demo --external-broker --gui --steps 120 --pace 1
```

Fără broker activ, omite `--external-broker`. Pentru trafic continuu,
înlocuiește `--steps 120` cu `--continuous`; oprire cu Ctrl+C.
Datele și jurnalele sunt în `data/runtime/`.

## Rezultate curente

Ultima verificare: **59 de teste trecute**; 120 de pași produc **480 de
măsurători**, verificate până în SQLite. Vezi [verificările](docs/verificare.md).
Comparația adaptiv/fix nu a fost încă realizată.

## Limitări

Traficul este integral simulat, fără pietoni. E2 observă numai 150 m.
Nu există recuperare offline garantată sau retenție automată a datelor.

## Bibliografie

- [SUMO și TraCI](https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html)
- [Detectoare E2](https://sumo.dlr.de/docs/Simulation/Output/Lanearea_Detectors_(E2).html) și [E1](https://sumo.dlr.de/docs/Simulation/Output/Induction_Loops_Detectors_(E1).html)
- [Semaforizarea în SUMO](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html)
- [Eclipse Paho MQTT Python](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html) și [Mosquitto](https://mosquitto.org/)
