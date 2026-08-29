# Rüdiger Live-Status

Der produktive Watcher veröffentlicht seinen aktuellen Laufstatus auf dem separaten Branch `ruediger/live-status` als `RUEDIGER_STATUS.json`.

Dieser Branch ist reine Telemetrie:
- nicht in `master` mergen;
- nicht als Produktfreigabe interpretieren;
- keine Produktdateien dort ablegen.

Die Datei enthält mindestens Watcher-Version, Zeitstempel, Phase, aktuelle Task, Task-Blob, Ergebnisbranch und eine kurze technische Detailmeldung.

Der Watcher aktualisiert den Status bei Phasenwechseln und während längerer Codex-Läufe mit dem Heartbeat.
