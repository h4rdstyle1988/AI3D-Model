# Reproduktion

Aus Repository-Wurzel:

```powershell
python outputs/herbst-igel-r01/herbst-igel-r01-parametric.py --repo . --output outputs/herbst-igel-r01
python outputs/herbst-igel-r01/validate_herbst_igel_r01.py --repo . --output outputs/herbst-igel-r01
```

Benötigt Python 3.12+, NumPy und Pillow. Das Build-Skript dekodiert und prüft beide autoritativen Referenzen vor der Konstruktion. Der zweite Lauf validiert STL und GLB nochmals unabhängig aus den geschriebenen Binärdateien. Die sekundäre Multiansicht wird nicht gelesen.
