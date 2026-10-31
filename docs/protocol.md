# Protocolul măsurătorilor, versiunea 1

Un mesaj pe direcție și pas. Topic: `trafficcast/J0/sensors/{N|E|S|W}`. JSON, MQTT 3.1.1, QoS 1, `retain=false`.

```json
{
  "run_id": "demo-001",
  "sensor_id": "E2_N",
  "direction": "N",
  "sequence": 42,
  "sim_time_s": 42.0,
  "source": "sumo",
  "vehicle_count": 8,
  "mean_speed_m_s": 2.1,
  "occupancy_pct": 35.0,
  "jam_length_m": 28.5,
  "exit_vehicle_count": 1,
  "tls_phase": 0,
  "schema_version": 1
}
```

Valorile exemplului sunt ilustrative. `sensor_id` identifică E2 principal; procesul direcției include și citirea E1 de pe ieșirea aceluiași braț.

| Câmp | Semnificație |
|---|---|
| `run_id` | Rulare: 1–64 litere ASCII, cifre, `_` sau `-`; implicit generat automat |
| `sensor_id`, `direction` | Identificatorul E2 și brațul; trebuie să corespundă topicului |
| `sequence` | Secvență de la 1, separată pentru fiecare senzor și rulare |
| `sim_time_s` | Timp în secunde din simularea SUMO, nu ora calculatorului |
| `source` | Întotdeauna `sumo` |
| `vehicle_count` | Vehicule observate în zona E2 în ultimul pas; nu debit |
| `mean_speed_m_s` | Viteză medie în m/s; `null` când SUMO întoarce o valoare indisponibilă negativă |
| `occupancy_pct` | Ocupare spațială a zonei E2, în procente |
| `jam_length_m` | Lungimea ambuteiajului raportată de E2, în metri, limitată de zona observată |
| `exit_vehicle_count` | Valoarea E1 `getLastStepVehicleNumber` pe ieșirea aceluiași braț; observații în ultimul pas, fără agregare cumulată |
| `tls_phase` | Indice 0–5 în programul semaforic al scenariului livrat |

E2_N observă vehicule care intră din Nord și merg spre Sud; E1_N_out observă ieșirea spre Nord. Acestea nu reprezintă același grup de vehicule. Pentru debitul agregat pe intervale se poate folosi raportul XML E1 `nVehContrib`; măsurarea pe ultimul pas are semantica proprie TraCI.

Gateway-ul respinge tipurile greșite, câmpurile lipsă/suplimentare, valorile negative/nefinite, direcțiile și topicurile incompatibile. Deduplică pe `(run_id, sensor_id, sequence)` și adaugă `received_at_utc` la stocare. Nu implementează încă verificarea continuă a golurilor de secvență.

## Urmărirea transmiterii

Jurnalele au evenimente JSON pentru `SUMO_READ`, `MQTT_PUBLISH`, `MQTT_PUBACK`, `MQTT_OBSERVED`, `GATEWAY_RECEIVE` și `GATEWAY_STORED`. Fiecare include `message_id`, derivat din `run_id:sensor_id:sequence`, plus `timestamp_utc`, `topic` și `payload` identic cu mesajul transmis. Identificatorul este derivat, nu un câmp suplimentar al mesajului MQTT.

`MQTT_PUBACK` confirmă primirea la broker. Observatorul și gateway-ul sunt abonați independenți; ordinea afișării lor față de PUBACK nu este garantată. `GATEWAY_STORED` apare numai după salvarea în SQLite. La duplicate apare `GATEWAY_DUPLICATE`.
