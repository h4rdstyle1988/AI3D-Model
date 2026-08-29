# Referenzablage

Projektbezogene Originalreferenzen liegen unter `references/<projekt>/`. Jede Task nennt konkrete Repo-Pfade. Pro Projekt beschreibt `manifest.json` auch fehlende, nicht übertragbare Binärdateien eindeutig.

Pflichtfelder des Manifests: `schema_version` (`1.0`), `project`, `references`. Jeder Eintrag enthält `repo_path`, `available`, `kind` (`photo`, `scan`, `drawing`, `measurement` oder `ai-generated`), `real_reference`, `source` und optional `sha256`/`note`. Originaldateien werden nicht überschrieben. KI-generierte Bilder müssen `kind: ai-generated` und `real_reference: false` tragen.

Validierung: `powershell -NoProfile -File tools/validate-reference-manifest.ps1 -ManifestPath references/<projekt>/manifest.json`.
