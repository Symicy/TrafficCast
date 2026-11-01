# Profiluri de trafic și reproducerea datelor

Intersecția generează măsurători pentru program. SUMO execută programul fix
al semafoarelor, iar gateway-ul validează și salvează observațiile. Profilul
traficului și sămânța aleatoare permit colectarea unor seturi de date variate.

## Profiluri disponibile

| Profil | Cerere |
|---|---|
| `baseline` | Fluxurile scenariului: 480 veh/h pe fiecare intrare N/S, 300 pe E/W |
| `balanced` | 450 veh/h pe fiecare intrare |
| `switching` | Prima treime: N/S 900, E/W 150; a doua: invers; ultima: 450 pe fiecare intrare |
| `waves` | În fiecare minut, un val de 20 s la 900 veh/h N/S și 600 E/W, apoi pauză |
| `left-heavy` | Debitele de bază, cu 45% stânga, 40% înainte, 15% dreapta |
| `light` | 90 veh/h pe fiecare intrare |
| `stress` | 1100 veh/h pe fiecare intrare |

Ratele sunt ținte pentru sosiri aleatoare, nu cote exacte pe rulare.
`baseline` păstrează cadența periodică a fluxurilor din scenariu.
Profilurile variabile folosesc intervale exponențiale, reproductibile prin
seed. În afară de `left-heavy`, ponderile sunt 20% stânga, 60% înainte și
20% dreapta, pe rutele disponibile. `left-heavy` cere scenariul urban.

## Demonstrație continuă

Windows, cu serviciul Mosquitto pornit:

```powershell
.\.venv\Scripts\python.exe -m trafficcast demo --external-broker --gui --continuous --profile switching --demand-duration 180 --pace 0.2
```

Linux, cu broker pornit de demonstrație:

```bash
.venv/bin/python -m trafficcast demo --gui --continuous --profile switching --demand-duration 180 --pace 0.2
```

În acest exemplu, cererea N/S este dominantă în primele 60 s simulate,
cererea E/V în următoarele 60 s, apoi urmează 60 s de trafic echilibrat.
Ciclul cererii se repetă cu vehicule noi, fără resetarea timpului sau a cozilor.
Semaforizarea rămâne programul fix din SUMO.

`--demand-duration` este implicit 1800 s pentru profilurile variabile.
La `baseline`, durata fluxurilor este cea din scenariu; modul continuu
prelungește acele fluxuri la aceeași cadență.
`--pace` este o pauză reală pe cadru, nu o garanție de sincronizare exactă.

## Colectare finită

Pentru seturi de date comparabile, păstrează scenariul, profilul, seed-ul,
durata cererii și numărul de pași. Exemplu Windows:

```powershell
.\.venv\Scripts\python.exe -m trafficcast demo --external-broker --profile switching --seed 42 --demand-duration 1800 --steps 2400 --pace 0 --runtime-dir data/runtime/switching-42
```

Linux:

```bash
.venv/bin/python -m trafficcast demo --profile switching --seed 42 --demand-duration 1800 --steps 2400 --pace 0 --runtime-dir data/runtime/switching-42
```

Sunt 1800 s de cerere și 600 s suplimentare pentru evacuarea traficului.
La trafic intens, pot rămâne vehicule neintroduse sau neterminate; rapoartele
SUMO trebuie interpretate împreună cu măsurătorile senzorilor.

Folosește un `run_id` nou și un director de jurnale separat pentru fiecare
experiment. Jurnalele aceluiași director sunt suprascrise, iar baza SQLite
acumulează rulările. Nu rula simultan două simulări pe același director de
scenariu, deoarece rapoartele XML sunt comune.

## Date disponibile

- MQTT: patru mesaje pe pas, cu rezumat și date pe bandă.
- SQLite: `measurements`, `measurement_lanes` și `measurement_exits`,
  cu identificatori de rulare, timp simulat, payload și calitatea datelor.
- JSONL în jurnale: urmărirea aceleiași măsurători până la salvare.
- XML SUMO: detectoare, summary și tripinfo; scenariul urban produce și vehroute.

Un program separat poate citi MQTT sau SQLite pentru prelucrare ori pentru
pregătirea datelor unui model. Semnificația câmpurilor este definită în
[protocol.md](protocol.md). Alegerea unui algoritm de decizie și integrarea
acestuia cu semafoarele sunt etape separate.
