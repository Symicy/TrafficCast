# Cum demonstrăm transmiterea datelor

```text
Detectoare SUMO → TraCI → adaptor → 4 procese senzor → broker → gateway → SQLite
                                                        └──→ monitor MQTT
```

SUMO generează măsurătorile prin simularea vehiculelor. Python le citește și le
publică în timp ce simularea rulează. Mesajele v2 includ rezumatul pe direcție
și citirile individuale ale benzilor; toate au `source="sumo"`.

## Demonstrație

Windows, cu serviciul Mosquitto pornit:

```powershell
.\.venv\Scripts\python.exe -m trafficcast demo --external-broker --gui --continuous
```

În alte terminale:

```powershell
Get-Content .\data\runtime\mqtt.log -Encoding utf8 -Wait
Get-Content .\data\runtime\gateway.log -Encoding utf8 -Wait
```

Linux, cu broker pornit de demonstrație:

```bash
.venv/bin/python -m trafficcast demo --gui --continuous
tail -f data/runtime/mqtt.log
tail -f data/runtime/gateway.log
```

Pentru o captură finită folosește `--steps 120 --pace 1` în loc de
`--continuous`. La început este normal ca detectoarele să fie încă goale.
Oprirea cu Ctrl+C în terminalul demo închide componentele proprii după consumarea
ultimului cadru; brokerul extern rămâne activ.

## Urmărirea unei măsurători

| Eveniment | Ce confirmă |
|---|---|
| `SUMO_READ` | Adaptorul a citit și agregat datele din SUMO |
| `MQTT_PUBLISH` | Senzorul începe publicarea pe topicul direcției |
| `MQTT_PUBACK` | Brokerul a confirmat publicarea cu QoS 1 |
| `MQTT_OBSERVED` | Abonatul independent a primit mesajul |
| `GATEWAY_RECEIVE` | Gateway-ul a primit și validat mesajul |
| `GATEWAY_STORED` | Măsurătoarea a fost salvată în SQLite |

Alege un `message_id`, de exemplu `identificator-rulare:E2_N:42`, și caută-l
în toate cele trei jurnale.

PowerShell:

```powershell
Select-String -SimpleMatch 'identificator-rulare:E2_N:42' -Path data/runtime/sumo-mqtt.log,data/runtime/mqtt.log,data/runtime/gateway.log -Encoding utf8
```

Bash:

```bash
grep -F 'identificator-rulare:E2_N:42' data/runtime/sumo-mqtt.log data/runtime/mqtt.log data/runtime/gateway.log
```

Verifică același topic și payload la toate etapele. Timestamp-urile UTC sunt ale
calculatorului, iar `sim_time_s` aparține simulatorului. Monitorul și gateway-ul
sunt abonați independenți; ordinea lor față de PUBACK poate varia.

[exemplu-transmisie.jsonl](exemplu-transmisie.jsonl) păstrează un exemplu capturat
din scenariul inițial, înaintea adăugării benzilor și virajelor.

## Materiale pentru prezentare

- Imaginea intersecției și măsurătorile care se schimbă.
- Jurnalele aceleiași rulări și același payload în cele șase evenimente.
- Înregistrările SQLite: 120 pe direcție pentru o rulare sănătoasă de 120 de pași.
- Opțional `broker.log`, când brokerul este pornit de demo; serviciul extern
  folosește propriul mecanism de jurnalizare.

Demonstrația verifică transmiterea datelor din intersecție către gateway.
Semaforizarea urmează programul fix din SUMO. Pentru cereri diferite și
reproducerea traficului, vezi [experimente.md](experimente.md).
