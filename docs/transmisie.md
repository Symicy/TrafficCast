# Cum demonstrăm transmiterea datelor din SUMO la gateway

## Fluxul demonstrat

```text
Detectoare SUMO → TraCI → adaptor → 4 procese senzor → Mosquitto → gateway → SQLite
                                                       └────→ observator MQTT
```

SUMO generează măsurătorile prin simularea vehiculelor. Python le citește și le publică în timp ce simularea rulează. Cele patru procese senzor respectă cerința de mai mulți emițători; nu inventează valori. Toate mesajele au `source="sumo"`.

## Demonstrație în trei ferestre

1. Rulează `bash scripts/demo.sh`. În aceeași fereastră vezi evenimentele adaptorului și ale proceselor senzor; SUMO-GUI arată traficul.
2. În alt terminal rulează `tail -f data/runtime/mqtt.log`: vezi mesajele primite de observator direct de la broker.
3. În alt terminal rulează `tail -f data/runtime/gateway.log`: vezi recepția și salvarea acelorași măsurători.

În primele secunde este normal ca detectoarele să nu observe vehicule încă; așteaptă ca acestea să ajungă lângă intersecție.

## Ce urmărim pentru o măsurătoare

| Eveniment | Ce confirmă |
|---|---|
| `SUMO_READ` | Adaptorul a citit detectorul prin TraCI |
| `MQTT_PUBLISH` | Procesul senzor începe publicarea pe topicul direcției |
| `MQTT_PUBACK` | Brokerul a confirmat publicarea cu QoS 1 |
| `MQTT_OBSERVED` | Abonatul independent a primit mesajul de la broker |
| `GATEWAY_RECEIVE` | Gateway-ul a primit și validat mesajul |
| `GATEWAY_STORED` | Gateway-ul a salvat măsurătoarea în SQLite |

Alege un `message_id` din jurnal, de forma `identificator-rulare:E2_N:42`, și caută exact același șir în cele trei jurnale:

```bash
grep -F 'identificator-rulare:E2_N:42' data/runtime/sumo-mqtt.log data/runtime/mqtt.log data/runtime/gateway.log
```

Înlocuiește exemplul cu un identificator din rularea ta. În fiecare etapă verifici același `topic`, `vehicle_count`, `jam_length_m`, `sim_time_s` și restul câmpurilor din `payload`. Timestamp-urile din jurnal sunt ale calculatorului; `sim_time_s` este timpul simulatorului.

Observatorul și gateway-ul primesc separat de la broker. Observatorul nu este intermediar între broker și gateway. PUBACK-ul și livrările către abonați se pot vedea în ordine diferită în jurnale. Confirmarea salvării este evenimentul `GATEWAY_STORED`.

Un exemplu capturat dintr-o rulare efectivă este în [exemplu-transmisie.jsonl](exemplu-transmisie.jsonl): același mesaj în toate cele șase evenimente.

## Ce păstrăm pentru prezentare

- O captură cu intersecția în SUMO-GUI și măsurătorile care se schimbă.
- Jurnalele `sumo-mqtt.log`, `mqtt.log`, `gateway.log` și `broker.log` din aceeași rulare.
- O măsurătoare cu același identificator și payload în toate etapele.
- Numărul de înregistrări pe direcție din SQLite: pentru 120 de pași, 120 pe fiecare direcție dacă toate procesele au funcționat.

`broker.log` include și evenimentele protocolului Mosquitto, deoarece configurația activează `log_type all`. Pentru inspecția JSON-ului MQTT poți folosi și `mosquitto_sub`, conform instrucțiunilor din `pornire.md`.

Această demonstrație dovedește colectarea și transmiterea. Evaluarea fluidizării traficului va necesita implementarea controlului adaptiv și compararea sa cu programul fix.
