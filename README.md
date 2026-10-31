# TrafficCast — semafoare inteligente pentru fluidizarea traficului

## Echipa

- Student 1: Avram Darius
- Student 2: Vancea Paul
- Student 3: Sima Alin

## Scenariu și scop

TrafficCast simulează o intersecție cu patru brațe în [SUMO](https://sumo.dlr.de/). Scopul final este fluidizarea traficului prin adaptarea semafoarelor la cererea observată. Vom compara controlul adaptiv cu semaforizarea fixă, folosind timpul de așteptare, cozile și numărul de vehicule evacuate. Toate componentele rutiere sunt simulate.

Etapa implementată acum: **mai multe procese senzor transmit date către un proces gateway**. Scenariul are semafoare cu timpi ficși; controlul adaptiv urmează după validarea comunicației.

## Arhitectura implementată

```text
SUMO → adaptor Python TraCI → 4 procese senzor → MQTT / Mosquitto → gateway → SQLite
                                  N / E / S / W
```

Un singur adaptor citește SUMO și distribuie măsurătorile prin cozi locale. Fiecare proces senzor publică pe propriul topic MQTT. Gateway-ul validează mesajele, elimină duplicatele și salvează măsurătorile. Toate măsurătorile provin direct din simularea SUMO în execuție. Jurnalele păstrează același identificator de mesaj la citire, publicare și recepție. Un observator MQTT independent arată mesajele livrate de broker.

## Pornire

Instrucțiuni complete: **[docs/pornire.md](docs/pornire.md)**. Din rădăcina repository-ului, pe Fedora:

```bash
sudo dnf install python3 python3-pip mosquitto
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
bash scripts/demo.sh
```

Demonstrație cu SUMO instalat deja, inclusiv prin Flatpak:

```bash
bash scripts/demo.sh --gui --steps 120 --pace 1
```

În alte terminale: `tail -f data/runtime/mqtt.log` și `tail -f data/runtime/gateway.log`. Datele se salvează în `data/runtime/trafficcast.sqlite3`. Scriptul demo pornește SUMO-GUI, cele patru procese senzor, brokerul local, observatorul și gateway-ul, apoi închide componentele la terminare; portul 1883 trebuie să fie liber.

## Organizare

| Director | Conținut |
|---|---|
| `simulation/intersection/` | Rețea SUMO generată, surse XML, trafic, semafoare și detectoare |
| `src/trafficcast/` | Adaptor SUMO, procese senzor, observator MQTT, gateway și jurnalizare |
| `config/` | Configurația brokerului Mosquitto local |
| `scripts/` | Pornirea simulării, regenerarea rețelei și demonstrația completă |
| `data/runtime/` | Baza SQLite și jurnale locale, excluse din Git |
| `docs/` | Instrucțiuni, arhitectură și protocol |
| `tests/` | Validare date, SQLite și teste cu broker/SUMO real |

Urmărirea unei măsurători, pas cu pas: [docs/transmisie.md](docs/transmisie.md).

## Următoarea etapă

Implementarea controlerului adaptiv și a comenzilor către SUMO prin TraCI, cu păstrarea fazelor compatibile, a galbenului, a intervalelor de degajare și a unei limite de așteptare. Predicția cozilor cu ML poate fi o extensie a controlerului.

## Bibliografie

- [SUMO și TraCI](https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html)
- [Detectoare E2](https://sumo.dlr.de/docs/Simulation/Output/Lanearea_Detectors_(E2).html)
- [Semaforizarea în SUMO](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html)
- [Eclipse Paho MQTT Python](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html)
- [Eclipse Mosquitto](https://mosquitto.org/)
