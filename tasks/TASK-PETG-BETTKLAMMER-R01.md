# TASK – PETG-Bettklammer + separater Nubsi – R01

Status: **KONSTRUKTIONSAUFTRAG / TESTREVISION**
Quelle: Nutzerfreigabe vom 2026-08-29
GitHub Issue: #1

## Auftrag

Konstruiere eine erste druckbare Testrevision **R01** bestehend aus zwei **separaten PETG-Bauteilen**, die gemeinsam auf derselben Druckplatte gedruckt werden:

1. PETG-Klammer für die Filztasche am Bett-Kopfteil.
2. Kleiner PETG-Nubsi/Noppen nach der verbindlich übertragenen Fotoreferenz.

Die beiden Bauteile dürfen geometrisch NICHT miteinander verbunden werden.

## VERBINDLICH – KLAMMER

- Material: **PETG**
- Klammerbreite: **20 mm**
- Schenkellänge / Gesamthöhe: **40 mm von ganz oben nach ganz unten** der Klammer
- Material-/Wandstärke: **2,0 mm**
- Bettprofil / Chromleiste: **20,0 mm tief** – vom Nutzer gemessen/bestätigt
- Filzdicke an der Klemmstelle: **2,0 mm** – vom Nutzer gemessen/bestätigt
- Vorhandener Chromüberstand gegenüber der angrenzenden Bettfläche: **2,0 mm** – vom Nutzer gemessen/bestätigt
- Der 2,0-mm-Chromüberstand sitzt direkt oben an der Chromleiste und läuft als rechteckige gerade Kante entlang.
- Grundprinzip: federnde, von oben aufgeschobene **U-Klammer** über Chromprofil + Filz.
- Die Verzahnung sitzt auf der **langen Innenseite des betreffenden Klammerschenkels**.
- Verzahnung: **viele kleine, direkt aneinandergereihte Zacken / feine Verzahnung**, nicht wenige weit auseinanderliegende Einzelzacken.
- Keine zusätzlichen Funktionen oder Befestigungsprinzipien ergänzen.

## TECHNISCH NOTWENDIG – KLAMMER

- Lichte Aufnahme muss 20,0 mm Chromprofil + 2,0 mm Filz aufnehmen.
- Nur technisch notwendiges PETG/FDM-Montagespiel ergänzen und dokumentieren.
- Belastungsgerechter Klammerbogen ohne scharf belastete 90°-Innenecke.
- Verzahnung so ausrichten, dass sie beim Aufschieben über den 2,0-mm-Chromüberstand gleitet und gegen Abziehen nach oben greift.
- Zahnfüße kerbarm auslegen.
- PETG-Federwirkung und geeignete Druckorientierung prüfen.
- Die zuletzt erzeugte Feinverzahnung mit 18 direkt aneinandergereihten Zähnen, 1,4 mm Teilung und 0,6 mm Eingriff darf als technischer R01-Stand weiterverwendet werden, sofern die erneute SOLL/IST-Prüfung keine Abweichung von den verbindlichen Vorgaben ergibt.

## VERBINDLICH – NUBSI/NOPPEN

Die fünf Originalfotos des Nutzers vom 2026-08-29 wurden von ChatGPT/Birgit direkt geprüft. Ihre für die Konstruktion relevanten Bildinformationen sind verbindlich in folgender Repository-Referenz übertragen:

`tasks/references/NUBSI-R01-PHOTO-REFERENCE.md`

**Diese Referenz ist für Rüdiger der autorisierte Ersatz für den fehlenden direkten Bildzugriff.** Ein erneuter STOPP allein wegen fehlender Bilddateien ist daher nicht zulässig, solange die dort beschriebene Geometrie ohne Änderung der verbindlichen Nutzermaße konstruiert werden kann.

Von ChatGPT früher erzeugte Visualisierungen/Zeichnungen/Datenblätter sind ausdrücklich **KEINE Konstruktionsreferenz**.

Vom Nutzer gemessen:

