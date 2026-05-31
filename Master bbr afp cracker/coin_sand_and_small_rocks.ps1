$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "extracted\Base"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Read-Json($path) {
    return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-Json($path, $obj) {
    $json = $obj | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($path, $json + [Environment]::NewLine, $utf8NoBom)
}

function Get-Prop($obj, [string]$name) {
    if ($null -eq $obj) { return $null }
    $p = $obj.PSObject.Properties[$name]
    if ($null -eq $p) { return $null }
    return $p.Value
}

function Set-Prop($obj, [string]$name, $value) {
    if ($null -eq $obj.PSObject.Properties[$name]) {
        $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value
    } else {
        $obj.PSObject.Properties[$name].Value = $value
    }
}

function Vec3($x, $y, $z) {
    [pscustomobject]@{ X = [double]$x; Y = [double]$y; Z = [double]$z }
}

function Clone-Json($obj) {
    return (($obj | ConvertTo-Json -Depth 100) | ConvertFrom-Json)
}

function Transform-Props($entity) {
    $data = Get-Prop $entity "data"
    $components = Get-Prop $data "Components"
    $transform = Get-Prop $components "VuTransformComponent"
    return (Get-Prop $transform "Properties")
}

function ForEach-Node($node, [scriptblock]$fn) {
    if ($null -eq $node) { return }
    & $fn $node
    if ($node -is [System.Array]) {
        foreach ($item in $node) { ForEach-Node $item $fn }
    } elseif ($node -is [pscustomobject]) {
        foreach ($p in $node.PSObject.Properties) { ForEach-Node $p.Value $fn }
    }
}

function Touch-JsonFile($path, [scriptblock]$edit) {
    $doc = Read-Json $path
    & $edit $doc
    Write-Json $path $doc
    Write-Host "edited $([System.IO.Path]::GetFileName($path))"
}

function Is-RockyEntity($entity) {
    $name = [string](Get-Prop $entity "name")
    $type = [string](Get-Prop $entity "type")
    return ($name -match "Rock|Stone|Boulder|Stalactite" -or $type -match "Rock|Stone|Boulder|Stalactite")
}

function Shrink-RockyEntity($entity) {
    if (-not (Is-RockyEntity $entity)) { return }
    $props = Transform-Props $entity
    if ($props) {
        Set-Prop $props "Scale" (Vec3 0.22 0.22 0.22)
        $pos = Get-Prop $props "Position"
        if ($pos) { $pos.Z = [double]$pos.Z - 0.4 }
    }
}

function Expand-Coin-Array($arr) {
    if ($arr -isnot [System.Array]) { return $arr }
    $coinBases = @()
    foreach ($entity in $arr) {
        if ($entity -isnot [pscustomobject]) { continue }
        if (([string](Get-Prop $entity "type")) -ne "#Powerup/Powerup_Coin") { continue }
        $name = [string](Get-Prop $entity "name")
        if ($name -match "_SAND|_RAIN") { continue }
        $coinBases += $entity
    }

    if ($coinBases.Count -eq 0) { return $arr }

    $new = @()
    foreach ($entity in $arr) { $new += $entity }

    $baseLimit = [Math]::Min($coinBases.Count, 24)
    for ($b = 0; $b -lt $baseLimit; $b++) {
        $baseCoin = $coinBases[$b]
        $baseProps = Transform-Props $baseCoin
        $basePos = Get-Prop $baseProps "Position"
        if (-not $basePos) { continue }

        $idx = 0
        foreach ($lane in @(-16, -10, -5, 0, 5, 10, 16)) {
            foreach ($along in @(-14, -7, 0, 7, 14)) {
                if ($lane -eq 0 -and $along -eq 0) { continue }
                $clone = Clone-Json $baseCoin
                Set-Prop $clone "name" ("{0}_SAND{1:D2}" -f ([string](Get-Prop $baseCoin "name")), $idx)
                $props = Transform-Props $clone
                $pos = Get-Prop $props "Position"
                $pos.X = [double]$basePos.X + $lane
                $pos.Y = [double]$basePos.Y + $along
                $pos.Z = [double]$basePos.Z + 0.45
                Set-Prop $props "Scale" (Vec3 1.7 1.7 1.7)
                $new += $clone
                $idx++
            }
        }
    }

    return @($new)
}

$templatePaths = @()
$templatePaths += Get-ChildItem -LiteralPath (Join-Path $root "VuTemplateAsset\Dynamic") -Filter "*.json" | Where-Object { $_.Name -match "Boulder|Rock|Stone" }
$templatePaths += Get-ChildItem -LiteralPath (Join-Path $root "VuTemplateAsset\Static") -Filter "*.json" | Where-Object { $_.Name -match "Rock|Stone|Boulder" }
$templatePaths += Get-ChildItem -LiteralPath (Join-Path $root "VuTemplateAsset\Breakable") -Filter "*.json" | Where-Object { $_.Name -match "Stalactite|Rock|Stone|Boulder" }

foreach ($file in $templatePaths) {
    Touch-JsonFile $file.FullName {
        param($doc)
        ForEach-Node $doc {
            param($node)
            if ($node -isnot [pscustomobject]) { return }
            $components = Get-Prop $node "Components"
            if ($components) {
                foreach ($componentProp in $components.PSObject.Properties) {
                    $props = Get-Prop $componentProp.Value "Properties"
                    if (-not $props) { continue }
                    if (Get-Prop $props "Draw Distance") { Set-Prop $props "Draw Distance" 450 }
                    if (Get-Prop $props "LOD 0 Draw Distance") { Set-Prop $props "LOD 0 Draw Distance" 120 }
                    if (Get-Prop $props "Collision Radius") { Set-Prop $props "Collision Radius" 0.18 }
                    if (Get-Prop $props "Collision Size") { Set-Prop $props "Collision Size" (Vec3 0.35 0.35 0.35) }
                }
            }
        }
    }
}

$setupsDir = Join-Path $root "VuProjectAsset\Setups"
Get-ChildItem -LiteralPath $setupsDir -Filter "*.json" | ForEach-Object {
    $path = $_.FullName
    Touch-JsonFile $path {
        param($doc)
        ForEach-Node $doc {
            param($node)
            if ($node -isnot [pscustomobject]) { return }
            Shrink-RockyEntity $node
            foreach ($p in @($node.PSObject.Properties)) {
                if ($p.Name -eq "ChildEntities" -and $p.Value -is [System.Array]) {
                    $node.PSObject.Properties[$p.Name].Value = Expand-Coin-Array $p.Value
                }
            }
        }
    }
}

Write-Host "Small rocks + coin sand applied."
