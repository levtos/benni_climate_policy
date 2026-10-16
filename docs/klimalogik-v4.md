# Lastenheft Klimalogik v4 – benni_climate_policy

Status: Entwurf zur Freigabe durch Benni · Stand 2026-10-05
Ersetzt fachlich: Klimalogik v3 (Mai/Juni 2026)
Grundlagen: Climate-Ist-Audit 2026-10-05 · Core-Contracts-Master-Entscheidungsakte Phase 4 (u. a. P4-56, P4-57, P4-60, P4-61, P4-62, P4-64) · Entscheidungen Benni 2026-10-05
Kennzeichnung: [V] technisch verifiziert · [B] Angabe Benni · [H] Hypothese · (abgeleitet) = Rechnung aus [V]/[B]

## 0. Zweck und Grenzen
- Umbau der bestehenden Policy, kein Neubau. Ziel: schlanke, verständliche Logik; der Raumsensor entscheidet.
- Die Policy ist profilfähig. Profile: `benni` (Umsetzung U1–U7) und `eltern` (U8). Gleiche Logik, Unterschiede nur in der Profil-Konfiguration (§3a).
- Umsetzung erst, wenn die Contracts aus §12 (mindestens P1 und P2) in Core Contracts gebaut und live verifiziert sind. Ausnahme: U0 nach ausdrücklicher Freigabe durch Benni.
- Nicht Gegenstand: Duftstecker, allgemeine Apply-Architektur (Ausnahme: Plan-Hash, §7), Vacation/Langzeitabwesenheit.
- Alle Zahlen sind Startwerte und im Tuning-UX einstellbar. Nichts ist fest verdrahtet.

## 1. Begriffe
| Begriff | Bedeutung |
|---|---|
| Raumziel | gewünschte Raumtemperatur laut Raumsensor (°C) |
| Stellwert | Zahl, die an das Eve-Thermostat geschickt wird |
| Eigenmessung | Temperatur, die das Thermostat selbst misst (Heizkörpernische) |
| Modus | Komfort, Normal, Eco, Ruhe, Rescue |
| Takt | heizen bis Ziel + 0,5 K, Pause bis Ziel − 0,5 K |
| Vorhalt | gemessener Abstand Eigenmessung − Raum beim Heizen |
| Außenwert | Garten-Temperatur, korrigiert um gefühlte Temperatur und Prognose |
| Wetterstufe | ungemütlich, frisch, mild, warm |
| Sonnenanteil s | 0…1 aus der erwarteten Strahlung aufs Fenster |
| zuhause | Presence `home` oder `parents`, Heimweg (§5) oder Presence `unknown` |

## 2. Faktenbasis (Auszug, Profil benni)
| Befund | Wert |
|---|---|
| Aqara-Kalibrierung Wohnzimmer, Küche, Bad | −3,5 K; Wohnzimmer-Feuchte −12 % [B][V] |
| Eigenmessung − Raum beim Heizen, Wohnzimmer / Küche | +1,9 / +2,0 K [V] |
| dasselbe in Ruhe | −0,7 / −1,3 K [V] |
| Bad, umgerechnet auf die −3,5-K-Kalibrierung | beim Heizen +0,5 K, in Ruhe +0,1 K (abgeleitet) |
| Beispiel 30.09. | Stellwert 23,0 → Raum blieb bei 21,4 °C [V] |
| Bennis Gewohnheit | 24,5 °C am Thermostat ≈ 22,5 °C Raum [B][V] |
| Wohnzimmer gegen Küche | Median +0,13 K, also dieselbe Luft [V] |
| Aqara-Meldetakt | Median 20–25 min, einzelne Lücken 2–3 h [V] |
| Garten gegen DWD-Station (Tal) | nachts +4,4 K, vormittags +5,2 K, nachmittags ±0 [V] |
| Dusch-Erkennung per Vibration | 10 von 10 [V] |
| Lüfter | 8,7 Läufe/Tag, Median 30 min [V] |

