# Hannes Live-Status

Der produktive Workflow-Agent Hannes veröffentlicht seinen aktuellen Laufstatus auf dem aus Kompatibilitätsgründen unverändert benannten Branch `ruediger/live-status` als `RUEDIGER_STATUS.json`.

Dieser Branch ist reine Telemetrie:
- nicht in `master` mergen;
- nicht als Produktfreigabe interpretieren;
- keine Produktdateien dort ablegen.

Die Datei enthält mindestens `agent_name: "Hannes"`, Watcher-Version, Zeitstempel, Phase, aktuelle Task, Task-Blob, Ergebnisbranch und eine kurze technische Detailmeldung. `STOPP` kennzeichnet einen technischen Hardlimit-Stopp, bei dem das lokale Ergebnis erhalten bleibt und kein Push gestartet wird.

Der Watcher aktualisiert den Status bei Phasenwechseln und während längerer Codex-Läufe mit dem Heartbeat.
