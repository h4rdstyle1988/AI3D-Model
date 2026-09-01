# MANFRED Supervisor R01

MANFRED ist die lokale Supervisor- und Betriebsüberwachung für die bestehenden Agentenstapel auf GAMECENTER.

Ziele:
- AI3D-Ruediger-Agent und Documents-Ruediger-Agent überwachen
- genau einen Watcher pro Agent sicherstellen
- abgestürzte Watcher über den bestehenden Scheduled Task neu starten
- doppelte Watcher erkennen und nur überzählige Instanzen beenden
- laufende Codex-Worker nicht grundlos beenden
- Usage-Limit/Retry-Zustände als zulässige Wartezustände behandeln
- Logs und lokalen Status schreiben
- Herbst-Igel nach R19 auf HOLD belassen; MANFRED erzeugt niemals Projektaufgaben
- keine beliebigen Remote-Shell-Kommandos ausführen

Lokale Installation:
- Root: D:\Manfred-Supervisor
- Scheduled Task: MANFRED-Supervisor
- Intervall: 60 Sekunden

MANFRED verändert keinen Projektcode und keine CAD-Ergebnisse. Er überwacht ausschließlich den Betrieb und führt nur fest definierte Recovery-Aktionen aus.