## 3. Zonen und Öffnungen (Profil benni)
| Zone | Räume | Heizkörper | Raumsensor | Relevante Öffnungen |
|---|---|---|---|---|
| Wohnbereich | Wohnzimmer, Küche, Flur, Schlafnische (keine Türen) | Wohnzimmer, Küche | Wohnzimmer-Aqara, Küche als Ersatz | 2 Wohnzimmerfenster, Terrassentür. Die Wohnungstür zählt NICHT |
| Bad | Bad (kein Fenster) | Bad | Bad-Aqara (hängt am Heizkörper, nur Feuchte/Diagnose) | keine |

## 3a. Profile
- Jedes Profil definiert: Zonen; je Zone Raumsensor(en), Thermostate und relevante Öffnungen; vorhandene Bad-Entfeuchtung (Lüfter ja/nein); eigene Matrix (§14).
- Die Öffnungsregel (§5, Zeile 0) gilt je Zone: Eine nicht sicher geschlossene Öffnung der Zone schaltet die Heizung dieser Zone aus.
- Nicht konfigurierte Eingänge oder Funktionen sind `not_applicable` (Konfiguration, kein Fehler, kein `unknown`), z. B. Lüfter, Heimweg (Distanz/Richtung), erwartete Strahlung, einzelne Bio-Zustände. Die zugehörige Regel entfällt, der Rest läuft unverändert.
- Eltern-Profil (Planungsstand) [B]:
  - Wohnbereich Wohnzimmer + Küche, größer als bei Benni, 2 Eve Thermo, Fenster und Terrassentür mit Kipp-Kontakten.
  - Schlafzimmer separat, ohne Heizkörper.
  - Bad mit Eve Thermo und Fensterkontakt, kein Lüfter. Badfenster nicht sicher zu → Bad-Heizung aus.
  - Gemeinsamer Bio-Zustand beider Eltern; Haushalts-Presence (ODER über beide).
- Matrix je Profil. Das Eltern-Profil startet mit den Werten aus §14 und wird separat justiert. Vorhalt je Thermostat in der Beobachtungswoche des Profils messen.

## 4. Modi
| Modus | Bedeutung | Grundwert |
|---|---|---|
| Komfort | warm | je Saison, Start 22,0 |
| Normal | leicht abgesenkt | je Saison, Start 20,5 |
| Eco | sparsam (länger weg) | 19,0 |
| Ruhe | Heizung aus; nur Notanker bei geschlossenem Fenster | 18,5 (Mindesttemperatur) |
| Rescue | manueller Knopf, Wohnbereich | 24,0 fest |

Gefühlte Innentemperatur wird nicht gerechnet. Geregelt wird auf die echte Raumtemperatur; „gefühlte" Einflüsse wirken über das Raumziel (§6).

## 5. Modusauswahl Wohnbereich (die erste passende Zeile gewinnt)
| # | Bedingung | Ergebnis |
|---|---|---|
| 0 | eine relevante Öffnung der Zone nicht `closed` + `valid` + `fresh` (`open`, `tilted`, `unknown`, `stale`, Konflikt, …) | AUS (10 °C, Modus aus), sofort, hart |
| 1 | Rescue aktiv | Rescue |
| 2 | Saison „Heizbetrieb aus" ODER Wetterstufe warm ODER Bio `sleep` | Ruhe |
| 3 | `away` seit > 3 h und nicht Heimweg | Eco |
| 4 | `away` bis 3 h und nicht Heimweg | Normal |
| 5 | Bio `pre_sleep` | Normal |
| 6 | Uhrzeit außerhalb des Tagfensters 06:00–22:00 | Normal |
| 7 | sonst | Komfort |

- Heimweg = Presence `away` UND Richtung `approaching` UND Distanz ≤ 1000 m. Ein Heimweg gilt als zuhause.
- Die Away-Dauer zählt ab `since_at` des Übergangs nach `away` (neustartfest).
- Bio `waking`/`awake` fallen in Zeile 6/7. Ist ein Fenster gekippt, gilt Zeile 0.
- Presence `unknown` wird wie zuhause behandelt, Bio `unknown` wie `awake`.

Beispiele:
- 23:30 wach, Fenster zu → Normal.
- 23:45 Fenster gekippt → AUS.
- Eingeschlafen, Fenster zu → `sleep` → Ruhe (heizt erst unter 18,5).
- 10 Uhr weg, 13:30 noch weg → Eco.
- 900 m entfernt, nähert sich → Komfort.

