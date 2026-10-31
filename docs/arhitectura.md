# Arhitectură și delimitarea etapei

Obiectiv final: fluidizarea traficului prin controlul adaptiv al unei intersecții. Etapa curentă implementează colectarea și transportul măsurătorilor; nu aplică decizii adaptive și nu presupune că îmbunătățirea traficului a fost deja demonstrată.

```text
SUMO (proces separat)
  ↕ TCP / TraCI
Adaptor (procesul Python principal)
  ├─ Queue N → proces senzor N ─┐
  ├─ Queue E → proces senzor E ─┤
  ├─ Queue S → proces senzor S ─┼─ MQTT QoS 1 → Mosquitto → gateway → SQLite
  └─ Queue W → proces senzor W ─┘
```

Măsurătorile provin exclusiv din SUMO în execuție. Adaptorul TraCI le citește după fiecare pas; procesele senzor publică imediat în MQTT, fără fișiere intermediare. Rapoartele XML SUMO sunt păstrate pentru analiză, dar nu sunt sursa mesajelor MQTT. Un abonat separat, `monitor`, observă mesajele livrate de broker fără să intervină în gateway.

## Responsabilități

- `sources.py`: citire TraCI, un cadru cu patru citiri, una per direcție. Adaptorul este singurul client TraCI și avansează simularea.
- `sensors.py`: patru procese create cu `multiprocessing` și metoda spawn; fiecare are propria conexiune MQTT. Cozile locale sunt limitate. Adaptorul așteaptă confirmarea publicării înainte de următorul cadru. Oprirea unui senzor lasă celelalte procese să continue.
- `transport.py`: conectare, confirmarea abonării și publicare QoS 1 cu timeout.
- `gateway.py`: validare, logare, monitorizarea inactivității după timpul real și stocare SQLite. Cheia `(run_id, sensor_id, sequence)` elimină duplicatele.
- `monitor.py`: abonat MQTT independent pentru demonstrarea transmiterii.
- `tracing.py`: evenimente JSON cu identificator comun, timestamp UTC, topic și payload.
- `messages.py`: contract comun și verificarea tipurilor, unităților, valorilor finite și identității senzorului.

PUBACK confirmă primirea la broker, nu finalizarea scrierii în SQLite. Această versiune presupune că gateway-ul este pornit înainte de sursă și rămâne activ. Nu oferă încă reluare după căderea brokerului sau gateway-ului. Confirmarea de aplicație și stocarea offline pot fi adăugate dacă devin cerințe.

## Scenariul rutier

- Nod central `J0`, patru brațe de aproximativ 300 m și opt segmente orientate.
- O bandă pe sens, viteză maximă 13.89 m/s, circulație numai înainte, fără viraje sau pietoni în scenariul inițial.
- Patru E2 de câte 150 m, terminând cu 1 m înainte de capătul intrării; E2 observă numai zona acoperită, nu întreaga coadă dacă aceasta depășește zona.
- Patru E1 la 10 m după intrarea pe segmentele de ieșire.
- Faze fixe: NS verde 30 s, galben 3 s, toate roșu 2 s; EV verde 30 s, galben 3 s, toate roșu 2 s. Indicii fazelor sunt 0–5.
- Ordinea legăturilor semaforice: 0=N, 1=E, 2=S, 3=W. Stările sunt `GrGr`, `yryr`, `rrrr`, `rGrG`, `ryry`, `rrrr`.
- Fluxuri de aproximativ 480 vehicule/oră pe fiecare intrare NS și 300 pe fiecare intrare EV; cerere până la 1800 s, final configurat la 2400 s, seed 42.

Când este controlată prin TraCI, durata este stabilită de `--steps`, nu de finalul configurat pentru rularea autonomă. La pași de 1 s, `--steps 2400` reproduce durata completă. Datele detectorilor sunt citite după fiecare pas.

## Următoarele etape

1. Controler bazat pe cozi, cu durate minime/maxime de verde și limitarea așteptării direcțiilor mai puțin încărcate.
2. Comenzi de la gateway/controler către adaptor, aplicate la momente bine definite ale simulării. Tranzițiile galben și toate roșu trebuie păstrate.
3. Compararea controlului adaptiv cu programul fix pe aceleași scenarii și semințe. Evaluare prin timp de așteptare, lungimea cozilor, durată și vehicule evacuate; se includ vehiculele neterminate.
4. Viraje, mai multe benzi sau ML numai după verificarea primei versiuni.
