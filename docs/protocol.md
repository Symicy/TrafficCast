# Protocolul măsurătorilor

Adaptorul produce o măsurătoare pe direcție și pas. Cele patru procese senzor
publică pe `trafficcast/J0/sensors/{N|E|S|W}`, cu MQTT 3.1.1, QoS 1 și
`retain=false`. **Sursa curentă emite versiunea 2**; gateway-ul acceptă și v1.

## Exemplu v2

Valorile sunt ilustrative. Datele unei direcții sunt transmise împreună, inclusiv
ambele benzi și ieșiri, fără a crea procese suplimentare.

```json
{
  "run_id": "demo-v2",
  "sensor_id": "E2_N",
  "direction": "N",
  "sequence": 42,
  "sim_time_s": 42.0,
  "source": "sumo",
  "vehicle_count": 4,
  "mean_speed_m_s": 1.125,
  "occupancy_pct": 6.6665,
  "jam_length_m": 12.0,
  "exit_vehicle_count": 1,
  "tls_phase": 0,
  "schema_version": 2,
  "halting_count": 3,
  "lanes": [
    {
      "detector_id": "E2_N_0",
      "lane_id": "N_in_0",
      "vehicle_count": 3,
      "halting_count": 2,
      "mean_speed_m_s": 1.5,
      "occupancy_pct": 10.0,
      "jam_length_m": 12.0,
      "detector_length_m": 150.0,
      "coverage_limited": false,
      "status": "ok"
    },
    {
      "detector_id": "E2_N_1",
      "lane_id": "N_in_1",
      "vehicle_count": 1,
      "halting_count": 1,
      "mean_speed_m_s": 0.0,
      "occupancy_pct": 3.333,
      "jam_length_m": 5.0,
      "detector_length_m": 150.0,
      "coverage_limited": false,
      "status": "ok"
    }
  ],
  "exits": [
    {
      "detector_id": "E1_N_out_0",
      "lane_id": "N_out_0",
      "vehicle_count": 1,
      "passed_vehicle_count": 1,
      "flow_veh_h": 180.0,
      "window_s": 60.0,
      "status": "ok"
    },
    {
      "detector_id": "E1_N_out_1",
      "lane_id": "N_out_1",
      "vehicle_count": 0,
      "passed_vehicle_count": 0,
      "flow_veh_h": 120.0,
      "window_s": 60.0,
      "status": "ok"
    }
  ],
  "phase_elapsed_s": 7.0,
  "red_elapsed_s": 0.0,
  "tls_state": "GGGgrrrrGGGgrrrr",
  "quality": "ok"
}
```

## Identitate și timp

- `run_id`: 1–64 litere ASCII, cifre, `_` sau `-`; identifică experimentul.
- `sensor_id`: identificator logic `E2_{direction}`; grupează senzorii fizici simulați.
- `direction`: N/E/S/W; trebuie să corespundă topicului și benzilor.
- `sequence`: începe de la 1 pentru fiecare direcție și rulare.
- `sim_time_s`: timpul SUMO în secunde, nu timpul calculatorului.
- `source`: întotdeauna `sumo`.
- `message_id`: derivat în jurnale ca `run_id:sensor_id:sequence`; nu este câmp MQTT.

Modul continuu păstrează identificatorul rulării și nu resetează timpul sau secvențele.

## Măsurători pe bandă și rezumat

`lanes` conține câte un element pentru fiecare E2 de la intrare; `exits`
conține E1 de pe benzile ieșirii aceluiași braț. Scenariul urban are câte două
elemente în fiecare listă, iar scenariul inițial câte unul.