## 6. Raumziel
Raumziel = Grundwert(Modus, Saison) − Sonnenabzug + Bodenaufschlag + Wetterverschiebung, begrenzt auf 18,5 … 24,0 °C.
- Sonnenabzug, Boden und Wetter gelten nur, wenn zuhause. Unterwegs (Eco, Normal unterwegs) gilt der reine Grundwert.
- Ruhe = 18,5 ohne Aufschläge. Rescue = 24,0 ohne Aufschläge.

### 6.1 Außenwert und Wetterstufe
Außenwert = T_Garten + 0,5 × (T_gefühlt − T_Garten) + 0,5 × Δ_Prognose
- T_gefühlt aus `apparent_temperature.v1` (Garten-Temperatur und -Feuchte, Wind als DWD-Modellwert).
- Δ_Prognose = Prognose(jetzt + 3 h) − Prognose(jetzt), aus DERSELBEN Prognosereihe (nie Absolutwert, wegen Tal-Versatz), begrenzt auf ±2 K.
- Glättung: gleitend 30 min.

| Stufe | Außenwert | Wirkung aufs Raumziel |
|---|---|---|
| ungemütlich | < 5 °C | +0,5 K |
| frisch | 5 bis < 12 °C | ±0 |
| mild | 12 °C bis < Heizgrenze | −0,5 K |
| warm | ≥ Heizgrenze (je Saison) | Modus Ruhe (§5, Zeile 2) |

- Ein Stufenwechsel braucht 0,5 K Abstand über die Grenze.
- Regen (gemessener Niederschlag ≥ 0,1 mm in der letzten Stunde) = eine Stufe kälter, höchstens ungemütlich.
- Wind wirkt nur über die gefühlte Temperatur. Keine separaten Offsets für Schnee, Nebel, Wind oder Sonne.

### 6.2 Sonne (nur Modus Komfort)
- s = 0 bei erwarteter Strahlung ≤ 100 W/m², s = 1 bei ≥ 350 W/m², linear dazwischen.
- Sonnenabzug = s × (Komfort − Normal). Komfort wird dadurch höchstens auf Normal gezogen.
- Ist der Raum trotzdem kalt, heizt der Takt normal.

### 6.3 Boden
Fester Aufschlag je Saison (§14). Keine Berechnung, kein Kälteindex.

### 6.4 Rechenbeispiele
| Lage | Rechnung | Raumziel |
|---|---|---|
| Januar 14:00, −2 °C, windig (gefühlt −6), bewölkt | 22,0 + 1,0 + 0,5 (ungemütlich) | 23,5 |
| Januar 11:00, 3 °C, klar, 420 W/m² (s = 1) | 22,0 − 1,5 + 1,0 + 0,5 | 22,0 |
| Oktober, 9 °C, Regen (gefühlt ≈ 6,5) | Außenwert ≈ 7,8 → frisch → Regen: ungemütlich; 22,0 + 0,5 + 0,5 | 23,0 |
| Oktober, 15 °C, sonnig | mild, s = 1: 22,0 − 1,5 + 0,5 − 0,5 | 20,5 |
| Oktober, 21:30, 21 °C | warm | Ruhe 18,5 |
| Oktober, 23:00, 8 °C, zuhause, wach | Normal: 20,5 + 0,5 + 0 | 21,0 |
| Oktober, 2 h weg | Normal ohne Aufschläge | 20,5 |
| Oktober, 4 h weg | Eco | 19,0 |

## 7. Heizentscheidung und Stellwert (Wohnbereich)
- Raumtemperatur = Fusion Wohnzimmer (primär) → Küche (Ersatz). Beide Heizkörper erhalten dasselbe.
- Takt: heizen, wenn Raum ≤ Ziel − 0,5; Pause, wenn Raum ≥ Ziel + 0,5; dazwischen bleibt der letzte Zustand. Nach einem Neustart gilt im Zwischenbereich „Pause".

