$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "extracted\Base\VuProjectAsset\Setups"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:converted = 0

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

function Ensure-ObjectProp($obj, [string]$name) {
    $value = Get-Prop $obj $name
    if ($null -eq $value -or $value -isnot [pscustomobject]) {
        $value = [pscustomobject]@{}
        Set-Prop $obj $name $value
    }
    return $value
}

function Convert-Node($node) {
    if ($null -eq $node) { return }

    if ($node -is [System.Array]) {
        foreach ($item in $node) { Convert-Node $item }
        return
    }

    if ($node -isnot [pscustomobject]) { return }

    if ([string](Get-Prop $node "type") -eq "#Powerup/Powerup_Coin") {
        Set-Prop $node "type" "#Powerup/Powerup"
        $name = [string](Get-Prop $node "name")
        if ($name -match "Coin") {
            Set-Prop $node "name" ($name -replace "Coin", "Boost")
        }
        $data = Ensure-ObjectProp $node "data"
        $properties = Ensure-ObjectProp $data "Properties"
        Set-Prop $properties "Boost" 10
        Set-Prop $properties "CoinMagnet" 0
        Set-Prop $properties "MegaCoin" 0
        Set-Prop $properties "Toughness" 0
        $script:converted++
    }

    foreach ($p in @($node.PSObject.Properties)) {
        Convert-Node $p.Value
    }
}

Get-ChildItem -LiteralPath $root -Filter "*.json" | ForEach-Object {
    $before = $script:converted
    $doc = Read-Json $_.FullName
    Convert-Node $doc
    if ($script:converted -gt $before) {
        Write-Json $_.FullName $doc
        Write-Host ("converted {0}: {1} coins to boost" -f $_.Name, ($script:converted - $before))
    }
}

Write-Host "Total coin pickups converted to boost: $script:converted"
