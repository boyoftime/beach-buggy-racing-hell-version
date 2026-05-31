$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "extracted\Base\VuProjectAsset\Setups"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:removed = 0

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

function Is-ExtraCoin($entity) {
    if ($entity -isnot [pscustomobject]) { return $false }
    if ([string](Get-Prop $entity "type") -ne "#Powerup/Powerup_Coin") { return $false }
    $name = [string](Get-Prop $entity "name")
    return ($name -match "_SAND|_RAIN|_LIGHT")
}

function Prune-Node($node) {
    if ($null -eq $node) { return }

    if ($node -is [System.Array]) {
        foreach ($item in $node) { Prune-Node $item }
        return
    }

    if ($node -isnot [pscustomobject]) { return }

    foreach ($p in @($node.PSObject.Properties)) {
        if ($p.Name -eq "ChildEntities" -and $p.Value -is [System.Array]) {
            $kept = @()
            foreach ($entity in $p.Value) {
                if (Is-ExtraCoin $entity) {
                    $script:removed++
                } else {
                    $kept += $entity
                }
            }
            $node.PSObject.Properties[$p.Name].Value = @($kept)
        }
    }

    foreach ($p in @($node.PSObject.Properties)) {
        Prune-Node $p.Value
    }
}

Get-ChildItem -LiteralPath $root -Filter "*.json" | ForEach-Object {
    $before = $script:removed
    $doc = Read-Json $_.FullName
    Prune-Node $doc
    if ($script:removed -gt $before) {
        Write-Json $_.FullName $doc
        Write-Host ("reduced {0}: removed {1} extra coins" -f $_.Name, ($script:removed - $before))
    }
}

Write-Host "Total extra road coins removed: $script:removed"