| Câmp | Semnificație |
|---|---|
| `vehicle_count` | Observații E2 în ultimul pas; la nivel de direcție se însumează benzile disponibile |
| `halting_count` | Vehicule considerate staționate conform pragurilor detectorului; se însumează pe direcție |
| `mean_speed_m_s` | Viteză E2 în m/s; rezumat ponderat cu numărul de vehicule cu viteză disponibilă |
| `occupancy_pct` | Ocupare E2; rezumatul este media benzilor disponibile, cu detectoare livrate de aceeași lungime |
| `jam_length_m` | Coada observată în metri; rezumatul păstrează maximul dintre benzi |
| `detector_length_m` | Lungimea observată de E2, 150 m în scenariile livrate |
| `coverage_limited` | Coada ajunge la cel puțin 90% din lungimea E2; poate depăși zona observată |
| `exit_vehicle_count` | Suma observațiilor E1 din ultimul pas; nu este total cumulativ de vehicule |
| `passed_vehicle_count` | Trecerea finalizată a unui vehicul prin E1, cu deduplicare între benzile de ieșire |
| `flow_veh_h` | Treceri finalizate pe fereastra observată, scalate la vehicule/oră |
| `window_s` | Durata ferestrei de debit: până la 60 s, mai scurtă la pornire sau după o întrerupere |

Viteza este `null` când nu este disponibilă. Ocuparea este între 0 și 100%.
`vehicle_count` și `halting_count` sunt citiri TraCI distincte; la schimbări
de bandă sau la marginea detectorului pot avea diferențe temporale și nu se
impune că primul este întotdeauna mai mare decât al doilea.

Deduplicarea E1 folosește identitatea vehiculului în adaptor, fără a o publica.
Memoria este eliberată când vehiculul părăsește rețeaua. Numărarea este definită
pentru scenariile livrate, în care o călătorie traversează intersecția o singură dată.

E2_N observă intrarea din nord; E1 de pe N_out observă ieșirea spre nord.
Acestea nu sunt același grup de vehicule, inclusiv când există viraje.

## Context semaforic și calitate

- `tls_phase`: indice 0–5 în programele livrate.
- `tls_state`: starea completă a legăturilor semaforice din SUMO.
- `phase_elapsed_s`: timpul simulat de la începutul fazei curente.
- `red_elapsed_s`: durata roșului continuu pentru direcția mesajului; zero pe verde/galben.
- `status`: `ok` sau `unavailable`, pentru fiecare detector.
- `quality`: `ok` dacă toate citirile sunt disponibile, altfel `degraded`.

O citire indisponibilă are măsurătorile `null`. Rezumatul direcției poate
conține numai contribuțiile disponibile; când `quality=degraded`, el nu
reprezintă întreaga direcție. Consumatorul trebuie să interpreteze și calitatea,
nu doar valorile numerice din rezumat.

Gateway-ul verifică separat golurile de secvență, ordinea și progresul timpului.
Salvează `reception_quality` (`ok`, `sequence_gap`, `out_of_order`, `stale`)
și emite `RECEPTION_QUALITY` pentru anomalii. Inactivitatea proceselor este
urmărită după timpul real. Aceste verificări nu recuperează pachetele pierdute.

## Compatibilitate și stocare

V1 conține câmpurile din exemplu până la `schema_version`, fără extensiile v2.
În v1, `schema_version` poate lipsi și este implicit 1.
Gateway-ul acceptă ambele versiuni pentru stocare.

SQLite păstrează cheia `(run_id, sensor_id, sequence)`, payload-ul integral și
`received_at_utc`. Tabelul `measurements` conține rezumatul și calitatea
recepției; `measurement_lanes` și `measurement_exits` păstrează citirile
individuale. Baza existentă este extinsă automat, fără ștergerea rândurilor v1.

## Contextul semafoarelor

Starea și timpii semafoarelor sunt observații ale programului fix executat de
SUMO. Gateway-ul primește măsurători; nu publică decizii sau comenzi către
intersecție. Alegerea unui algoritm sau model de semaforizare este separată
de acest protocol de date.

## Jurnale

Cele șase etape rămân `SUMO_READ`, `MQTT_PUBLISH`, `MQTT_PUBACK`,
`MQTT_OBSERVED`, `GATEWAY_RECEIVE`, `GATEWAY_STORED`.
Payload-ul măsurătorii este același în toate etapele.
Mai există `GATEWAY_DUPLICATE` și `RECEPTION_QUALITY` pentru stocare și
calitatea recepției. PUBACK confirmă brokerul; salvarea este confirmată prin
`GATEWAY_STORED`.
