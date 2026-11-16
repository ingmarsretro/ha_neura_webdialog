# Neura Webdialog für Home Assistant

Home-Assistant-Integration für die Weboberfläche einer Neura-Webdialog-Wärmepumpe. Sie liest die Schema-Seite und stellt die Werte auf zwei Wegen bereit:

- MQTT, unverändert auf den bisherigen Topics, QoS 0, ohne Retain, Zahlen als Text
- Entitäten direkt in Home Assistant

In diesem Repository stehen keine Zugangsdaten, Benutzernamen oder Standort-IP-Adressen. Die trägst du nach dem Installieren in Home Assistant ein. Gespeichert werden sie nur in der Home-Assistant-Konfiguration.

Autor ist bihlo. Die Lizenz ist proprietär, siehe [LICENSE](LICENSE). Lizenzen und Autoren der verwendeten Bibliotheken stehen in [NOTICE](NOTICE), die Kurzform in [AUTHORS](AUTHORS).

## Dateien für GitHub

Lade den Inhalt dieses Ordners als Repository hoch. Der Ordner `datasauger/` gehört nicht dazu. Darin liegt die alte PHP-Fassung mit Zugangsdaten, und `.gitignore` schließt ihn aus.

Diese Dateien und Ordner hochladen:

- `AUTHORS`
- `LICENSE`
- `NOTICE`
- `README.md`
- `hacs.json`
- `.gitignore`
- `custom_components/neura_webdialog/`
- `tests/`

Neues GitHub-Repository anlegen, diese Dateien auf den Branch `main` legen. Ein Release ist nicht nötig. Wer eine Version in HACS sehen will, setzt ein Tag `v1.0.0`. Das entspricht der Version in `custom_components/neura_webdialog/manifest.json`.

Öffentliches und privates Repository funktionieren beide. Bei einem privaten Repository braucht HACS ein GitHub-Token mit Zugriff auf dieses Repository. Das Token wird in HACS unter Konfiguration eingetragen, nicht in diesem Projekt.

## In Home Assistant über den GitHub-Link hinzufügen

Home Assistant allein hat kein Feld für einen GitHub-Link. Der Link wird in HACS eingetragen. HACS muss vorher installiert sein. Voraussetzung für die Integration ist Home Assistant 2024.11 oder neuer.

1. HACS öffnen.
2. Integrationen öffnen.
3. Das Menü mit den drei Punkten öffnen und **Benutzerdefinierte Repositories** wählen.
4. Die Repository-URL einfügen, zum Beispiel `https://github.com/DEIN-KONTO/DEIN-REPOSITORY`.
5. Als Kategorie **Integration** wählen und hinzufügen.
6. **Neura Webdialog** in HACS suchen und herunterladen.
7. Home Assistant neu starten.
8. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Neura Webdialog**.

Danach fragt Home Assistant nach der Wärmepumpe und nach MQTT. Nichts davon ist vorausgefüllt außer technischen Vorgaben, die keine Zugangsdaten sind.

| Feld | Voreinstellung |
| --- | --- |
| Adresse der Wärmepumpe | leer |
| Benutzername | leer |
| Passwort | leer |
| Abfrageintervall | 60 Sekunden |
| MQTT veröffentlichen | an |
| MQTT-Broker | leer |
| MQTT-Port | `1883` |
| MQTT-Client-ID | `neura_webdialog` |
| MQTT-Benutzer und Passwort | leer |

Adresse, Benutzer, Passwort und Broker-Adresse eintragen. Läuft am Broker bereits ein Programm mit der Client-ID `neura_webdialog`, eine andere ID eintragen. MQTT lässt sich im Formular abschalten. Die Entitäten werden dann trotzdem aktualisiert.

Beim Speichern prüft Home Assistant die Anmeldung an der Wärmepumpe. Ist MQTT aktiv, wird auch der Broker geprüft. Dieselben Felder lassen sich später in den Integrationseinstellungen ändern. Ein leeres Passwortfeld behält dort das gespeicherte Passwort.

## MQTT

| Topic | Inhalt |
| --- | --- |
| `Neura/loginStatus` | `1` nach Anmeldung, `0` wenn das Login abgelehnt wird |
| `Neura/status/Estrichtemperatur` | Temperatur |
| `Neura/status/Raumtemperatur` | Temperatur |
| `Neura/status/Boiler_E_patrone` | `1` oder `0` |
| `Neura/status/Boilertemperatur` | Temperatur |
| `Neura/status/Vorlauf` | Temperatur |
| `Neura/status/Ruecklauf` | Temperatur |
| `Neura/status/Kompressor_ein` | Temperatur |
| `Neura/status/Kompressor_aus` | Temperatur |
| `Neura/status/Umschaltventil_Boilerladung` | `1` oder `0` |
| `Neura/status/Waermepumpe` | `1` oder `0` |
| `Neura/status/Umwaelzpumpe` | `1` oder `0` |

Temperaturen werden wie in der früheren PHP-Fassung gelesen: `°C` wird entfernt, ein Komma beendet die Zahl. Schaltwerte sind nur bei exakt `ON` eine `1`.

## Entitäten

Alle Werte hängen am Gerät **Neura Webdialog**.

- `sensor.neura_screed`, `sensor.neura_room`, `sensor.neura_cylinder`
- `sensor.neura_flow`, `sensor.neura_return`, `sensor.neura_comp_in`, `sensor.neura_comp_out`
- `binary_sensor.neura_heater_rod`, `binary_sensor.neura_cylinder_pump`
- `binary_sensor.neura_heatpump_2`, `binary_sensor.neura_circulator_pump`
- `binary_sensor.neura_login`

In der deutschen Oberfläche heißen sie Estrichtemperatur, Raumtemperatur, Boiler E-Patrone, Boilertemperatur, Vorlauf, Rücklauf, Kompressor ein, Kompressor aus, Umschaltventil Boilerladung, Wärmepumpe, Umwälzpumpe und Anmeldung.

Fehlt auf der Schema-Seite ein einzelnes Feld, werden die übrigen Werte trotzdem veröffentlicht. Der fehlende Wert bleibt auf dem letzten Stand. Ist die Weboberfläche nicht erreichbar, werden die Entitäten unavailable und es wird nichts per MQTT gesendet. Wird das Login abgelehnt, geht `Neura/loginStatus` auf `0` und die Entität Anmeldung auf aus.

## Lizenz und Autoren

| Bestandteil | Autor | Lizenz |
| --- | --- | --- |
| Diese Integration | bihlo | proprietär, siehe LICENSE |
| paho-mqtt | Eclipse Foundation und Mitwirkende | EPL-2.0 oder BSD-3-Clause |
| aiohttp | aio-libs | Apache-2.0, Bestandteil von Home Assistant |
| php-mqtt/client, nur die alte Fassung | Marvin Mall | MIT |
| phpgt/dom, phpgt/cssxpath, phpgt/propfunc, nur die alte Fassung | Greg Bowler und Mitwirkende | MIT |
| guzzlehttp/guzzle, nur die alte Fassung | Michael Dowling, Graham Campbell und Mitwirkende | MIT |

Die PHP-Bibliotheken werden von dieser Integration nicht mitgeliefert. Die vollständige Liste steht in [NOTICE](NOTICE).

## Protokoll

```yaml
logger:
  logs:
    custom_components.neura_webdialog: debug
```

Debug zeigt die gelesenen Zahlen und die MQTT-Payloads. Passwörter werden nicht geloggt.
