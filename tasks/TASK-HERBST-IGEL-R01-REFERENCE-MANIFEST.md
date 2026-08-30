# TASK-HERBST-IGEL-R01 – REFERENZ-MANIFEST

Status: DRAFT / NOCH NICHT QUEUEN
Datum: 2026-08-30

Die Bildreferenzen werden wegen der GitHub-Textschnittstelle als Base64-Dateien gespeichert. Vor Konstruktion lokal dekodieren.

## DATEIEN

### 1. Autoritative saubere Optikreferenz
Base64:
`tasks/TASK-HERBST-IGEL-R01-REF-CLEAN.jpg.b64`

Dekodiertes Ziel:
`TASK-HERBST-IGEL-R01-REF-CLEAN.jpg`

SHA-256:
`8fc5ea79cee2ee2d4afac14ed2741a922e2159c68ff9cd87c3c7fdb377e2ac4c`

Bedeutung:
- Autoritativ fuer sichtbare Optik, Proportion, Gesicht, Koerperhaltung, Stacheln/Blaetter und das sichtbare dekorative Ahornblatt.

### 2. Autoritative Trennlinien-Referenz
Base64:
`tasks/TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64`

Dekodiertes Ziel:
`TASK-HERBST-IGEL-R01-REF-SEAM.jpg`

SHA-256:
`b46aa70f60d342ab36d24fff1488308a6b33b286ce2890577a42be69425697a4`

Bedeutung:
- Autoritativ fuer die vom Nutzer blau markierte Trennlinie zwischen Desert-Tan-Koerper und Kupfer-Ruecken.

### 3. Sekundaere Multiansicht
Base64:
`tasks/TASK-HERBST-IGEL-R01-REF-MULTIVIEW-SECONDARY.jpg.b64`

Dekodiertes Ziel:
`TASK-HERBST-IGEL-R01-REF-MULTIVIEW-SECONDARY.jpg`

SHA-256:
`176b02bf201599563dd1af57bc07b9b00a1db5eef3e492999090b4954cc02482`

Bedeutung:
- Nur Orientierung fuer grobe Silhouette und nicht sichtbare Seiten.
- KI-generiert und **nicht autoritativ** fuer Details.
- Bei jedem Widerspruch zu REF-CLEAN / REF-SEAM ignorieren.
- Insbesondere kein zweites dekoratives Ahornblatt aus dieser Multiansicht uebernehmen.

## DEKODIEREN – POWERSHELL
Beispiel fuer REF-CLEAN:

```powershell
$b64 = Get-Content -Raw "tasks\TASK-HERBST-IGEL-R01-REF-CLEAN.jpg.b64"
[IO.File]::WriteAllBytes(
  "TASK-HERBST-IGEL-R01-REF-CLEAN.jpg",
  [Convert]::FromBase64String($b64)
)
```

Analog fuer die beiden anderen Dateien.

## SHA-256 PRUEFEN – POWERSHELL

```powershell
Get-FileHash .\TASK-HERBST-IGEL-R01-REF-CLEAN.jpg -Algorithm SHA256
Get-FileHash .\TASK-HERBST-IGEL-R01-REF-SEAM.jpg -Algorithm SHA256
Get-FileHash .\TASK-HERBST-IGEL-R01-REF-MULTIVIEW-SECONDARY.jpg -Algorithm SHA256
```

Vor Nutzung muessen die Hashes exakt mit diesem Manifest uebereinstimmen.

## REFERENZ-PRIORITAET
1. Aktuelle Nutzerangabe / Task-Spezifikation
2. REF-SEAM fuer Trennlinie
3. REF-CLEAN fuer Optik
4. REF-MULTIVIEW-SECONDARY nur zur Lueckenfuellung

Keine Detailanforderung aus der Sekundaeransicht darf eine autoritative Referenz veraendern.
