# Pornire pe Windows și Linux

Rulează comenzile din rădăcina repository-ului. Python minim: **3.11**.
Versiunile de referință sunt **SUMO 1.28.0**, **Mosquitto 2.1.2** și dependențele
Python fixate în `pyproject.toml`.

## 1. Windows nativ — PowerShell

Instalează [Python](https://www.python.org/downloads/windows/),
[SUMO pentru Windows](https://sumo.dlr.de/docs/Installing/) și
[Mosquitto x64](https://mosquitto.org/download/). Dacă Python este deja instalat,
verifică `python --version`; nu este necesară încă o instalare.

SUMO include `sumo.exe`, `sumo-gui.exe` și `netconvert.exe` în directorul
`bin`. Instalatorul poate configura `SUMO_HOME` și `PATH`; deschide un terminal
nou după instalare. Aplicația caută și `SUMO_HOME` din setările Windows, iar
Mosquitto este căutat și în directorul standard de instalare.

Exemplu pentru instalarea verificată local; adaptează directoarele dacă diferă:

```powershell
$env:SUMO_HOME = 'C:\Program Files (x86)\SUMO'
$env:Path = "$env:SUMO_HOME\bin;C:\Program Files\Mosquitto;$env:Path"
sumo --version
netconvert --version
mosquitto -h
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Comenzile de mai sus modifică mediul numai pentru terminalul curent.
Pentru persistență, adaugă directoarele în variabila utilizatorului `PATH`
din setările Windows. Mediul virtual nu trebuie activat; folosim direct
interpreterul său, fără modificarea politicii de execuție PowerShell.

Verifică serviciul brokerului:

```powershell
Get-Service mosquitto
```

Dacă este pornit, folosește-l astfel:

```powershell
.\.venv\Scripts\python.exe -m trafficcast demo --external-broker --gui --steps 120 --pace 1
```

Dacă nu ai un broker pornit, omite `--external-broker`. Nu porni două
instanțe de broker pe același port. Pentru un broker separat al demonstrației
poți folosi `--port 1884`, fără să oprești serviciul existent.

## 2. Linux — Bash

### Fedora

```bash
sudo dnf install python3 python3-pip mosquitto flatpak
flatpak install --user flathub org.eclipse.sumo
```

Comanda Flatpak presupune că Flathub este configurat.
[Instrucțiuni Flatpak](https://flatpak.org/setup/).
O instalare SUMO nativă existentă este acceptată și are prioritate în modul `auto`.

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip mosquitto mosquitto-clients sumo sumo-tools
```

Verifică `sumo --version`. Pachetele distribuției pot avea altă versiune decât
1.28.0; pentru mediul de referință folosește o versiune corespunzătoare din
[sursele oficiale SUMO](https://sumo.dlr.de/docs/Installing/), inclusiv Flatpak.

### Mediul Python și demonstrația

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m trafficcast demo --gui --steps 120 --pace 1
```

Dacă brokerul distribuției rulează deja ca serviciu, adaugă
`--external-broker` sau alege `--port 1884` pentru brokerul propriu.
Pentru a forța SUMO Flatpak, adaugă `--sumo-backend flatpak`.

`bash scripts/demo.sh` pornește implicit demonstrația GUI cu 120 de pași și
pauză de 1 s. Parametrii expliciți sunt transmiși coordonatorului comun.
`TRAFFICCAST_PYTHON` poate selecta alt interpreter pentru scripturile Bash.

## 3. Comenzi comune și mod continuu

În exemplele următoare, `python` înseamnă interpreterul din `.venv`:
`.venv/bin/python` pe Linux sau `.\.venv\Scripts\python.exe` pe Windows.

```text
python -m trafficcast demo --gui --steps 120 --pace 1
python -m trafficcast demo --steps 120 --pace 0
python -m trafficcast demo --gui --continuous
python -m trafficcast demo --external-broker --gui --continuous
```

Fără `--gui`, simularea rulează fără interfață. Implicit sunt 120 de pași și
o pauză reală de 0,1 s; pentru `--continuous`, pauza implicită este 1 s.
Pauza se adaugă procesării și comunicației, deci nu garantează sincronizare
exactă cu ceasul real. Un pas al scenariilor livrate înseamnă 1 s simulat.

**Pentru acest proiect, modul continuu este pentru demonstrații**, iar
rulările finite sunt pentru teste și colectarea unor seturi de date comparabile.
Modul continuu nu repornește scenariul și nu recirculă aceleași mașini.
După secunda 1800, adaptorul continuă periodic introducerea unor vehicule noi
prin TraCI, folosind rutele/distribuțiile și debitele din scenariu. Timpul,
cozile, `run_id` și secvențele continuă.

Oprește cu **Ctrl+C în terminalul demonstrației**. Coordonatorul lasă cadrul în
curs să se termine, așteaptă până la 10 s salvarea în SQLite și observarea MQTT,
apoi închide procesele proprii. Brokerul extern rămâne pornit.
Jurnalele, baza și rapoartele XML cresc pe durata rulării; nu există încă rotație
automată sau retenție pentru sesiuni fără limită.

`--continuous` și `--steps` nu pot fi folosite împreună.
Modul continuu acceptă fluxurile periodice ale celor două scenarii livrate;
pentru scenarii proprii cere `id`, `route`, `period` numeric și `end` explicit.
Atributele suplimentare nesuportate sunt respinse explicit.

## Profiluri de trafic și reproducerea datelor

Pentru a genera cereri diferite, selectează un profil de trafic:

```text
python -m trafficcast demo --external-broker --gui --continuous --profile switching --demand-duration 180 --pace 0.2
python -m trafficcast demo --external-broker --profile balanced --seed 42 --steps 2400 --pace 0
```

Semaforizarea este programul fix din scenariu: verde 30 s, galben 3 s și
degajare 2 s pentru fiecare axă. Gateway-ul colectează și salvează datele.

Profilurile disponibile sunt `baseline`, `balanced`, `switching`, `waves`,
`left-heavy`, `light` și `stress`. Pentru profilurile variabile, `--demand-duration`
stabilește durata cererii, implicit 1800 s; în modul continuu sunt generate
cicluri cu vehicule noi. `baseline` folosește fluxurile din scenariu.
Pentru o colectare finită reproductibilă:

```text
python -m trafficcast demo --external-broker --profile switching --seed 42 --steps 2400 --pace 0 --runtime-dir data/runtime/switching-42
```

Folosește directoare de date și identificatori de rulare distincte pentru
experimente diferite. Vezi [experimente.md](experimente.md) pentru profiluri și durate.

## 4. Jurnale și baza de date

În PowerShell:

```powershell
Get-Content .\data\runtime\mqtt.log -Encoding utf8 -Wait
Get-Content .\data\runtime\gateway.log -Encoding utf8 -Wait
```

În Bash:

```bash
tail -f data/runtime/mqtt.log
tail -f data/runtime/gateway.log
```

Sunt păstrate `sumo-mqtt.log`, `mqtt.log`, `gateway.log`,
`trafficcast.sqlite3` și, pentru brokerul propriu, `broker.log`.
Jurnalele sunt suprascrise la fiecare demo; SQLite acumulează rulări.
Poți separa experimentele cu `--runtime-dir data/runtime/experiment-1`.

Mesajele curente folosesc schema v2, cu date individuale pe bandă. Gateway-ul
acceptă și v1 și extinde automat baza existentă, păstrând rândurile vechi.
Citirile sunt în `measurement_lanes` și `measurement_exits`, iar rezumatul,
payload-ul și calitatea recepției sunt în `measurements`.

Verificarea numărului de măsurători, pe ambele sisteme:

```text
python -c "import sqlite3; db=sqlite3.connect('data/runtime/trafficcast.sqlite3'); print(db.execute('SELECT run_id,direction,COUNT(*) FROM measurements GROUP BY run_id,direction').fetchall())"
```

O rulare sănătoasă de 120 de pași produce **480 de măsurători**.
Folosește un `run_id` nou la fiecare experiment. Demo respinge identificatorii
deja salvați; pornirea manuală deduplică mesajele pe rulare, senzor și secvență.

## 5. Pornire manuală

În patru terminale, cu interpreterul virtual disponibil și executabilele în PATH:

```text
mosquitto -c config/mosquitto.conf
python -m trafficcast gateway
python -m trafficcast monitor
python -m trafficcast run --gui --continuous
```

Dacă serviciul Mosquitto este deja pornit, folosește-l și sari prima comandă.
Așteaptă `GATEWAY_READY` și `MONITOR_READY` înainte de sursă.
La oprirea manuală, oprește întâi `run`, apoi observatorul și gateway-ul.
Pentru alt broker, setează aceleași `--host` și `--port` pentru toate componentele.
Configurația brokerului propriu permite conexiuni anonime numai pe loopback.

## 6. Scenarii și regenerarea rețelei

```text
python -m trafficcast scenario gui
python -m trafficcast scenario headless
python -m trafficcast scenario rebuild
python -m trafficcast demo --scenario simulation/intersection/intersection.sumocfg --steps 120 --pace 0
```

Scenariul implicit este `simulation/intersection-urban/intersection.sumocfg`;
cel inițial rămâne în `simulation/intersection/`.
Comanda GUI începe automat simularea. `scenario` pornește numai SUMO, fără MQTT;
modul continuu este disponibil prin `run` sau `demo`.

După modificarea surselor de noduri, segmente, conexiuni sau faze, regenerează
rețeaua cu `scenario rebuild`, folosind `--scenario` pentru alt director.
Nu rula simultan două simulări pe același scenariu: rapoartele din `results/`
sunt suprascrise. Folosește copii separate pentru experimente paralele.
Aceeași regulă se aplică directorului de jurnale `--runtime-dir`.

## 7. Teste

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:TRAFFICCAST_TEST_SUMO = '1'
.\.venv\Scripts\python.exe -m pytest -q
```

Bash:

```bash
.venv/bin/python -m pytest -q
TRAFFICCAST_TEST_SUMO=1 .venv/bin/python -m pytest -q
```

Testele de integrare folosesc porturi temporare, baze și copii de scenariu,
inclusiv căi cu spații. Nu opresc serviciul brokerului existent.
Testele care cer SUMO sunt activate explicit; cele MQTT se omit dacă Mosquitto
nu este găsit. Vezi [verificare.md](verificare.md) pentru verificările efectuate.

## Probleme frecvente

- **Port ocupat:** folosește `--external-broker` pentru brokerul existent sau alt `--port`.
- **Executabil negăsit:** verifică PATH, SUMO_HOME și instalările. Redeschide terminalul după instalare.
- **Connection refused:** brokerul extern nu rulează sau hostul/portul nu corespund.
- **Măsurători inițial zero:** vehiculele nu au ajuns încă la zona detectorilor.
- **FĂRĂ DATE după terminare:** gateway-ul manual raportează inactivitatea după timpul real; nu diagnostichează cauza.
- **Oprirea brokerului în timpul rulării:** fluxul poate eșua prin timeout; stocarea offline și reluarea garantată nu sunt implementate.
