param([string]$OutputDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'

# Identische Konstruktionsparameter zum SCAD-Stand, alle Werte in mm.
$p = [ordered]@{ Width=20.0; Wall=2.0; Clear=22.4; Height=40.0; ToothPitch=1.4; ToothHeight=0.6; ToothCount=18; ToothStart=1.2; ArcSegments=48 }
$outerWidth = $p.Clear + 2*$p.Wall
$outerRadius = $outerWidth/2
$innerRadius = $outerRadius-$p.Wall
$cz = $p.Height-$outerRadius

$poly = [System.Collections.Generic.List[object]]::new()
function Add-P([double]$x,[double]$z) { $script:poly.Add(@($x,$z)) }
Add-P 0 0; Add-P 0 $cz
for($i=1;$i -le $p.ArcSegments;$i++) { $a=[math]::PI-$i*[math]::PI/$p.ArcSegments; Add-P ($outerWidth/2+$outerRadius*[math]::Cos($a)) ($cz+$outerRadius*[math]::Sin($a)) }
Add-P $outerWidth 0; Add-P ($p.Wall+$p.Clear) 0; Add-P ($p.Wall+$p.Clear) $p.ToothStart
for($i=0;$i -lt $p.ToothCount;$i++) { $z0=$p.ToothStart+$i*$p.ToothPitch; Add-P ($p.Wall+$p.Clear-$p.ToothHeight) ($z0+$p.ToothPitch-0.25); Add-P ($p.Wall+$p.Clear) ($z0+$p.ToothPitch) }
Add-P ($p.Wall+$p.Clear) $cz
for($i=1;$i -le $p.ArcSegments;$i++) { $a=$i*[math]::PI/$p.ArcSegments; Add-P ($outerWidth/2+$innerRadius*[math]::Cos($a)) ($cz+$innerRadius*[math]::Sin($a)) }
Add-P $p.Wall 0

function Area2($pts) { $s=0.0; for($i=0;$i -lt $pts.Count;$i++){ $j=($i+1)%$pts.Count; $s += $pts[$i][0]*$pts[$j][1]-$pts[$j][0]*$pts[$i][1] }; $s }
function Cross($a,$b,$c) { ($b[0]-$a[0])*($c[1]-$a[1])-($b[1]-$a[1])*($c[0]-$a[0]) }
function InsideTri($pt,$a,$b,$c,$sign) { (Cross $a $b $pt)*$sign -ge -1e-9 -and (Cross $b $c $pt)*$sign -ge -1e-9 -and (Cross $c $a $pt)*$sign -ge -1e-9 }
$orientation = if((Area2 $poly) -gt 0){1}else{-1}
$idx=[System.Collections.Generic.List[int]]::new(); 0..($poly.Count-1) | ForEach-Object {$idx.Add($_)}
$caps=[System.Collections.Generic.List[object]]::new()
while($idx.Count -gt 3){ $found=$false; for($k=0;$k -lt $idx.Count;$k++){ $ia=$idx[($k-1+$idx.Count)%$idx.Count];$ib=$idx[$k];$ic=$idx[($k+1)%$idx.Count]; if((Cross $poly[$ia] $poly[$ib] $poly[$ic])*$orientation -le 1e-9){continue}; $contains=$false; foreach($q in $idx){if($q-ne$ia-and$q-ne$ib-and$q-ne$ic-and(InsideTri $poly[$q] $poly[$ia] $poly[$ib] $poly[$ic] $orientation)){$contains=$true;break}}; if(!$contains){$caps.Add(@($ia,$ib,$ic));$idx.RemoveAt($k);$found=$true;break} }; if(!$found){throw 'Triangulation fehlgeschlagen'} }
$caps.Add(@($idx[0],$idx[1],$idx[2]))

$facets=[System.Collections.Generic.List[object]]::new()
foreach($t in $caps){ if($orientation -gt 0){$facets.Add(@($t[2],$t[1],$t[0],0));$facets.Add(@($t[0],$t[1],$t[2],1))}else{$facets.Add(@($t[0],$t[1],$t[2],0));$facets.Add(@($t[2],$t[1],$t[0],1))} }
for($i=0;$i -lt $poly.Count;$i++){ $j=($i+1)%$poly.Count; if($orientation -gt 0){$facets.Add(@($i,$j,$j,2));$facets.Add(@($i,$j,$i,3))}else{$facets.Add(@($i,$j,$i,2));$facets.Add(@($i,$j,$j,3))} }
function V($code){$i=$code[0];$side=$code[1]; [pscustomobject]@{X=[double]$poly[$i][0];Y=[double]$(if($side){$p.Width}else{0.0});Z=[double]$poly[$i][1]}}
function TriVerts($f){ if($f[3]-eq 0-or$f[3]-eq 1){@((V @($f[0],$f[3])),(V @($f[1],$f[3])),(V @($f[2],$f[3])))}elseif($f[3]-eq 2){@((V @($f[0],0)),(V @($f[1],0)),(V @($f[1],1)))}else{@((V @($f[0],0)),(V @($f[1],1)),(V @($f[0],1)))}}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$stl=Join-Path $OutputDirectory 'petg-bettklammer-r01.stl'; $inv=[Globalization.CultureInfo]::InvariantCulture
$lines=[System.Collections.Generic.List[string]]::new();$lines.Add('solid petg_bettklammer_r01')
foreach($f in $facets){$vv=TriVerts $f;$lines.Add('  facet normal 0 0 0');$lines.Add('    outer loop');foreach($v in $vv){$lines.Add([string]::Format($inv,'      vertex {0:R} {1:R} {2:R}',$v.X,$v.Y,$v.Z))};$lines.Add('    endloop');$lines.Add('  endfacet')};$lines.Add('endsolid petg_bettklammer_r01'); [IO.File]::WriteAllLines($stl,$lines,[Text.UTF8Encoding]::new($false))

# Topologische Validierung ueber ungerichtete Kanten.
$edges=@{};$mins=@([double]::MaxValue,[double]::MaxValue,[double]::MaxValue);$maxs=@([double]::MinValue,[double]::MinValue,[double]::MinValue)
foreach($f in $facets){$vv=TriVerts $f;foreach($v in $vv){$vals=@($v.X,$v.Y,$v.Z);for($d=0;$d-lt3;$d++){$mins[$d]=[math]::Min($mins[$d],$vals[$d]);$maxs[$d]=[math]::Max($maxs[$d],$vals[$d])}};for($e=0;$e-lt3;$e++){$a=('{0:R},{1:R},{2:R}' -f $vv[$e].X,$vv[$e].Y,$vv[$e].Z);$b=('{0:R},{1:R},{2:R}' -f $vv[($e+1)%3].X,$vv[($e+1)%3].Y,$vv[($e+1)%3].Z);$key=(@($a,$b)|Sort-Object)-join '|';$old=0;if($edges.ContainsKey($key)){$old=$edges[$key]};$edges[$key]=1+$old}}
$bad=@($edges.Values|Where-Object{$_-ne2}).Count
$result=[ordered]@{revision='R01';stl=(Split-Path $stl -Leaf);vertices_2d=$poly.Count;triangles=$facets.Count;bounds_mm=[ordered]@{x=@($mins[0],$maxs[0]);y=@($mins[1],$maxs[1]);z=@($mins[2],$maxs[2])};dimensions_mm=[ordered]@{width=$p.Width;overall_height=$p.Height;outer_depth=$outerWidth;clear_width=$p.Clear;wall=$p.Wall};topology=[ordered]@{undirected_edges=$edges.Count;nonmanifold_or_boundary_edges=$bad;watertight=($bad-eq0)};status=$(if($bad-eq0){'PASS'}else{'FAIL'})}
$result|ConvertTo-Json -Depth 8|Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'technical-validation.json'); if($bad-ne0){throw "Mesh nicht watertight: $bad Kanten"}; $result|ConvertTo-Json -Depth 8
