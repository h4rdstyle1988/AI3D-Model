param([string]$OutputDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$p = [ordered]@{ Width=20.0; Wall=2.0; Clear=22.4; Height=40.0; ToothPitch=1.4; ToothHeight=0.6; ToothCount=18; ToothStart=1.2; ArcSegments=48 }
$outer = $p.Clear + 2*$p.Wall; $ro=$outer/2; $ri=$ro-$p.Wall; $cz=$p.Height-$ro
$poly=[Collections.Generic.List[object]]::new()
function Add-P([double]$x,[double]$z){$script:poly.Add(@($x,$z))}
Add-P 0 0; Add-P 0 $cz
for($i=1;$i-le$p.ArcSegments;$i++){$a=[math]::PI-$i*[math]::PI/$p.ArcSegments;Add-P ($outer/2+$ro*[math]::Cos($a)) ($cz+$ro*[math]::Sin($a))}
Add-P $outer 0; Add-P ($p.Wall+$p.Clear) 0; Add-P ($p.Wall+$p.Clear) $p.ToothStart
for($i=0;$i-lt$p.ToothCount;$i++){$z=$p.ToothStart+$i*$p.ToothPitch;Add-P ($p.Wall+$p.Clear-$p.ToothHeight) ($z+$p.ToothPitch-0.25);Add-P ($p.Wall+$p.Clear) ($z+$p.ToothPitch)}
Add-P ($p.Wall+$p.Clear) $cz
for($i=1;$i-le$p.ArcSegments;$i++){$a=$i*[math]::PI/$p.ArcSegments;Add-P ($outer/2+$ri*[math]::Cos($a)) ($cz+$ri*[math]::Sin($a))}
Add-P $p.Wall 0
function Area2($q){$s=0.0;for($i=0;$i-lt$q.Count;$i++){$j=($i+1)%$q.Count;$s+=$q[$i][0]*$q[$j][1]-$q[$j][0]*$q[$i][1]};$s}
function Cross($a,$b,$c){($b[0]-$a[0])*($c[1]-$a[1])-($b[1]-$a[1])*($c[0]-$a[0])}
function InTri($q,$a,$b,$c,$sgn){(Cross $a $b $q)*$sgn-ge-1e-9-and(Cross $b $c $q)*$sgn-ge-1e-9-and(Cross $c $a $q)*$sgn-ge-1e-9}
$sgn=if((Area2 $poly)-gt0){1}else{-1};$idx=[Collections.Generic.List[int]]::new();0..($poly.Count-1)|%{$idx.Add($_)};$caps=[Collections.Generic.List[object]]::new()
while($idx.Count-gt3){$found=$false;for($k=0;$k-lt$idx.Count;$k++){$ia=$idx[($k-1+$idx.Count)%$idx.Count];$ib=$idx[$k];$ic=$idx[($k+1)%$idx.Count];if((Cross $poly[$ia] $poly[$ib] $poly[$ic])*$sgn-le1e-9){continue};$inside=$false;foreach($q in $idx){if($q-ne$ia-and$q-ne$ib-and$q-ne$ic-and(InTri $poly[$q] $poly[$ia] $poly[$ib] $poly[$ic] $sgn)){$inside=$true;break}};if(!$inside){$caps.Add(@($ia,$ib,$ic));$idx.RemoveAt($k);$found=$true;break}};if(!$found){throw 'Triangulation fehlgeschlagen'}}
$caps.Add(@($idx[0],$idx[1],$idx[2]));$facets=[Collections.Generic.List[object]]::new()
foreach($t in $caps){if($sgn-gt0){$facets.Add(@($t[2],$t[1],$t[0],0));$facets.Add(@($t[0],$t[1],$t[2],1))}else{$facets.Add(@($t[0],$t[1],$t[2],0));$facets.Add(@($t[2],$t[1],$t[0],1))}}
for($i=0;$i-lt$poly.Count;$i++){$j=($i+1)%$poly.Count;if($sgn-gt0){$facets.Add(@($i,$j,$j,2));$facets.Add(@($i,$j,$i,3))}else{$facets.Add(@($i,$j,$i,2));$facets.Add(@($i,$j,$j,3))}}
function V($i,$side){[pscustomobject]@{X=[double]$poly[$i][0];Y=[double]$(if($side){$p.Width}else{0});Z=[double]$poly[$i][1]}}
function TV($f){if($f[3]-lt2){@((V $f[0] $f[3]),(V $f[1] $f[3]),(V $f[2] $f[3]))}elseif($f[3]-eq2){@((V $f[0] 0),(V $f[1] 0),(V $f[1] 1))}else{@((V $f[0] 0),(V $f[1] 1),(V $f[0] 1))}}
New-Item -ItemType Directory -Force $OutputDirectory|Out-Null;$stl=Join-Path $OutputDirectory 'petg-bettklammer-r01.stl';$ci=[Globalization.CultureInfo]::InvariantCulture;$lines=[Collections.Generic.List[string]]::new();$lines.Add('solid petg_bettklammer_r01')
foreach($f in $facets){$vv=TV $f;$lines.Add('  facet normal 0 0 0');$lines.Add('    outer loop');foreach($v in $vv){$lines.Add([string]::Format($ci,'      vertex {0:R} {1:R} {2:R}',$v.X,$v.Y,$v.Z))};$lines.Add('    endloop');$lines.Add('  endfacet')};$lines.Add('endsolid petg_bettklammer_r01');[IO.File]::WriteAllLines($stl,$lines,[Text.UTF8Encoding]::new($false))
$edges=@{};$mins=@([double]::MaxValue,[double]::MaxValue,[double]::MaxValue);$maxs=@([double]::MinValue,[double]::MinValue,[double]::MinValue)
foreach($f in $facets){$vv=TV $f;foreach($v in $vv){$a=@($v.X,$v.Y,$v.Z);for($d=0;$d-lt3;$d++){$mins[$d]=[math]::Min($mins[$d],$a[$d]);$maxs[$d]=[math]::Max($maxs[$d],$a[$d])}};for($e=0;$e-lt3;$e++){$a=('{0:R},{1:R},{2:R}'-f$vv[$e].X,$vv[$e].Y,$vv[$e].Z);$b=('{0:R},{1:R},{2:R}'-f$vv[($e+1)%3].X,$vv[($e+1)%3].Y,$vv[($e+1)%3].Z);$key=(@($a,$b)|Sort-Object)-join'|';$edges[$key]=1+$(if($edges.ContainsKey($key)){$edges[$key]}else{0})}}
$bad=@($edges.Values|?{$_-ne2}).Count;$result=[ordered]@{revision='R01';part='Klammer';stl=(Split-Path $stl -Leaf);triangles=$facets.Count;bounds_mm=[ordered]@{x=@($mins[0],$maxs[0]);y=@($mins[1],$maxs[1]);z=@($mins[2],$maxs[2])};dimensions_mm=[ordered]@{width=$p.Width;overall_height=$p.Height;outer_depth=$outer;clear_depth=$p.Clear;wall=$p.Wall};topology=[ordered]@{undirected_edges=$edges.Count;nonmanifold_or_boundary_edges=$bad;watertight=($bad-eq0)};status=$(if($bad-eq0){'PASS'}else{'FAIL'})}
$result|ConvertTo-Json -Depth 8|Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'technical-validation-klammer.json');if($bad-ne0){throw "Mesh nicht geschlossen: $bad Kanten"};$result|ConvertTo-Json -Depth 8
