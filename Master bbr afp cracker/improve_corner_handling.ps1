$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "extracted\Base\VuDBAsset"
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

$carDbPath = Join-Path $root "CarDB.bin.json"
$carDb = Read-Json $carDbPath
foreach ($carProp in $carDb.VuDBAsset.PSObject.Properties) {
    $car = $carProp.Value
    if ($carProp.Name -eq "Default") {
        Set-Prop $car "Inertia Factor" 1.15
        Set-Prop $car "Max Steering Angle" 52.0
        $chassis = Get-Prop $car "Chassis"
        if ($chassis) {
            Set-Prop $chassis "Aero Lift" -38
            Set-Prop $chassis "Air Steering Speed" 135
            Set-Prop $chassis "Fast Steering Speed" 155
            Set-Prop $chassis "Slow Steering Speed" 95
            Set-Prop $chassis "Fast Steering Boat Speed" 135
            Set-Prop $chassis "Slow Steering Boat Speed" 58
            Set-Prop $chassis "Lat Skin Friction Coeff" 0.09
            Set-Prop $chassis "Long Skin Friction Coeff" 0.025
            Set-Prop $chassis "Power Slide Coeff" 0.24
            $stability = Get-Prop $chassis "Stability"
            if ($stability) { $stability.X = 11; $stability.Y = 13; $stability.Z = 11 }
        }
    } else {
        Set-Prop $car "Mass" 840
        Set-Prop $car "Max Braking Force" 22000
        $chassis = Get-Prop $car "Chassis"
        if ($chassis) { Set-Prop $chassis "Drag Coeff" 0.13 }
        $suspension = Get-Prop $car "Suspension"
        if ($suspension) {
            Set-Prop $suspension "Damping Coeff" 6200.0
            Set-Prop $suspension "Lower Spring Coeff" 26000.0
            Set-Prop $suspension "Upper Spring Coeff" 52000.0
            Set-Prop $suspension "Power Slide Coeff" 0.22
            Set-Prop $suspension "Rollover Resistance" 2.2
            Set-Prop $suspension "Wheelie Resistance" 1.8
        }
    }
}
Write-Json $carDbPath $carDb
Write-Host "improved steering and corner stability"

$upgradePath = Join-Path $root "CarUpgradeDB.bin.json"
$upgradeDb = Read-Json $upgradePath
foreach ($entryProp in $upgradeDb.VuDBAsset.PSObject.Properties) {
    $entry = $entryProp.Value
    $engine = Get-Prop $entry "Engine"
    if ($engine) {
        Set-Prop $engine "Max Forward Speed" 330
        Set-Prop $engine "Max Power" 1150
        $curve = Get-Prop $engine "Torque Curve"
        if ($curve) {
            foreach ($point in $curve) {
                if ($point.Count -ge 2) { $point[1] = 360 }
            }
        }
    }
    $stats = Get-Prop $entry "Stats"
    if ($stats) {
        Set-Prop $stats "Accel" 16
        Set-Prop $stats "Speed" 15
        Set-Prop $stats "Tough" 12
    }
}
Write-Json $upgradePath $upgradeDb
Write-Host "added corner-exit torque"

$surfacePath = Join-Path $root "SurfaceDB.bin.json"
$surfaceDb = Read-Json $surfacePath
foreach ($surfaceProp in $surfaceDb.VuDBAsset.PSObject.Properties) {
    $surface = $surfaceProp.Value
    if (Get-Prop $surface "Friction") {
        switch ($surfaceProp.Name) {
            "Ice" { Set-Prop $surface "Friction" 0.45 }
            "Sand" { Set-Prop $surface "Friction" 0.62 }
            "Snow" { Set-Prop $surface "Friction" 0.62 }
            "<none>" { Set-Prop $surface "Friction" 0.0 }
            default { Set-Prop $surface "Friction" 0.88 }
        }
    }
}
Write-Json $surfacePath $surfaceDb
Write-Host "balanced surface grip for faster turns"