| Lage | Stellwert |
|---|---|
| heizen | Ziel + Vorhalt (2,0) + Reserve (1,0), auf 0,5 gerundet, höchstens 27,0 |
| Pause | Modus aus (10 °C) |
| Öffnung nicht sicher zu | Modus aus (10 °C), sofort |
| keine gültige Raumtemperatur | Ziel + Vorhalt (ohne Reserve); das Thermostat regelt selbst |

- Begründung: Das Thermostat misst beim Heizen etwa 2 K zu viel. Die Reserve sorgt dafür, dass immer der Raumsensor abschaltet, nicht das Thermostat (Problem 30.09.).
- Beispiel Winter-Komfort 23,0: heizt ab 22,5, Stellwert 26,0, Pause ab 23,5.
- Apply/Plan-Hash enthält NUR Stellwerte (Thermostat-Soll/Modus, Lüfter), keine Eingangswerte wie den Außenwert.

## 8. Rescue
- Schalter der Climate-Policy (Dashboard/Tuning), nur Wohnbereich, wird nie automatisch eingeschaltet.
- Raumziel 24,0, Stellwert 27,0.
- Ende, je nachdem was zuerst passiert: der Takt schaltet erstmals ab (Raum ≥ 24,5), eine Öffnung geht auf, oder 120 min seit Aktivierung (gemessen ab `since_at`, neustartfest). Danach setzt sich der Schalter selbst zurück.
- Kein Boost: Rescue erhöht nicht die Heizleistung, nur das Ziel.

## 9. Bad – Heizung
| Bedingung | Bad-Ziel |
|---|---|
| relevante Bad-Öffnung nicht sicher zu (nur Profile mit Badfenster) | AUS (10 °C, Modus aus), sofort |
| Saison „Heizbetrieb aus" oder Wetterstufe warm | 18,5 |
| away (ohne Heimweg) | Bad-Eco 19,0 ohne Aufschläge |
| sonst (auch nachts und bei Bio `sleep`) | Bad-Komfort 22,5 + Boden + Wetterverschiebung |

- Stellwert = Bad-Ziel + Bad-Vorhalt (0,0), Modus heizen. Das Thermostat regelt selbst (der Bad-Sensor ist keine Raumwahrheit).
- Keine Sonne, keine festen Zeiten, kein Heizen zum Trocknen, keine Heizpause während der Lüfter läuft.
- Beispiele: Januar, zuhause, ungemütlich → 22,5 + 1,0 + 0,5 = 24,0. Weg → 19,0. Eltern: Badfenster gekippt → AUS.

## 10. Bad – Lüfter
Gilt nur in Profilen mit konfiguriertem Badlüfter (Profil benni ja, Profil eltern nein → `not_applicable`).

| Grund | Start | Ende |
|---|---|---|
| Nutzung | Ereignis Dusche oder Toilette | 30 min nach dem letzten Ereignis (aus `since_at`) |
| Feuchte | Abs. Feuchte Bad − Wohnzimmer > 2,5 g/m³ ODER Anstieg ≥ 15 %-Punkte in 5 min | Differenz < 1,5 g/m³, höchstens 60 min |
| Mindestlüftung | 12 h kein Lauf, nur 06:00–22:00 | 10 min |
| Deckel | 120 min Dauerlauf | 120 min Sperre |

- Feuchte-Referenz nur Wohnzimmer (keine Fusion mit der Küche, andere Luftfeuchte).
- Entfallen: feste Schwellen 75 % und Taupunkt 17 °C; Warten aufs Aufheizen.
- Die Schwellen 2,5/1,5 sind vorläufig: Nach der Wohnzimmer-Kalibrierung (−12 %) liegt die Ruhedifferenz grob bei ~1,6 g/m³ (abgeleitet). In der Beobachtungswoche messen und auf Ruhedifferenz + ~1 setzen.
- Beispiel: Dusche 13:05 → Lüfter an; Differenz 4,0 → läuft weiter bis < 1,5, höchstens 60 min. Bad-Heizung läuft weiter.

## 11. Qualität und Ausfälle
- Eingänge tragen Core-Qualität: `valid`, `held` (innerhalb der Grace verwendbar), `unknown`/`unresolved` mit Grund; nicht konfigurierte Eingänge sind `not_applicable` (§3a).
- Climate erfindet keine Werte und setzt keine Ersatzwerte.

