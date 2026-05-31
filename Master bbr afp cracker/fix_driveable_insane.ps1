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

function Vec3($x, $y, $z) {
    [pscustomobject]@{ X = [double]$x; Y = [double]$y; Z = [double]$z }
}

$carDbPath = Join-Path $root "CarDB.bin.json"
$carDb = Read-Json $carDbPath
foreach ($carProp in $carDb.VuDBAsset.PSObject.Properties) {
    $car = $carProp.Value
    if ($carProp.Name -eq "Default") {
        Set-Prop $car "Draw Distance" 500.0
        Set-Prop $car "Inertia Factor" 1.5
        Set-Prop $car "Max Steering Angle" 38.0
        $chassis = Get-Prop $car "Chassis"
        if ($chassis) {
            Set-Prop $chassis "Aero Lift" -25
            Set-Prop $chassis "Air Steering Speed" 95
            Set-Prop $chassis "Fast Steering Speed" 105
            Set-Prop $chassis "Slow Steering Speed" 65
            Set-Prop $chassis "Fast Steering Boat Speed" 100
            Set-Prop $chassis "Slow Steering Boat Speed" 35
            Set-Prop $chassis "Lat Skin Friction Coeff" 0.16
            Set-Prop $chassis "Long Skin Friction Coeff" 0.04
            Set-Prop $chassis "Power Slide Coeff" 0.45
            $stability = Get-Prop $chassis "Stability"
            if ($stability) { $stability.X = 7; $stability.Y = 9; $stability.Z = 7 }
        }
    } else {
        Set-Prop $car "Breakable Penalty" 0.15
        Set-Prop $car "Mass" 900
        Set-Prop $car "Max Braking Force" 18000
        $camera = Get-Prop $car "Camera"
        if ($camera) {
            Set-Prop $camera "Ideal Distance" 4
            Set-Prop $camera "Ideal Pitch" -23
            Set-Prop $camera "Lag Distance" 1.0
            Set-Prop $camera "Max Stay Behind Factor" 0.65
        }
        $chassis = Get-Prop $car "Chassis"
        if ($chassis) { Set-Prop $chassis "Drag Coeff" 0.22 }
        $suspension = Get-Prop $car "Suspension"
        if ($suspension) {
            Set-Prop $suspension "Damping Coeff" 5200.0
            Set-Prop $suspension "Lower Spring Coeff" 22000.0
            Set-Prop $suspension "Upper Spring Coeff" 44000.0
            Set-Prop $suspension "Power Slide Coeff" 0.45
            Set-Prop $suspension "Rollover Resistance" 1.6
            Set-Prop $suspension "Wheelie Resistance" 1.2
            Set-Prop $suspension "Visual Extension Rate" 3.0
        }
    }
}
Write-Json $carDbPath $carDb
Write-Host "fixed CarDB physics"

$upgradePath = Join-Path $root "CarUpgradeDB.bin.json"
$upgradeDb = Read-Json $upgradePath
foreach ($entryProp in $upgradeDb.VuDBAsset.PSObject.Properties) {
    $entry = $entryProp.Value
    $engine = Get-Prop $entry "Engine"
    if ($engine) {
        Set-Prop $engine "Max Forward Speed" 275
        Set-Prop $engine "Max Power" 850
        $curve = Get-Prop $engine "Torque Curve"
        if ($curve) {
            foreach ($point in $curve) {
                if ($point.Count -ge 2) { $point[1] = 260 }
            }
        }
    }
    $stats = Get-Prop $entry "Stats"
    if ($stats) {
        Set-Prop $stats "Accel" 12
        Set-Prop $stats "Speed" 12
        Set-Prop $stats "Tough" 12
    }
}
Write-Json $upgradePath $upgradeDb
Write-Host "fixed CarUpgradeDB speed"

$surfacePath = Join-Path $root "SurfaceDB.bin.json"
$surfaceDb = Read-Json $surfacePath
foreach ($surfaceProp in $surfaceDb.VuDBAsset.PSObject.Properties) {
    $surface = $surfaceProp.Value
    if (Get-Prop $surface "Friction") {
        switch ($surfaceProp.Name) {
            "Ice" { Set-Prop $surface "Friction" 0.35 }
            "Sand" { Set-Prop $surface "Friction" 0.55 }
            "Snow" { Set-Prop $surface "Friction" 0.55 }
            "<none>" { Set-Prop $surface "Friction" 0.0 }
            default { Set-Prop $surface "Friction" 0.75 }
        }
    }
}
Write-Json $surfacePath $surfaceDb
Write-Host "fixed SurfaceDB grip"

$powerPath = Join-Path $root "PowerUpDB.bin.json"
$powerDb = Read-Json $powerPath
$boost = Get-Prop $powerDb.VuDBAsset "Boost"
$levels = Get-Prop $boost "Levels"
if ($levels) {
    foreach ($level in $levels) {
        if (Get-Prop $level "Duration") { Set-Prop $level "Duration" 18 }
        if (Get-Prop $level "Power") { Set-Prop $level "Power" 4.0 }
        if (Get-Prop $level "Speed") { Set-Prop $level "Speed" 360 }
    }
}
Write-Json $powerPath $powerDb
Write-Host "fixed Boost so it does not launch the car into nonsense"