- Material des Nachbaus: **PETG**
- Steckschaft-Durchmesser: **6,0 mm**
- Steckschaft-Länge: **4,0 mm**, gemessen von der Unterkante bis zur Unterseite/Basis des Kopfes
- größter Außendurchmesser Kopf: **11,0 mm**
- Steckschaft: **gerader, durchgehender Zylinder ohne Stufe**
- oberhalb des Schafts sitzt unmittelbar der auf den Fotos erkennbare Kopf
- Formcharakter des Kopfes gemäß `tasks/references/NUBSI-R01-PHOTO-REFERENCE.md` rekonstruieren
- keine zusätzliche Stufe, Rastung, Nut oder sonstige Funktion erfinden
- Nubsi bleibt ein **separates Bauteil** und wird lediglich zusammen mit der Klammer auf derselben Druckplatte angeordnet.

## TECHNISCH NOTWENDIG – NUBSI

- Die Fotoreferenz beschreibt einen rotationssymmetrischen Nubsi mit geradem Ø-6-mm-Schaft und glatt gewölbtem/kuppelförmigem Kopf bis Ø 11 mm.
- Der in der Fotoreferenz genannte Kopf-Höhenkorridor von ca. **3,5–4,5 mm** ist **fotoabgeleitet**, nicht vom Nutzer gemessen. Innerhalb dieses Korridors ist die R01-Kopfkontur technisch festzulegen.
- Eine dünne umlaufende sichtbare Randkante gehört zur Kopfkontur und darf **nicht als separate Schaftstufe/Kragen** modelliert werden.
- Nicht vorgegebene, rein formbildende Radien/Höhen des Kopfes sind als **FOTOABGELEITET / TECHNISCH FESTGELEGT** zu kennzeichnen.
- Keine erfundene Präzision behaupten.
- Der verbindliche 6,0-mm-Schaft darf nicht eigenmächtig wegen angenommener FDM-Passung verkleinert/vergrößert werden. Falls ein anderes Fertigmaß für die reale Passung technisch erforderlich erscheint: als OFFEN melden, nicht still ändern.
- Keine Hohlräume/Bohrungen ergänzen.
- FDM-taugliche Druckorientierung bestimmen; Support nur wenn erreichbar und entfernbar.

## GEMEINSAME DRUCKPLATTE

- Klammer und Nubsi als **zwei separate STL-Bauteile** erzeugen.
- Zusätzlich einen gemeinsamen Druckplatten-/Anordnungsstand dokumentieren, sodass beide in PETG in einem Druckjob gedruckt werden können.
- Zwischen den Bauteilen ausreichenden Abstand für einen kollisionsfreien FDM-Druck vorsehen; Abstand ist technisch festzulegen und zu dokumentieren.
- Keine geometrische Verbindung zwischen Klammer und Nubsi.

## ZIEL VON R01

R01 ist ein materialarmer Passungs- und Funktionstest. Ein technischer PASS ersetzt keine reale Nutzerfreigabe.

## AUSGABE

Erzeuge und dokumentiere:

1. parametrische/reproduzierbare CAD-Stände für Klammer und Nubsi,
2. **STL Klammer R01**,
3. **STL Nubsi R01**,
4. gemeinsamen Druckplatten-/Anordnungsstand für beide PETG-Bauteile,
5. SOLL/IST-Maßbericht für beide Teile,
6. technische Festlegungen und aus Fotos abgeleitete Werte klar kennzeichnen,
7. FDM-/PETG-Prüfung inklusive Druckorientierungen,
8. technische Mesh-/STL-Validierung beider Einzelteile,
9. Revisionseintrag mit **GEÄNDERT / UNVERÄNDERT / ENTFERNT / OFFEN**,
10. keine finale Nutzerfreigabe behaupten.

## STOPP-/ESKALATIONSREGEL

Technische STOPPs und Detailentscheidungen, die die verbindliche Produktidee und Nutzermaße nicht verändern, sind zunächst durch ChatGPT/Birgit zu prüfen bzw. technisch zu entscheiden und sollen den Nutzer nicht unnötig blockieren.

Die fehlenden Originalbilddateien im Worker-Kontext sind durch `tasks/references/NUBSI-R01-PHOTO-REFERENCE.md` technisch aufgelöst. Dieser Punkt darf nicht erneut als Nutzerentscheidung eskaliert werden.

Nur wenn eine verbindliche Nutzeranforderung geändert werden müsste, eine reale nicht ableitbare Information trotz der übertragenen Fotoreferenz zwingend fehlt oder eine echte Produkt-/Freigabeentscheidung notwendig ist, als **NUTZERENTSCHEIDUNG ERFORDERLICH** markieren.

Keine stillen Nebenänderungen und keine zusätzlichen Features.
