# Projektbezogene Referenzen

Reale Referenzen liegen ausschließlich unter `references/<projekt>/`. Jede Task nennt die konkreten Repo-Pfade; die Formulierung „Fotos wurden bereitgestellt“ reicht nicht.

Jeder Projektordner enthält eine `manifest.json` nach `references/manifest.schema.json`. Das Manifest unterscheidet `AVAILABLE`, `NOT_TRANSFERRED` und `MISSING`. Für verfügbare Dateien sind SHA-256, Quelle und Aufnahmedatum (falls bekannt) zu erfassen. Originale werden nicht bearbeitet oder überschrieben; abgeleitete Bilder erhalten eigene Dateien und einen Verweis auf das Original. KI-generierte Bilder müssen als `GENERATED` gekennzeichnet sein und dürfen nie den Typ `REAL_REFERENCE` tragen.

Wenn Binärdateien nicht übertragbar sind, bleibt der geplante Repo-Pfad im Manifest mit `NOT_TRANSFERRED`, Beschreibung, Besitzer und sicherem Übergabeweg dokumentiert. Ein solcher Eintrag ist keine reale Referenz und darf nicht als geometrischer Nachweis verwendet werden.

