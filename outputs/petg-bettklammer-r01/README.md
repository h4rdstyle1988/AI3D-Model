# PETG-Bettklammer + Nubsi – R01

Status: **KONSTRUKTIONSAUFTRAG / TESTREVISION – TECHNISCH ERZEUGT**  
Keine finale Nutzerfreigabe.

## Dateien

- `petg-bettklammer-r01.stl` – Klammer, einzelnes geschlossenes Mesh
- `petg-nubsi-r01.stl` – Nubsi, einzelnes geschlossenes Mesh
- `petg-bettklammer-und-nubsi-r01-druckplatte.stl` – gemeinsamer Anordnungsstand mit zwei geometrisch getrennten geschlossenen Körpern
- `design-parameters.json` – maschinenlesbarer Parameterstand
- `mesh-validation.json` – maschinenlesbare STL-/Topologieprüfung
- `SOLL-IST-REPORT.md` – Maß- und Anforderungsprüfung
- `FDM-PETG-REPORT.md` – Druckorientierung und Fertigungsprüfung
- `REVISION-R01.md` – Revisionsangaben und offene Punkte
- `reproduction-scripts/` – reproduzierbare CAD-/STL-Erzeugung und Validierung

## Reproduktion

Aus dem Repository-Stamm in Windows PowerShell:

```powershell
& 'outputs/petg-bettklammer-r01/reproduction-scripts/build-petg-bettklammer-r01.ps1'
& 'outputs/petg-bettklammer-r01/reproduction-scripts/validate-petg-bettklammer-r01.ps1'
```

Der Generator ist der parametrische CAD-Stand dieser Revision. Die Parameter sind benannt im Skript und zusätzlich in `design-parameters.json` dokumentiert. Es werden keine externen CAD-Bibliotheken benötigt.

## Ergebnisstatus

Die lokale geometrische und topologische Prüfung ist **PASS**. Ein realer Druck-, Passungs- und Funktionstest bleibt erforderlich und ist ausdrücklich keine bereits erteilte Nutzerfreigabe.
