# Climate Policy Logic

Kurzform: Aussen entscheidet, was erlaubt ist. Innen entscheidet, ob es gebraucht wird. Apply setzt hoch oder runter.

## Aussenfreigabe

Die Aussenfreigabe bewertet den Heizwert, Wetter, Forecast und Saisonband. Daraus entsteht die maximal erlaubte Stufe: Aus, Eco, Komfort oder Boost. Diese Stufe ist eine Freigabe, keine Heizanforderung.

Die gefuehlte Aussentemperatur wird in der Policy aus Rohwerten berechnet:

- reale Aussentemperatur
- Aussenluftfeuchte
- Windgeschwindigkeit

Ein fertig berechneter Feels-like-Sensor wird nicht mehr als fachlicher Input verwendet.

## Innenbedarf

Wohnzimmer und Kueche nutzen eine gemeinsame Wohnbereichsmatrix. Das Bad nutzt eine eigene Matrix. Jede Stufe hat:

- `heat_on_below`: darunter darf die freigegebene Stufe aktiv heizen
- `heat_off_at`: ab hier wird nicht nachgeheizt
- `min_hold_minutes`: vorbereitete Mindestdauer gegen Flapping

Liegt der Raum ueber `heat_off_at`, entsteht ein Downshift-Plan mit `room_temperature_above_target_no_heating` oder `bath_temperature_above_target_no_heating`.

## Zieltemperaturen

### Bad: Legacy-Hotfix v0.1.13

Entscheidung vom 01.11.2026 in [Issue #37](https://github.com/Levtos/benni_climate_policy/issues/37):
Grundwaerme 22,0 Grad, Komfortbasis 23,0 Grad plus bestehendem Aussenbonus.
Die Bad-Matrix schaltet Grundwaerme unter 21,5 Grad ein und ab 22,5 Grad aus
(Haltewert 20 Minuten); Komfort nutzt 22,5/23,5 Grad (30 Minuten).
Feuchte-Grundwaerme bleibt bei Ziel 22,0 und Abschaltgrenze 22,5 Grad.
Der bestehende Maximum-Abgleich verhindert auch bei abweichendem Tuning,
dass Feuchte-Grundwaerme Ziel oder Abschaltgrenze der normalen Grundwaerme senkt.
Schutzprofil, fehlende Quellen, Aussenfreigabe, Bodenaufschlag und Apply bleiben unveraendert.
Diese Entscheidung ersetzt fuer das Bad die alten Werte und `late_morning`
aus dem [Klimalogik-Lastenheft](https://github.com/Levtos/einhornzentrale/blob/main/docs/lastenhefte/reviewed/klimalogik/lastenheft.md).
Sie gibt keinen Umbau nach #33 oder an Core Contracts frei.

Die Combined-Sensoren reichen die Core-State-Werte durch. Geprueft am
[Producer-Stand c9408fa](https://github.com/Levtos/benni-core-state/blob/c9408fa33f2914b1c5f7316738cb38b43add33b5/custom_components/benni_core_state/const.py#L168):

- `day_state`: `early_night`, `late_night`, `early_morning`, `forenoon`,
  `midday`, `afternoon`, `late_afternoon`, `evening`, `late_evening`.
- `day_context`: `werktag`, `wochenende`, `frei`.
  [Feiertage werden als `frei` ausgegeben](https://github.com/Levtos/benni-core-state/blob/c9408fa33f2914b1c5f7316738cb38b43add33b5/custom_components/benni_core_state/logic.py#L1338).

Das freie Komfortfenster nutzt `forenoon`; `feiertag` wird zusaetzlich zu den
bestehenden Aliaswerten akzeptiert. Werktags bleibt `early_morning`, taeglich
bleibt `late_evening`, jeweils mit der bestehenden T_eff-Grenze.

Gespeicherte Config-Entry-Optionen haben weiterhin Vorrang; es gibt keine
automatische Migration. Benni prueft bzw. setzt im Tuning-UX:

| Options-Schluessel | Neuer Standard |
|---|---:|
| `bath_setpoint_ground` | 22.0 |
| `bath_setpoint_comfort` | 23.0 |
| `indoor_bathroom_grundwaerme_heat_on_below` | 21.5 |
| `indoor_bathroom_grundwaerme_heat_off_at` | 22.5 |
| `indoor_bathroom_grundwaerme_min_hold_minutes` | 20 |
| `indoor_bathroom_komfort_heat_on_below` | 22.5 |
| `indoor_bathroom_komfort_heat_off_at` | 23.5 |
| `indoor_bathroom_komfort_min_hold_minutes` | 30 |
| `bath_humidity_ground_heat_target` | 22.0 |
| `bath_humidity_ground_heat_off_at` | 22.5 |

Alle Werte bleiben einstellbar. Die bestehenden Temperaturgrenzen von 5 bis
30 Grad und Haltewerte von 0 bis 240 Minuten umfassen die neuen Standards.
Die Haltewerte und Feuchtewerte sind numerisch unveraendert; alte explizite
Temperaturwerte koennen die neuen Defaults weiterhin uebersteuern.

Der Plan weist drei Werte aus:

- `policy_target_temperature`: fachlicher Komfortwert, z. B. Eco 21,0 Grad
- `floor_slab_delta_current`: technischer Bodenplatten-Aufschlag
- `thermostat_target_temperature`: Zielwert, der ans Thermostat geht

Der Innenbedarf wird gegen die gemessene Raumtemperatur bewertet, nicht gegen den technisch erhoehten Thermostat-Zielwert.

## Dynamisches Bodenplatten-Delta

Das Delta wird getrennt von `floor_slab_tau` berechnet. Tau bleibt die Traegheit in der Heizwertberechnung. Delta ist der aktuelle technische Aufschlag auf den Thermostat-Zielwert.

Das dynamische Modell nutzt einen kleinen 3-Tage-Kaelteindex:

- gestern: kleiner In-Memory-Tageswert, falls vorhanden
- heute: aktuelle reale Aussentemperatur
- morgen: Forecast um ca. 12 Uhr, gecached ueber den vorhandenen Weather-Forecast

Fehlen Werte, wird die Qualitaet als `degraded` oder `fallback` markiert. Es gibt keine sekundenweisen Polls und keine schweren History-Abfragen pro Recalculate.

## Apply und Downshift

Apply setzt nicht nur hoch. Ein Plan kann auch bewusst herunterregeln oder ausschalten. Downshifts durch Fenster/Tuer, Raum ueber Ziel oder Bad ueber Ziel nutzen denselben Off-Pfad und duerfen nicht durch Cooldown blockiert werden.
