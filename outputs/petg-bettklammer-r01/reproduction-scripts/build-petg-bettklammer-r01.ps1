param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..')
)

$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture

function V([double]$x,[double]$y,[double]$z) { [pscustomobject]@{X=$x;Y=$y;Z=$z} }
function Add-Tri($list,$a,$b,$c) {
    [void]$list.Add([pscustomobject]@{A=$a;B=$b;C=$c})
}

function Get-EarTriangles($points) {
    $idx=[Collections.Generic.List[int]]::new(); for($i=0;$i -lt $points.Count;$i++){$idx.Add($i)}
    $ears=[Collections.Generic.List[object]]::new(); $guard=0
    while($idx.Count -gt 3 -and $guard -lt 10000) {
        $cut=$false
        for($k=0;$k -lt $idx.Count;$k++) {
            $ia=$idx[($k-1+$idx.Count)%$idx.Count]; $ib=$idx[$k]; $ic=$idx[($k+1)%$idx.Count]
            $a=$points[$ia]; $b=$points[$ib]; $c=$points[$ic]
            $cross=($b[0]-$a[0])*($c[1]-$b[1])-($b[1]-$a[1])*($c[0]-$b[0]); if($cross -le 1e-10){continue}
            $contains=$false
            foreach($ip in $idx) {
                if($ip -eq $ia -or $ip -eq $ib -or $ip -eq $ic){continue}; $p=$points[$ip]
                $c1=($b[0]-$a[0])*($p[1]-$a[1])-($b[1]-$a[1])*($p[0]-$a[0])
                $c2=($c[0]-$b[0])*($p[1]-$b[1])-($c[1]-$b[1])*($p[0]-$b[0])
                $c3=($a[0]-$c[0])*($p[1]-$c[1])-($a[1]-$c[1])*($p[0]-$c[0])
                if($c1 -gt 1e-10 -and $c2 -gt 1e-10 -and $c3 -gt 1e-10){$contains=$true;break}
            }
            if(-not $contains){$ears.Add(@($ia,$ib,$ic));$idx.RemoveAt($k);$cut=$true;break}
        }
        if(-not $cut){throw 'Ear clipping failed: invalid or non-simple profile'}; $guard++
    }
    $ears.Add(@($idx[0],$idx[1],$idx[2])); return $ears
}

function Add-ExtrudedPolygon($tris, $points, [double]$width, [double]$xoff=0, [double]$yoff=0, [double]$zoff=0) {
    $n=$points.Count
    # Polygon is CCW; ear clipping handles the concave U profile and tooth flanks.
    foreach($e in (Get-EarTriangles $points)) {
        $p0=$points[$e[0]]; $p1=$points[$e[1]]; $p2=$points[$e[2]]
        Add-Tri $tris (V ($p0[0]+$xoff) $yoff ($p0[1]+$zoff)) (V ($p1[0]+$xoff) $yoff ($p1[1]+$zoff)) (V ($p2[0]+$xoff) $yoff ($p2[1]+$zoff))
        Add-Tri $tris (V ($p0[0]+$xoff) ($yoff+$width) ($p0[1]+$zoff)) (V ($p2[0]+$xoff) ($yoff+$width) ($p2[1]+$zoff)) (V ($p1[0]+$xoff) ($yoff+$width) ($p1[1]+$zoff))
    }
    for($i=0;$i -lt $n;$i++) {
        $j=($i+1)%$n; $a=$points[$i]; $b=$points[$j]
        $a0=V ($a[0]+$xoff) $yoff ($a[1]+$zoff); $b0=V ($b[0]+$xoff) $yoff ($b[1]+$zoff)
        $a1=V ($a[0]+$xoff) ($yoff+$width) ($a[1]+$zoff); $b1=V ($b[0]+$xoff) ($yoff+$width) ($b[1]+$zoff)
        Add-Tri $tris $a0 $b1 $b0; Add-Tri $tris $a0 $a1 $b1
    }
}

