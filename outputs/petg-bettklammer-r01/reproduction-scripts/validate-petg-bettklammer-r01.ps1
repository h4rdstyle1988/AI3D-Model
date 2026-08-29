param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..'))
$ErrorActionPreference='Stop'; $inv=[Globalization.CultureInfo]::InvariantCulture

function Read-StlTriangles($path) {
    $verts=[Collections.Generic.List[object]]::new()
    foreach($line in [IO.File]::ReadLines($path)) {
        if($line -match '^\s*vertex\s+([^ ]+)\s+([^ ]+)\s+([^ ]+)') {
            [void]$verts.Add(@([double]::Parse($Matches[1],$inv),[double]::Parse($Matches[2],$inv),[double]::Parse($Matches[3],$inv)))
        }
    }
    if($verts.Count%3 -ne 0){throw "Invalid triangle stream: $path"}; return ,$verts
}
function Add-Edge($edges,$a,$b) {$ka=('{0:R},{1:R},{2:R}' -f $a[0],$a[1],$a[2]);$kb=('{0:R},{1:R},{2:R}' -f $b[0],$b[1],$b[2]);$key=if($ka -lt $kb){"$ka|$kb"}else{"$kb|$ka"};if($edges.ContainsKey($key)){$edges[$key]++}else{$edges[$key]=1}}
function Analyze-Stl($path) {
    $v=Read-StlTriangles $path; $edges=@{}; $deg=0; $volume6=0.0
    $min=@([double]::PositiveInfinity,[double]::PositiveInfinity,[double]::PositiveInfinity); $max=@([double]::NegativeInfinity,[double]::NegativeInfinity,[double]::NegativeInfinity)
    for($i=0;$i -lt $v.Count;$i+=3) {
        $a=$v[$i];$b=$v[$i+1];$c=$v[$i+2]
        for($d=0;$d -lt 3;$d++){$min[$d]=[Math]::Min($min[$d],[Math]::Min($a[$d],[Math]::Min($b[$d],$c[$d])));$max[$d]=[Math]::Max($max[$d],[Math]::Max($a[$d],[Math]::Max($b[$d],$c[$d])))}
        $ux=$b[0]-$a[0];$uy=$b[1]-$a[1];$uz=$b[2]-$a[2];$vx=$c[0]-$a[0];$vy=$c[1]-$a[1];$vz=$c[2]-$a[2]
        $nx=$uy*$vz-$uz*$vy;$ny=$uz*$vx-$ux*$vz;$nz=$ux*$vy-$uy*$vx
        if(($nx*$nx+$ny*$ny+$nz*$nz) -lt 1e-16){$deg++}
        $volume6 += $a[0]*($b[1]*$c[2]-$b[2]*$c[1])-$a[1]*($b[0]*$c[2]-$b[2]*$c[0])+$a[2]*($b[0]*$c[1]-$b[1]*$c[0])
        Add-Edge $edges $a $b; Add-Edge $edges $b $c; Add-Edge $edges $c $a
    }
    $bad=@($edges.Values|Where-Object{$_ -ne 2}).Count
    [ordered]@{file=[IO.Path]::GetFileName($path);triangles=$v.Count/3;bounds_min=$min;bounds_max=$max;size=@(($max[0]-$min[0]),($max[1]-$min[1]),($max[2]-$min[2]));degenerate_triangles=$deg;non_two_manifold_edges=$bad;signed_volume_mm3=$volume6/6;watertight=($deg-eq 0 -and $bad-eq 0)}
}
$files=@('petg-bettklammer-r01.stl','petg-nubsi-r01.stl','petg-bettklammer-und-nubsi-r01-druckplatte.stl')
$results=@($files|ForEach-Object{Analyze-Stl (Join-Path $OutputDirectory $_)})
$report=[ordered]@{revision='R01';validator='repository PowerShell ASCII-STL topology validator';results=$results;overall_pass=(@($results|Where-Object{-not $_.watertight}).Count-eq 0)}
$report|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'mesh-validation.json')
$report|ConvertTo-Json -Depth 6