| Ausfall | Reaktion |
|---|---|
| Wohnzimmer-Raumtemperatur | Küche übernimmt (Fusion) |
| beide | Stellwert Ziel + Vorhalt, das Thermostat regelt selbst |
| Bad-Aqara | Bad-Heizung unverändert; Lüfter nur über Nutzung |
| Wohnzimmer-Feuchte | Lüfter ohne Differenz: Nutzung, Anstieg, Höchstdauer |
| Außenwert nicht bestimmbar | keine Wetterverschiebung, keine Wärme-Ruhe; Raum regelt mit der Saison |
| gefühlte Temperatur fehlt | Gewicht 0 |
| Prognose / Niederschlag / Strahlung fehlt | jeweiliger Term = 0 bzw. s = 0 |
| Presence `unknown` | wie zuhause |
| Bio `unknown` | wie `awake` |
| Öffnungskontakt `unknown`/`stale` | Heizung der Zone AUS (K3), Grund in der Diagnose; Core macht `unknown` zentral sichtbar |
| Vibration Dusche/Toilette | Lüfter über Feuchte |

Diagnose pro Zone: eine Begründungszeile, z. B. „Komfort · 22,0 − Sonne 0,8 + Boden 0,5 = 21,7 · Raum 21,1 → heizt · Stellwert 24,5". Dazu ein Vorhalt-Monitor (Eigenmessung − Raum beim Heizen gegen 2,0 K) und der Hinweis „Heizanforderung > 90 min ohne Raumanstieg" (möglicherweise liefert der Kessel nicht [H]).

## 12. Contract-Bedarf und Priorität (Input für die Contract-Ableitung)
Keine neue Vertragsart; Einordnung in die neun Bausteine der Akte (P4-21). Für das Eltern-Profil dieselben Contracts im Core-Profil `eltern`, soweit konfiguriert.

| Prio | Contract / Wahrheit | Bezug Akte | ohne ihn |
|---|---|---|---|
| P1 | Öffnung je Kontakt (benni: WZ links, WZ rechts, Terrassentür; eltern: zusätzlich Badfenster), ereignisbasierte Frische über Lebenszeichen | K3, M14-03 | kein Betrieb der Zone |
| P1 | Raumtemperatur Wohnbereich (Fusion WZ → Küche) | – | kein Betrieb |
| P1 | Raumfeuchte Wohnzimmer; Raumtemperatur/-feuchte Bad | K4 | Lüfter eingeschränkt |
| P1 | Presence: Ort, Distanz, Richtung (eltern: Haushalts-Presence) | P4-62 | wie zuhause |
| P1 | Bio-State (`pre_sleep`, `sleep`, `waking`, `awake`) | P4-60 | wie wach |
| P1 | Ereignisse Dusche/Toilette mit `since_at` (nur benni) | M13-03 | Lüfter nur über Feuchte |
| P2 | Außentemperatur/-feuchte Garten mit DWD-Ersatz | Audit §6.9 | keine Wetterstufe |
| P2 | `apparent_temperature.v1`, `absolute_humidity.v1`; Wind (DWD-Modell, gekennzeichnet) | M30-15 | Gewicht 0 / keine Differenz |
| P3 | Erwartete Strahlung aufs Fenster (einmal in Core, aus der Blind-Control-Berechnung) | K1, C-06 | s = 0 |
| P3 | Prognose-Reihe Temperatur, Niederschlag gemessen (Attribut-Bindings mit Herkunft) | M06-09, M14-09 | Term 0 |

- Bauen ab P1; Go-Live der Policy frühestens mit P1 + P2 (sonst fehlt die Wärme-Ruhe).
- Zonen-Zugehörigkeit als Registry-Metadatum (Area).
- Policy-intern bleiben: Außenwert, Wetterstufe, Sonnenanteil, Bodenaufschlag, Modi, Raumziel, Takt, Vorhalt, Rescue, Lüfterlogik, `shower_active`, `humidity_rise_5m`.

