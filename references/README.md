# Referenzschema

Verbindlicher Ablageort ist `references/<projekt>/`. Jede Task nennt die konkret verwendeten Repo-Pfade.

Jeder Projektordner enthält `manifest.json` nach `references/reference-manifest.schema.json`. `kind` unterscheidet `original` (reale Nutzerreferenz) und `ai_generated`. KI-generierte Bilder dürfen nie als reale Referenz ausgewiesen werden. Ist eine Binärdatei nicht übertragen, bleibt `available: false`; Quelle, vorgesehener Dateiname und Status werden trotzdem erfasst.

Originaldateien werden nicht still ersetzt oder bearbeitet. Eine abgeleitete Datei erhält einen eigenen Manifest-Eintrag.
