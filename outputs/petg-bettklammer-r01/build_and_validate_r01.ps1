param([string]$OutputDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
[Globalization.CultureInfo]::CurrentCulture = [Globalization.CultureInfo]::InvariantCulture
[Globalization.CultureInfo]::CurrentUICulture = [Globalization.CultureInfo]::InvariantCulture

# Dieselben R01-Parameter wie in der SCAD-Quelle.
$width = 20.0; $height = 40.0; $wall = 2.0
$gap = 22.4; $outerDepth = 26.4
$ri = 3.0; $ro = 5.0; $segments = 16
$engagement = 1.0; $rootRadius = 0.35

function Add-Arc([System.Collections.Generic.List[object]]$p, [double]$cx, [double]$cz,
                 [double]$r, [double]$a0, [double]$a1, [int]$n, [bool]$skipFirst=$false) {
    for ($i=([int]$skipFirst); $i -le $n; $i++) {
        $a = ($a0 + ($a1-$a0)*$i/$n) * [Math]::PI / 180.0
        [double]$px = $cx + ($r * [Math]::Cos($a))
        [double]$pz = $cz + ($r * [Math]::Sin($a))
        $p.Add(@($px, $pz))
    }
}

# Einfache, nicht selbstschneidende CCW-Aussenkontur des offenen U-Profils.
$p = [System.Collections.Generic.List[object]]::new()
$p.Add(@(0.0,0.0)); $p.Add(@(0.0,35.0))
Add-Arc $p 5.0 35.0 $ro 180 90 $segments $true
$p.Add(@(21.4,40.0)); Add-Arc $p 21.4 35.0 $ro 90 0 $segments $true
$p.Add(@(26.4,0.0)); $p.Add(@(24.4,0.0))

# Rechte innere Wand, abwaerts: kurze Halteflanke, lange Aufschieberampe.
foreach ($zu in @(17.0,22.0,27.0,32.0)) {
    # Aufwaerts entlang der Innenwand: unterer verrundeter Rampenfuss,
    # Spitze, oberer verrundeter Haltekantenfuss.
    $p.Add(@(24.4,($zu-2.0-$rootRadius)))
    $p.Add(@(24.35,($zu-2.0)))
    $p.Add(@(23.4,($zu-0.35)))
    $p.Add(@(24.35,$zu))
    $p.Add(@(24.4,($zu+$rootRadius)))
}
$p.Add(@(24.4,35.0)); Add-Arc $p 21.4 35.0 $ri 0 90 $segments $true
$p.Add(@(5.0,38.0)); Add-Arc $p 5.0 35.0 $ri 90 180 $segments $true
$p.Add(@(2.0,0.0))

# Die konstruktive Aufzaehlung oben ist im Uhrzeigersinn; Ear-Clipping und
# Normalenberechnung arbeiten nachfolgend mit CCW-Orientierung.
$p.Reverse()

function Cross($a,$b,$c) { ($b[0]-$a[0])*($c[1]-$a[1])-($b[1]-$a[1])*($c[0]-$a[0]) }
function In-Triangle($q,$a,$b,$c) {
    (Cross $a $b $q) -ge -1e-9 -and (Cross $b $c $q) -ge -1e-9 -and (Cross $c $a $q) -ge -1e-9
}

# Ear clipping fuer die Deckflaechen.
$idx = [System.Collections.Generic.List[int]]::new()
for($i=0;$i-lt$p.Count;$i++){$idx.Add($i)}
$caps = [System.Collections.Generic.List[object]]::new()
while($idx.Count -gt 3) {
    $cut=$false
    for($j=0;$j-lt$idx.Count;$j++) {
        $ia=$idx[($j-1+$idx.Count)%$idx.Count]; $ib=$idx[$j]; $ic=$idx[($j+1)%$idx.Count]
        if((Cross $p[$ia] $p[$ib] $p[$ic]) -le 1e-9){continue}
        $inside=$false
        foreach($ik in $idx){if($ik-ne$ia-and$ik-ne$ib-and$ik-ne$ic-and(In-Triangle $p[$ik] $p[$ia] $p[$ib] $p[$ic])){$inside=$true;break}}
        if(-not$inside){$caps.Add(@($ia,$ib,$ic));$idx.RemoveAt($j);$cut=$true;break}
    }
    if(-not$cut){throw 'Triangulation fehlgeschlagen: Kontur pruefen.'}
}
$caps.Add(@($idx[0],$idx[1],$idx[2]))

function Facet($sw,$a,$b,$c) {
    $ux=$b[0]-$a[0];$uy=$b[1]-$a[1];$uz=$b[2]-$a[2]
    $vx=$c[0]-$a[0];$vy=$c[1]-$a[1];$vz=$c[2]-$a[2]
    $nx=$uy*$vz-$uz*$vy;$ny=$uz*$vx-$ux*$vz;$nz=$ux*$vy-$uy*$vx
    $len=[Math]::Sqrt($nx*$nx+$ny*$ny+$nz*$nz); if($len-gt 0){$nx/=$len;$ny/=$len;$nz/=$len}
    $sw.WriteLine(('  facet normal {0:R} {1:R} {2:R}' -f $nx,$ny,$nz));$sw.WriteLine('    outer loop')
    $sw.WriteLine(('      vertex {0:R} {1:R} {2:R}' -f $a[0],$a[1],$a[2]))
    $sw.WriteLine(('      vertex {0:R} {1:R} {2:R}' -f $b[0],$b[1],$b[2]))
    $sw.WriteLine(('      vertex {0:R} {1:R} {2:R}' -f $c[0],$c[1],$c[2]))
    $sw.WriteLine('    endloop');$sw.WriteLine('  endfacet')
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$stl=Join-Path $OutputDirectory 'petg-bettklammer-r01.stl'
$sw=[IO.StreamWriter]::new($stl,$false,[Text.Encoding]::ASCII);$sw.WriteLine('solid petg_bettklammer_r01')
foreach($t in $caps){
    $a=$p[$t[0]];$b=$p[$t[1]];$c=$p[$t[2]]
    Facet $sw @($a[0],0.0,$a[1]) @($c[0],0.0,$c[1]) @($b[0],0.0,$b[1])
    Facet $sw @($a[0],$width,$a[1]) @($b[0],$width,$b[1]) @($c[0],$width,$c[1])
}
for($i=0;$i-lt$p.Count;$i++){
    $j=($i+1)%$p.Count;$a=$p[$i];$b=$p[$j]
    Facet $sw @($a[0],0.0,$a[1]) @($b[0],0.0,$b[1]) @($b[0],$width,$b[1])
    Facet $sw @($a[0],0.0,$a[1]) @($b[0],$width,$b[1]) @($a[0],$width,$a[1])
}
$sw.WriteLine('endsolid petg_bettklammer_r01');$sw.Dispose()

# STL-Pruefung: Dreiecke, Grenzen und jede ungerichtete Kante genau zweimal.
$verts=[System.Collections.Generic.List[object]]::new();$edges=@{}
foreach($line in [IO.File]::ReadLines($stl)){
    if($line -match '^\s*vertex\s+([-0-9.Ee+]+)\s+([-0-9.Ee+]+)\s+([-0-9.Ee+]+)'){
        $verts.Add(@([double]$matches[1],[double]$matches[2],[double]$matches[3]))
    }
}
for($i=0; $i -lt $verts.Count; $i+=3){for($e=0; $e -lt 3; $e++){
    $a=($verts[($i+$e)]|ForEach-Object{$_.ToString('F6')})-join',';$b=($verts[($i+(($e+1) % 3))]|ForEach-Object{$_.ToString('F6')})-join','
    $key=(@($a,$b)|Sort-Object)-join'|';if($edges.ContainsKey($key)){$edges[$key]++}else{$edges[$key]=1}
}}
$bad=@($edges.Values|Where-Object{$_ -ne 2}).Count
$xs=$verts|ForEach-Object{$_[0]};$ys=$verts|ForEach-Object{$_[1]};$zs=$verts|ForEach-Object{$_[2]}
$result=[ordered]@{
 revision='R01'; stl=(Split-Path $stl -Leaf); triangle_count=[int]($verts.Count/3)
 watertight_edge_test=($bad-eq0); nonmanifold_or_open_edges=$bad
 bounds_mm=[ordered]@{x=@(($xs|Measure-Object -Minimum).Minimum,($xs|Measure-Object -Maximum).Maximum);y=@(($ys|Measure-Object -Minimum).Minimum,($ys|Measure-Object -Maximum).Maximum);z=@(($zs|Measure-Object -Minimum).Minimum,($zs|Measure-Object -Maximum).Maximum)}
 required=[ordered]@{width_mm=$width;height_mm=$height;wall_mm=$wall;clear_gap_mm=$gap;assembly_clearance_mm=0.4;tooth_count=4;tooth_engagement_mm=$engagement}
 status=$(if($bad-eq0){'PASS_TECHNICAL'}else{'FAIL'})
 note='Technischer Mesh-/Mass-Pass ist keine finale Nutzerfreigabe.'
}
$result|ConvertTo-Json -Depth 5|Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'technical-validation.json')
if($bad-ne0){throw "STL nicht watertight: $bad problematische Kanten"}
Write-Host "PASS: $stl; $($result.triangle_count) Dreiecke; Bounds 26.4 x 20.0 x 40.0 mm; watertight."