## 13. Umbauschritte
| Schritt | Inhalt | Voraussetzung | Abnahme (Beispiele) |
|---|---|---|---|
| U0 (optional, nur nach Bennis Go) | Heutige Policy: Übergangs- und Pre-Night-Boost entfernen; Nachtrampe unter die Außenfreigabe („Aus ab") stellen | keine | Abend 21 °C außen: kein Boost, keine Nachtrampe |
| U1 | Gerüst: profilfähige Struktur (§3a); Eingänge über CoreContractsClient mit Qualität; Diagnose-Begründungszeile; Plan-Hash nur Stellwerte | P1 live (Profil benni) | Wetteränderung ohne Stellwertänderung → kein Apply |
| U2 | Wohnbereich-Kern: §5 Modusauswahl, §6 ohne 6.1/6.2, §7 Takt und Stellwert, §8 Rescue. Entfernen: Heizwert, Saison-Stufen Aus/Spar/Komfort/Boost, Nachtrampe, 8-h-Regel, free_time, Kälteindex, Bodenplatten-Delta am Thermostat, Mindestlaufzeit | U1 | §15 Nr. 1, 6–13 |
| U3 | Bad und Lüfter: §9, §10. Entfernen: feste Bad-Zeiten, Außenbonus, Feuchte-Grundwärme, Lüfter-Koordination | U1 | §15 Nr. 14–15 |
| U4 | Wetter: §6.1 inkl. Regen und Prognose | P2 live | §15 Nr. 2–5 |
| U5 | Sonne: §6.2 | P3 live | §15 Nr. 2, 4 |
| U6 | Matrix/Tuning: neue Struktur §14 (je Profil), Migration der Startwerte, alte 113 Felder entfernen. UX-Anforderungen liefern (Gestaltung über ChatGPT, UX-Hoheit) | U2–U5 | alle Werte im UX änderbar; Prüfung Komfort ≥ Normal ≥ Eco ≥ Ruhe |
| U7 | Schattenbetrieb alt gegen neu, Beobachtungswoche (Vorhalt, Feuchte-Ruhedifferenz, Lüfterlaufzeit), danach Core Devices für Climate abschalten | U2–U6 | Live/Live Verified durch Benni |
| U8 | Eltern-Profil: Konfiguration nach §3a, eigene Matrix, Anbindung über den Core-Adapter von haos_eltern | Core-Profil `eltern` mit P1 + P2 live; Adapter haos_eltern | Badfenster gekippt → Bad AUS; Lüfterlogik `not_applicable`; Wohnbereich verhält sich wie §15 |

Go-Live Profil benni frühestens nach U4. U1–U7 werden bereits profilfähig gebaut, damit U8 nur Konfiguration ist.

## 14. Matrix (Startwerte je Profil; alles im Tuning-UX)
Saisons (Monate frei zuordenbar):
| Saison | Monate | Heizbetrieb | Heizgrenze °C | Komfort °C | Normal °C | Boden K |
|---|---|---|---|---|---|---|
| Winter | Dez–Feb | an | 15,5 | 22,0 | 20,5 | +1,0 |
| Kalte Übergangszeit | Mär, Nov | an | 16,0 | 22,0 | 20,5 | +1,0 |
| Übergangszeit | Apr, Okt | an | 17,0 | 22,0 | 20,5 | +0,5 |
| Warme Übergangszeit | Mai, Sep | an | 18,5 | 22,0 | 20,5 | +0,5 |
| Sommer | Jun–Aug | aus | 19,5 | 22,0 | 20,5 | 0 |

Global:
| Gruppe | Werte |
|---|---|
| Ziele | Eco 19,0 · Mindesttemperatur/Ruhe 18,5 · Rescue 24,0 · Rescue-Höchstdauer 120 min · Raumziel max 24,0 |
| Alltag | Tagfenster 06:00–22:00 · Eco nach 3 h weg · Heimweg-Distanz 1000 m |
| Außenwert | Gewicht gefühlt 0,5 · Prognose-Horizont 3 h · Prognose-Gewicht 0,5 · Prognose-Deckel ±2 K · Glättung 30 min |
| Wetterstufe | Grenze ungemütlich 5 °C · Grenze mild 12 °C · Hysterese 0,5 K · ungemütlich +0,5 K · mild −0,5 K · Regen ab 0,1 mm/h |
| Sonne | Beginn 100 W/m² · voll 350 W/m² |
| Takt und Thermostat | ein −0,5 K · aus +0,5 K · Vorhalt je Thermostat (benni: WZ 2,0, Küche 2,0, Bad 0,0) · Reserve 1,0 · Stellwert max 27,0 |
| Bad | Komfort 22,5 · Eco 19,0 |
| Lüfter (nur Profile mit Lüfter) | Nutzungs-Hold 30 min · Differenz ein 2,5 g/m³ · aus 1,5 g/m³ · Anstieg 15 %/5 min · Feuchte-Lauf max 60 min · Deckel 120 min · Sperre 120 min · Mindestlüftung nach 12 h · Dauer 10 min |

Summe Profil benni: 65 Werte plus Monatszuordnung (vorher 113 plus fest verdrahtete Konstanten). Das Eltern-Profil hat keine Lüfterwerte. DWD-Ersatzzeiten und Presence-Radien sind Core-Konfiguration.

## 15. Abnahme-Szenarien (Profil benni)
| Nr | Lage | Erwartung |
|---|---|---|
| 1 | Jan 14:00, zuhause, −2 °C windig, Raum 22,8 | Komfort, Ziel 23,5, heizt, Stellwert 26,5 |
| 2 | Jan 11:00, 3 °C, 420 W/m², Raum 22,4 | Ziel 22,0, keine neue Heizung (im Takt-Band) |
| 3 | Okt 16:00, 9 °C, Regen | Ziel 23,0, Stellwert 26,0 beim Heizen |
| 4 | Okt 12:00, 15 °C, sonnig, Raum 19,9 | Ziel 20,5, heizt (≤ 20,0) |
| 5 | Okt 21:30, 21 °C | Ruhe, Raum 22 → aus; kein Boost |
| 6 | Okt 23:00, wach, 8 °C | Normal, Ziel 21,0 |
| 7 | 00:30 `pre_sleep` → 00:40 Fenster gekippt → 01:15 `sleep` | Normal → AUS → AUS |
| 8 | eingeschlafen, Fenster zu, Raum 20,3 | Ruhe, aus |
| 9 | weg 2 h / 4 h | Normal 20,5 / Eco 19,0 |
| 10 | weg, 900 m, `approaching`, frisch | Komfort 22,5 (Okt), Stellwert 25,5 |
| 11 | `parents` | wie zuhause |
| 12 | Rescue 23:30 Januar | Stellwert 27,0; Ende bei Raum ≥ 24,5 oder nach 120 min |
| 13 | Wohnzimmer-Sensor aus / beide aus / Fensterkontakt `unknown` | Küche / Ziel + 2,0 selbstregelnd / AUS mit Grund |
| 14 | Dusche 13:05, Differenz 4,0 | Lüfter bis Differenz < 1,5 (max 60 min), Bad heizt weiter |
| 15 | Toilette 02:10 | Lüfter bis 02:40 |

## 16. Annahmen
- Die Wohnzimmer-/Küchen-Kalibrierung −3,5 K galt bereits im Messzeitraum 24.09.–03.10. (Vorhalt 2,0 gültig).
- Eve öffnet das Ventil voll, wenn der Stellwert deutlich über der Eigenmessung liegt [H]; Stellwert-Raster 0,5 K.
- Erwartete Strahlung in W/m² auf der Fensterebene.
- Das Bad bleibt nachts Komfort, wenn zuhause.
- Innenfeuchte im Wohnbereich nur als Lüfter-Referenz und Diagnose (Feuchtekomfort später optional).

## 17. Nachtrag für die Akte (P4-65, Vorschlag)
- Boost entfällt vollständig (vorher „keine Entscheidung", P4-61 §6).
- Bodenplatten-Delta ist kein Core-Zonenwert, sondern eine Saison-Konstante der Policy.
- Climate: Presence `unknown` → wie zuhause; Bio `sleep` → Ruhe.
- Climate-Heimweg über Distanz und Richtung (P4-62 §4), Startwert 1000 m.
- Climate ist profilfähig; Eltern-Profil mit Badfenster als relevanter Bad-Öffnung, ohne Lüfter.
