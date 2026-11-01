# Arhitectură și stadiul proiectului

Etapa curentă implementează simularea, colectarea și transportul măsurătorilor,
cu pornire comună pe Windows/Linux și trafic finit sau continuu.
Intersecția este sursa de date pentru program. SUMO execută semaforizarea fixă
definită în scenariu; colectarea și gateway-ul sunt independente de viitorul
algoritm sau model care va lua decizii.

```text
Coordonator demo → broker propriu sau broker extern
                → gateway → SQLite
                → monitor MQTT independent
                → adaptor Python ↔ SUMO / TraCI
                    ├─ Queue N → proces senzor N ─┐
                    ├─ Queue E → proces senzor E ─┤
                    ├─ Queue S → proces senzor S ─┼→ MQTT QoS 1 → broker
                    └─ Queue W → proces senzor W ─┘
```

## Responsabilități

- `sources.py`: unicul client TraCI avansează simularea, verifică acoperirea
  detectorilor pe benzi și construiește patru măsurători v2 pe cadru.
  În modul continuu prelungește fluxurile periodice prin introducerea de vehicule.
- `sensors.py`: patru procese `multiprocessing/spawn`, conexiuni MQTT separate,
  cozi locale limitate și așteptarea PUBACK înainte de cadrul următor.
- `transport.py`: conectare, confirmarea abonării și publicare QoS 1 cu timeout.
- `gateway.py`: validare, deduplicare pe `(run_id, sensor_id, sequence)`,
  stocare SQLite/WAL, verificarea secvenței/timpului și avertizare de inactivitate
  după timpul real.
- `telemetry.py`: citiri individuale E2/E1, staționări, debite pe fereastră,
  deduplicarea trecerilor și ceasul de roșu în timpul simulat.
- `quality.py`: urmărirea golurilor de secvență, ordinii și progresului timpului.
- `demand.py`: profiluri de cerere reproductibile și cicluri de trafic continuu.
- `monitor.py`: abonat independent pentru observarea mesajelor livrate.
- `tracing.py`: evenimente JSON corelate, scrise împreună cu newline pentru
  a evita intercalarea mesajelor între procese pe Windows.
- `demo.py`: pornire, verificarea pregătirii, jurnale UTF-8, confirmarea
  finalizării salvării/observării și închiderea componentelor proprii.
- `runtime.py`: descoperirea executabilelor și oprire portabilă prin semnale
  sau fișiere private de control. Fișierele de control nu transportă măsurători.
- `messages.py`: contractul comun, cu validarea tipurilor și unităților.

Datele sunt disponibile prin MQTT și SQLite pentru un consumator separat.
Programul viitor poate reuni citirile după `run_id`, `sequence` și `sim_time_s`.
Gateway-ul tratează fiecare măsurătoare validă independent și păstrează
contextul semaforic pentru interpretarea datelor.

PUBACK confirmă primirea la broker, nu scrierea în SQLite.
Demo verifică la final numărul de înregistrări al rulării și numărul de mesaje
observate, cu timeout de 10 s. Acest control nu reprezintă un protocol de
recuperare după căderi. Nu există încă stocare offline sau reluare garantată.

Oprirea unui senzor după inițializare lasă celelalte direcții să continue în
`run`. Demo semnalează o rulare finită incompletă. Senzorii nu sunt reporniți automat.

## Scenarii

| Proprietate | Implicit: intersection-urban | Inițial: intersection |
|---|---|---|
| Benzi pe sens | 2 | 1 |
| Mișcări | Stânga, înainte, dreapta | Numai înainte |
| Bandă dreaptă, indice 0 | Înainte și dreapta | Înainte |
| Bandă stângă, indice 1 | Stânga și înainte | — |
| Detectoare | 8 E2 și 8 E1 | 4 E2 și 4 E1 |
| Mesaje pe pas | 4, cu rezumat și date pe bandă | 4, cu câte o bandă |
| Program | N/S, apoi E/V; stânga cedează | N/S, apoi E/V |

Ambele scenarii au nodul central `J0`, brațe de aproximativ 300 m,
viteză maximă 13,89 m/s, pas de 1 s și seed 42.
Fiecare verde durează 30 s, urmat de galben 3 s și toate roșu 2 s:
șase faze, cu indicii 0–5, ciclu de 70 s.

În scenariul urban sunt 16 legături semaforice: câte patru pentru fiecare
direcție în ordinea N/E/S/W; în fiecare grup: dreapta, înainte de pe banda 0,
înainte de pe banda 1 și stânga. Starea verde a grupului este `GGGg`;
`g` indică cedarea la conflictele cu mișcările prioritare.
În scenariul inițial sunt patru legături, câte una pe direcție.

E2 au 150 m și se termină cu 1 m înainte de capătul intrării.
E1 sunt la 10 m pe fiecare bandă de ieșire. Măsurarea pe direcție este definită
în [protocol.md](protocol.md); detectorul observă numai zona acoperită.

## Cerere, durată și rezultate

Debitele totale rămân 480 vehicule/oră pe fiecare intrare N/S și 300 pe E/W.
În scenariul urban, rutele sunt alese cu ponderi 20% stânga, 60% înainte și
20% dreapta; procentele sunt probabilități, nu cote exacte pe rulare.
`departLane="best"` permite alegerea benzii compatibile cu ruta.

Cererea finită se termină la 1800 s; rularea autonomă se încheie la 2400 s.
Prin TraCI, durata este controlată de `--steps` sau `--continuous`.
În modul continuu, fluxurile livrate sunt continuate la aceeași cadență prin
TraCI, cu identificatori noi, fără resetarea stării și fără pre-generarea unui
fișier nelimitat de vehicule.

Rapoartele XML includ E1/E2, summary și tripinfo cu vehiculele neterminate;
scenariul urban produce și vehroute. Rulările simultane cer copii separate
de scenariu și directoare de jurnale separate.

## Reproducerea datelor și extensii

Profilul de cerere și sămânța aleatoare pot fi alese pentru fiecare rulare.
Vezi [experimente.md](experimente.md) pentru profiluri, durate și organizarea
seturilor de date. Un viitor algoritm sau model de semaforizare poate consuma
aceeași schemă de măsurători; alegerea și integrarea sa sunt etape separate.
