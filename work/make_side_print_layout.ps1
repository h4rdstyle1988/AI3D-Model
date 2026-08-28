param(
    [Parameter(Mandatory = $true)][string]$InputStl,
    [Parameter(Mandatory = $true)][string]$OutputStl,
    [double]$BedPlaneOriginalY = -5.0
)

$inputFull = [IO.Path]::GetFullPath($InputStl)
$outputFull = [IO.Path]::GetFullPath($OutputStl)
if (-not [IO.File]::Exists($inputFull)) {
    throw "Input STL not found: $inputFull"
}

$parent = [IO.Path]::GetDirectoryName($outputFull)
[IO.Directory]::CreateDirectory($parent) | Out-Null

$source = [IO.File]::Open($inputFull, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
$target = [IO.File]::Open($outputFull, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
$reader = [IO.BinaryReader]::new($source)
$writer = [IO.BinaryWriter]::new($target)

try {
    $header = $reader.ReadBytes(80)
    if ($header.Length -ne 80) { throw "Input is not a binary STL" }
    $writer.Write($header)
    $triangleCount = $reader.ReadUInt32()
    $writer.Write($triangleCount)

    function Write-RotatedNormal([IO.BinaryReader]$r, [IO.BinaryWriter]$w) {
        $x = $r.ReadSingle(); $y = $r.ReadSingle(); $z = $r.ReadSingle()
        # +90 degrees about X: (x, y, z) -> (x, -z, y)
        $w.Write([single]$x); $w.Write([single](-$z)); $w.Write([single]$y)
    }

    function Write-RotatedVertex([IO.BinaryReader]$r, [IO.BinaryWriter]$w, [double]$bedY) {
        $x = $r.ReadSingle(); $y = $r.ReadSingle(); $z = $r.ReadSingle()
        # Same rotation, then set the original y=-5.0 rail side exactly on Z=0.
        # The untouched hex corner at y=-5.1 consequently penetrates the virtual
        # bed by only 0.1 mm; this is slicer placement, not a design-mesh edit.
        $w.Write([single]$x)
        $w.Write([single](-$z))
        $w.Write([single]($y - $bedY))
    }

    for ($i = [uint32]0; $i -lt $triangleCount; $i++) {
        Write-RotatedNormal $reader $writer
        Write-RotatedVertex $reader $writer $BedPlaneOriginalY
        Write-RotatedVertex $reader $writer $BedPlaneOriginalY
        Write-RotatedVertex $reader $writer $BedPlaneOriginalY
        $writer.Write($reader.ReadUInt16())
    }
}
finally {
    $writer.Dispose(); $reader.Dispose(); $target.Dispose(); $source.Dispose()
}

Get-Item -LiteralPath $outputFull | Select-Object FullName, Length, LastWriteTime
