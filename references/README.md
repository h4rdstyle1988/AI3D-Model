# Referenzablage

Projektbezogene reale Referenzen liegen unter `references/<projekt>/`. Jede Task nennt die konkreten Repo-Pfade. Originale werden nicht bearbeitet oder durch KI-generierte Bilder ersetzt.

Jeder Projektordner enthaelt eine `reference-manifest.json` nach `references/reference-manifest.schema.json`. Ist eine Binaerdatei im Remote-Workflow nicht verfuegbar, bleibt ihr Eintrag im Manifest erhalten und traegt `availability: "missing"` sowie eine sachliche Beschaffungsnotiz. Ein Manifest ersetzt niemals die reale Referenz.

Zulaessige Verfuegbarkeit: `available`, `missing`. Zulaessige Herkunft: `real`, `generated`. Nur `real` darf als reale Mess-/Fotoreferenz verwendet werden.
