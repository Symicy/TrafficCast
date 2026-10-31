# Pornire pe Fedora — SUMO → MQTT → gateway

Toate măsurătorile sunt citite din SUMO în execuție, prin TraCI. Rulează comenzile din rădăcina repository-ului. Este suficient un singur calculator. Python minim: 3.11; SUMO verificat: 1.28.0.

## 1. Pregătirea mediului

```bash
sudo dnf install python3 python3-pip mosquitto
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Dacă ai SUMO instalat prin Flatpak, folosești instalarea existentă. Verificare: `flatpak info org.eclipse.sumo`. Pentru o instalare nouă, cu Flathub deja configurat:

```bash
flatpak install --user flathub org.eclipse.sumo
```

## 2. Demonstrația completă

```bash
bash scripts/demo.sh
```

Aceasta pornește SUMO-GUI, patru procese senzor, un broker Mosquitto local pe `127.0.0.1:1883`, gateway-ul și un observator MQTT. Simularea este controlată automat de TraCI; nu trebuie pornită separat cu Play.

Comanda implicită simulează 120 de pași, cu o pauză reală de 1 s după fiecare cadru. Fiecare pas al scenariului este de 1 s simulat. Timpul real include și comunicația și procesarea. În primul terminal vezi evenimentele `SUMO_READ`, `MQTT_PUBLISH`, `MQTT_PUBACK`, cu măsurătorile efective.

Deschide două terminale în același director:

```bash
tail -f data/runtime/mqtt.log
```

```bash
tail -f data/runtime/gateway.log
```

Primul arată `MQTT_OBSERVED`, de la un abonat independent al brokerului. Al doilea arată `GATEWAY_RECEIVE` și `GATEWAY_STORED`. Identificatorul `message_id` este același la fiecare etapă. Vezi [transmisie.md](transmisie.md) pentru o prezentare pas cu pas.

După terminare, jurnalele rămân disponibile în `data/runtime/`, iar datele sunt în `trafficcast.sqlite3`. Scriptul închide componentele pornite de el. Jurnalele sunt suprascrise la fiecare demonstrație, baza de date acumulează rulări cu `run_id` diferit. Pentru o prezentare, copiază jurnalele înaintea următoarei rulări.

Dacă există deja un broker pe 1883, folosește pornirea manuală. Pentru o verificare rapidă fără interfață grafică:

```bash
bash scripts/demo.sh --steps 120 --pace 0
```

Pentru a regla viteza demonstrației cu GUI:

```bash
bash scripts/demo.sh --gui --steps 120 --pace 0.5
```

## 3. Pornirea manuală, în patru terminale

Terminal 1 — broker:

```bash
mosquitto -c config/mosquitto.conf
```

Terminal 2 — gateway, după activarea `.venv`:

```bash
python -m trafficcast gateway
```

Terminal 3 — observator MQTT, după activarea `.venv`:

```bash
python -m trafficcast monitor
```

Așteaptă `GATEWAY_READY` și `MONITOR_READY`, apoi pornește în terminalul 4 adaptorul și senzorii:

```bash
python -m trafficcast run --gui --steps 120 --pace 1
```

Oprește componentele cu Ctrl+C. Pentru a vedea JSON-ul MQTT fără formatul jurnalului aplicației, poți folosi în alt terminal:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'trafficcast/J0/sensors/+' -v
```

Cu alt port sau broker, setează aceleași `--host` și `--port` la `gateway`, `monitor` și `run`. Configurația livrată permite conexiuni anonime numai pe loopback.

## 4. Verificarea datelor salvate

```bash
python - <<'PYTHON'
import sqlite3
with sqlite3.connect('data/runtime/trafficcast.sqlite3') as db:
    for row in db.execute('SELECT run_id, direction, COUNT(*) FROM measurements GROUP BY run_id, direction'):
        print(row)
PYTHON
```

O rulare completă de 120 de pași produce 120 de înregistrări pe direcție, în total 480. `run_id` este generat automat la fiecare pornire. Dacă îl setezi manual cu `--run-id`, folosește o identificare nouă pentru fiecare rulare: baza deduplică pe rulare, senzor și secvență.

## 5. Simularea opririi unui senzor

Pornește `python -m trafficcast run --gui --steps 120 --pace 1`. Citește PID-ul unei direcții din `SENZOR_PORNIT`, apoi execută `kill PID` în alt terminal, folosind PID-ul acelui proces. Restul direcțiilor continuă, iar gateway-ul anunță absența datelor după 5 s reale. Nu repornim automat senzorul.

Avertizarea apare și la finalul normal al unui flux dacă gateway-ul rămâne pornit manual: indică inactivitate, nu diagnostichează cauza.

## 6. Deschiderea doar a scenariului SUMO

```bash
bash scripts/sumo.sh gui
```

În această variantă apasă Play. Ea pornește numai simularea, fără fluxul MQTT. Configurația este `simulation/intersection/intersection.sumocfg`. Rulare fără interfață: `bash scripts/sumo.sh headless`. Regenerarea rețelei după modificarea surselor: `bash scripts/sumo.sh rebuild`.

Nu rula simultan două simulări pe același director: rapoartele XML din `simulation/intersection/results/` sunt suprascrise. Pentru scenarii simultane, folosește copii separate și `--scenario`.

## 7. Teste

```bash
python -m pytest -q
TRAFFICCAST_TEST_SUMO=1 python -m pytest -q
```

Testele MQTT cer `mosquitto` în PATH. Cele două teste ale fluxului de trafic folosesc SUMO real și sunt activate prin variabila de mai sus. Ele verifică egalitatea măsurătorilor la citire, publicare, observare MQTT, recepție și salvare, precum și continuarea celorlalți senzori după oprirea unuia. Sunt folosite porturi și baze temporare și copii ale scenariului.

## Probleme frecvente

- `Connection refused`: brokerul nu este pornit sau portul este greșit.
- Lipsesc primele mesaje: pornește gateway-ul și observatorul înaintea simulării și așteaptă confirmarea abonării.
- SUMO nu este găsit: verifică Flatpak sau executabilul din PATH; `--sumo-backend flatpak` forțează Flatpak.
- La început măsurătorile sunt zero: vehiculele au nevoie de timp să ajungă la detectoarele de lângă intersecție.
- Oprirea brokerului în timpul rulării produce timeout; retransmiterea după o perioadă offline nu este implementată.
