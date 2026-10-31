# Verificare locală — 31 octombrie 2026

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