function Add-Lathe($tris,$profile,[int]$segments,[double]$xoff=0,[double]$yoff=0,[double]$zoff=0) {
    for($i=0;$i -lt $segments;$i++) {
        $a=2*[Math]::PI*$i/$segments; $b=2*[Math]::PI*(($i+1)%$segments)/$segments
        for($j=0;$j -lt $profile.Count-1;$j++) {
            $r0=$profile[$j][0]; $z0=$profile[$j][1]; $r1=$profile[$j+1][0]; $z1=$profile[$j+1][1]
            $p00=V ($xoff+$r0*[Math]::Cos($a)) ($yoff+$r0*[Math]::Sin($a)) ($zoff+$z0)
            $p01=V ($xoff+$r0*[Math]::Cos($b)) ($yoff+$r0*[Math]::Sin($b)) ($zoff+$z0)
            $p10=V ($xoff+$r1*[Math]::Cos($a)) ($yoff+$r1*[Math]::Sin($a)) ($zoff+$z1)
            $p11=V ($xoff+$r1*[Math]::Cos($b)) ($yoff+$r1*[Math]::Sin($b)) ($zoff+$z1)
            if([Math]::Abs($r0) -lt 1e-12) { Add-Tri $tris $p00 $p11 $p10 }
            elseif([Math]::Abs($r1) -lt 1e-12) { Add-Tri $tris $p00 $p01 $p10 }
            else { Add-Tri $tris $p00 $p01 $p11; Add-Tri $tris $p00 $p11 $p10 }
        }
    }
}

