# Verificări

## Windows — 1 noiembrie 2026

Mediu: Python 3.14.0, SUMO nativ 1.28.0, Mosquitto 2.1.2, paho-mqtt 2.1.0,
TraCI și sumolib 1.28.0. Dependențele au fost instalate în mediul virtual al proiectului.

- **59 de teste trecute**, cu `TRAFFICCAST_TEST_SUMO=1`, fără teste omise.
- Cele două scenarii sunt verificate cu SUMO și broker Mosquitto real.
- Sunt verificate schema v2 pe bandă, compatibilitatea v1 și extinderea bazei
  existente fără pierderea rândurilor, golurile de secvență și citirile indisponibile.
- Gateway-ul este verificat ca receptor de date: nu publică decizii de
  semaforizare, iar sursa păstrează programul fix chiar dacă pe broker există
  mesaje externe pe un topic de comenzi.
- Demonstrația de 120 de pași produce **480 de măsurători**, cu payload-uri
  identice la citire, publicare, PUBACK, observare, recepție și salvare în SQLite.
- Sunt verificate brokerul propriu, folosirea unui broker extern și păstrarea
  acestuia după oprire, portul ocupat, căile cu spații și oprirea unui senzor.
- Agregarea verifică viteza ponderată, ocuparea, coada maximă, citirile fără viteză
  și detectoarele lipsă.
- Modul continuu este verificat cu un final de cerere scurtat în copii temporare:
  vehicule noi apar după final, timpul nu se resetează și oprirea coordonată
  păstrează toate mesajele confirmate în SQLite și în observator.
- Rularea finită completă a fiecărui scenariu introduce și evacuează **780 de
  vehicule**, fără coliziuni, teleportări, vehicule eliminate sau neterminate.
  În scenariul urban sunt folosite toate cele 12 rute și ambele benzi pentru înainte.
- Numărarea trecerilor E1 finalizate produce 780 pentru fiecare scenariu,
  cu deduplicare inclusiv la schimbarea benzii în zona detectorului.
- SUMO-GUI a fost pornit automat prin TraCI pentru 5 pași și s-a închis după
  terminare. Această verificare confirmă pornirea și închiderea, nu reprezintă
  o inspecție vizuală completă a aspectului.
- Demonstrația completă cu GUI și brokerul existent a salvat 20 de mesaje
  pentru 5 pași și a închis automat procesele proprii și SUMO-GUI.
- Profilurile variabile sunt verificate și în modul continuu, inclusiv
  depășirea duratei unui ciclu și păstrarea stării simulării.
- Sintaxa scripturilor Bash a fost verificată cu Git Bash.

Brokerul instalat ca serviciu a fost verificat printr-o conexiune MQTT 3.1.1
și a rămas pornit. Testele folosesc porturi și copii temporare de scenariu.

Compatibilitatea Linux este păstrată în implementarea comună și în ghid;
suita versiunii noi **nu a fost rerulată pe Linux în această sesiune**.
Este disponibil numai WSL docker-desktop, iar motorul Docker nu rulează.
Verificarea Fedora de mai jos privește versiunea inițială.

Reproducere pe Windows:

```powershell
$env:TRAFFICCAST_TEST_SUMO = '1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m trafficcast demo --external-broker --steps 120 --pace 0
```

Comenzile Linux și instrucțiunile complete sunt în [pornire.md](pornire.md).

## Istoric Fedora — 31 octombrie 2026

Flux verificat: **SUMO în execuție → TraCI → patru procese senzor → Mosquitto → gateway → SQLite**, cu observator MQTT independent.

Mediu: Fedora 44, Python 3.14.8, SUMO Flatpak 1.28.0, Mosquitto 2.1.2, paho-mqtt 2.1.0 și TraCI 1.28.0.

- Suita completă cu `TRAFFICCAST_TEST_SUMO=1`: **17 teste trecute**, fără teste omise.
- Testul de integrare urmărește 320 de măsurători SUMO și verifică egalitatea payload-ului la toate cele șase etape din jurnale, apoi egalitatea cu înregistrările SQLite.
- Demonstrația prin `scripts/demo.sh --steps 120 --pace 0 --run-id sumo-live-20261031`: **480 de măsurători**, câte 120 pe direcție.
- Sunt exact 480 de evenimente pentru fiecare etapă: `SUMO_READ`, `MQTT_PUBLISH`, `MQTT_PUBACK`, `MQTT_OBSERVED`, `GATEWAY_RECEIVE`, `GATEWAY_STORED`. Payload-urile sunt identice pentru fiecare identificator, inclusiv în baza de date.
- Exemplul [exemplu-transmisie.jsonl](exemplu-transmisie.jsonl) provine din această rulare efectivă: `sumo-live-20261031:E2_N:35`, timp simulat 35 s, trei vehicule observate și ambuteiaj de 5 m.
- Testul opririi unui senzor folosește tot SUMO: celelalte trei procese termină toate cele 80 de cadre, iar gateway-ul anunță inactivitatea direcției oprite.
- Sunt verificate și respingerea datelor invalide și deduplicarea QoS 1.
- Sintaxa Bash și whitespace-ul diff-ului: fără erori.

Integrarea a fost verificată fără interfață grafică. Deschiderea vizuală SUMO-GUI nu a fost verificată în această etapă. Nu sunt implementate încă decizii adaptive și nu este raportată o îmbunătățire a traficului.

Reproducere: [pornire.md](pornire.md). Testele folosesc directoare și porturi temporare; brokerul trebuie să fie disponibil în PATH. Măsurătorile de trafic din demonstrație și din testele fluxului provin din SUMO.
