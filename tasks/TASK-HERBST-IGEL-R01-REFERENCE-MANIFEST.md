# TASK-HERBST-IGEL-R01 – REFERENZ-MANIFEST

Status: AKTIV – TRANSPORT KORRIGIERT
Datum: 2026-08-30

Die Bildreferenzen werden wegen der GitHub-Textschnittstelle als Base64-Dateien gespeichert. Vor Konstruktion lokal dekodieren.

## DATEIEN

### 1. Autoritative saubere Optikreferenz
Base64:
`tasks/TASK-HERBST-IGEL-R01-REF-CLEAN.jpg.b64`

Dekodiertes Ziel:
`TASK-HERBST-IGEL-R01-REF-CLEAN.jpg`

SHA-256:
`d3e7465d9f2d5164836cf5b4d238e04e37778eac995d35123edd6cee04ad9836`

Bedeutung:
- Autoritativ fuer sichtbare Optik, Proportion, Gesicht, Koerperhaltung, Stacheln/Blaetter und das sichtbare dekorative Ahornblatt.
- Technischer Transport-Fix: aus derselben autoritativen Ausgangsreferenz neu als 320 x 320 JPEG kodiert; keine Produktanforderung geaendert.

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
Die bisherige Datei `tasks/TASK-HERBST-IGEL-R01-REF-MULTIVIEW-SECONDARY.jpg.b64` ist wegen Transportkorruption fuer diesen Lauf NICHT ZU VERWENDEN.
Sie war ohnehin nur sekundaere Orientierung und keine verbindliche Produktanforderung.
Nicht sichtbare Seiten sind organisch aus REF-CLEAN abzuleiten, ohne neue Dekorationen oder ein zweites Ahornblatt zu erfinden.

## DEKODIEREN – POWERSHELL

```powershell
$b64 = Get-Content -Raw "tasks\TASK-HERBST-IGEL-R01-REF-CLEAN.jpg.b64"
[IO.File]::WriteAllBytes(
  "TASK-HERBST-IGEL-R01-REF-CLEAN.jpg",
  [Convert]::FromBase64String($b64)
)

$b64 = Get-Content -Raw "tasks\TASK-HERBST-IGEL-R01-REF-SEAM.jpg.b64"
[IO.File]::WriteAllBytes(
  "TASK-HERBST-IGEL-R01-REF-SEAM.jpg",
  [Convert]::FromBase64String($b64)
)
```

## SHA-256 PRUEFEN – POWERSHELL

```powershell
Get-FileHash .\TASK-HERBST-IGEL-R01-REF-CLEAN.jpg -Algorithm SHA256
Get-FileHash .\TASK-HERBST-IGEL-R01-REF-SEAM.jpg -Algorithm SHA256
```

Vor Nutzung muessen diese beiden Hashes exakt mit diesem Manifest uebereinstimmen.

## REFERENZ-PRIORITAET
1. Aktuelle Nutzerangabe / Task-Spezifikation
2. REF-SEAM fuer Trennlinie
3. REF-CLEAN fuer Optik

Keine nicht autoritative Quelle darf die beiden Referenzen oder die Nutzeranforderungen veraendern.