function Write-Stl($path,$name,$tris) {
    $lines=[Collections.Generic.List[string]]::new(); $lines.Add("solid $name")
    foreach($triangle in $tris) {
        $p0=@($triangle.A)[0]; $p1=@($triangle.B)[0]; $p2=@($triangle.C)[0]
        $u=@(($p1.X-$p0.X),($p1.Y-$p0.Y),($p1.Z-$p0.Z)); $v=@(($p2.X-$p0.X),($p2.Y-$p0.Y),($p2.Z-$p0.Z))
        $nx=$u[1]*$v[2]-$u[2]*$v[1]; $ny=$u[2]*$v[0]-$u[0]*$v[2]; $nz=$u[0]*$v[1]-$u[1]*$v[0]
        $len=[Math]::Sqrt($nx*$nx+$ny*$ny+$nz*$nz); if($len -gt 0){$nx/=$len;$ny/=$len;$nz/=$len}
        $lines.Add('  facet normal '+$nx.ToString('R',$inv)+' '+$ny.ToString('R',$inv)+' '+$nz.ToString('R',$inv)); $lines.Add('    outer loop')
        $lines.Add('      vertex '+$p0.X.ToString('R',$inv)+' '+$p0.Y.ToString('R',$inv)+' '+$p0.Z.ToString('R',$inv)); $lines.Add('      vertex '+$p1.X.ToString('R',$inv)+' '+$p1.Y.ToString('R',$inv)+' '+$p1.Z.ToString('R',$inv)); $lines.Add('      vertex '+$p2.X.ToString('R',$inv)+' '+$p2.Y.ToString('R',$inv)+' '+$p2.Z.ToString('R',$inv))
        $lines.Add('    endloop'); $lines.Add('  endfacet')
    }
    $lines.Add("endsolid $name"); [IO.File]::WriteAllLines($path,$lines,[Text.UTF8Encoding]::new($false))
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

# Klammer cross-section: X across the opening, Z bottom-to-top, extrusion Y=20 mm.
$wall=[double]2.0; $mountingClearance=[double]0.4; $gap=[double](22.0+$mountingClearance); $outerRadius=[double]($gap/2+$wall); $innerRadius=[double]($gap/2)
$centerX=$outerRadius; $centerZ=40-$outerRadius
$poly=[Collections.Generic.List[object]]::new(); [void]$poly.Add(@(0.0,0.0))
for($i=0;$i -le 32;$i++){ $a=[double]([Math]::PI-$i*[Math]::PI/32); [void]$poly.Add(@([double]($centerX+$outerRadius*[Math]::Cos($a)),[double]($centerZ+$outerRadius*[Math]::Sin($a)))) }
$rightOuter=[double](2*$outerRadius); $rightInner=[double]($rightOuter-$wall); [void]$poly.Add(@($rightOuter,0.0)); [void]$poly.Add(@($rightInner,0.0))
# 18 contiguous asymmetric teeth, 1.4 pitch, 0.6 engagement; gentle insertion ramp and steep withdrawal face.
$pitch=[double]1.4; $engagement=[double]0.6; $toothStart=[double]1.0
[void]$poly.Add(@($rightInner,$toothStart))
for($i=0;$i -lt 18;$i++){ $toothZ=[double]($toothStart+$i*$pitch); [void]$poly.Add(@([double]($rightInner-$engagement),[double]($toothZ+1.05))); [void]$poly.Add(@($rightInner,[double]($toothZ+$pitch))) }
[void]$poly.Add(@($rightInner,$centerZ))
for($i=1;$i -le 32;$i++){ $a=[double]($i*[Math]::PI/32); [void]$poly.Add(@([double]($centerX+$innerRadius*[Math]::Cos($a)),[double]($centerZ+$innerRadius*[Math]::Sin($a)))) }
[void]$poly.Add(@($wall,0.0))
# Normalize profile winding to CCW for deterministic cap and wall normals.
$signedArea=0.0; for($i=0;$i -lt $poly.Count;$i++){ $j=($i+1)%$poly.Count; $signedArea += $poly[$i][0]*$poly[$j][1]-$poly[$j][0]*$poly[$i][1] }
if($signedArea -lt 0){$poly.Reverse()}
$clip=[Collections.Generic.List[object]]::new(); Add-ExtrudedPolygon $clip $poly 20.0

# Nubsi: exact shaft 6x4 mm; photo-derived 4.0 mm head. Thin rim is integrated in the smooth head profile.
$headH=[double]4.0; $profile=[Collections.Generic.List[object]]::new(); [void]$profile.Add(@(0.0,0.0)); [void]$profile.Add(@(3.0,0.0)); [void]$profile.Add(@(3.0,4.0)); [void]$profile.Add(@(5.5,4.0))
for($i=1;$i -le 16;$i++){ $theta=[double]($i*[Math]::PI/32); $radius=if($i -eq 16){0.0}else{[double](5.5*[Math]::Cos($theta))}; [void]$profile.Add(@($radius,[double](4.0+$headH*[Math]::Sin($theta)))) }
$nubsi=[Collections.Generic.List[object]]::new(); Add-Lathe $nubsi $profile 96

Write-Stl (Join-Path $OutputDirectory 'petg-bettklammer-r01.stl') 'petg_bettklammer_r01' $clip
Write-Stl (Join-Path $OutputDirectory 'petg-nubsi-r01.stl') 'petg_nubsi_r01' $nubsi

# Plate coordinates are already print-oriented: clip broad side on Y=0, nubsi upright. 10 mm edge gap.
$plate=[Collections.Generic.List[object]]::new(); Add-ExtrudedPolygon $plate $poly 20.0 0 0 0
Add-Lathe $plate $profile 96 ($rightOuter+10+5.5) 5.5 0
Write-Stl (Join-Path $OutputDirectory 'petg-bettklammer-und-nubsi-r01-druckplatte.stl') 'petg_bettklammer_und_nubsi_r01_plate_two_shells' $plate

$parameters=[ordered]@{
 revision='R01'; units='mm'; material='PETG'; clip=[ordered]@{width=20.0; total_height=40.0; wall=2.0; profile_depth=20.0; felt=2.0; mounting_clearance=0.4; clear_opening=22.4; outer_width=26.4; teeth=18; pitch=1.4; engagement=0.6; inner_bend_radius=11.2}; nubsi=[ordered]@{shaft_diameter=6.0; shaft_length=4.0; head_max_diameter=11.0; head_height=4.0; total_height=8.0; head_value_class='FOTOABGELEITET / TECHNISCH FESTGELEGT'}; plate=[ordered]@{minimum_edge_gap=10.0; connected=$false}
}
$parameters | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'design-parameters.json')
Write-Output "Generated $($clip.Count) clip triangles, $($nubsi.Count) nubsi triangles, $($plate.Count) plate triangles."
