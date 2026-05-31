$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "extracted\Base"
$backupRoot = Join-Path $PSScriptRoot ("backup_insane_json_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Read-Json($path) {
    return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-Json($path, $obj) {
    $json = $obj | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($path, $json + [Environment]::NewLine, $utf8NoBom)
}

function Backup-File($path) {
    $fullRoot = [System.IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
    $fullPath = [System.IO.Path]::GetFullPath($path)
    $rel = $fullPath.Substring($fullRoot.Length)
    $dst = Join-Path $backupRoot $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $path -Destination $dst -Force
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
    $props = Get-Prop $transform "Properties"
    return $props
}

function Touch-JsonFile($path, [scriptblock]$edit) {
    Backup-File $path
    $doc = Read-Json $path
    & $edit $doc
    Write-Json $path $doc
    Write-Host "edited $([System.IO.Path]::GetFileName($path))"
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

New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$db = Join-Path $root "VuDBAsset"

Touch-JsonFile (Join-Path $db "CarDB.bin.json") {
    param($doc)
    $cars = $doc.VuDBAsset
    foreach ($carProp in $cars.PSObject.Properties) {
        $car = $carProp.Value
        if ($carProp.Name -eq "Default") {
            Set-Prop $car "Draw Distance" 900.0
            Set-Prop $car "Inertia Factor" 0.75
            Set-Prop $car "Max Steering Angle" 58.0
            $chassis = Get-Prop $car "Chassis"
            if ($chassis) {
                Set-Prop $chassis "Aero Lift" -90
                Set-Prop $chassis "Air Steering Speed" 220
                Set-Prop $chassis "Fast Steering Speed" 180
                Set-Prop $chassis "Slow Steering Speed" 120
                Set-Prop $chassis "Fast Steering Boat Speed" 180
                Set-Prop $chassis "Slow Steering Boat Speed" 80
                Set-Prop $chassis "Lat Skin Friction Coeff" 0.02
                Set-Prop $chassis "Long Skin Friction Coeff" 0.02
                Set-Prop $chassis "Power Slide Coeff" 0.12
                $stability = Get-Prop $chassis "Stability"
                if ($stability) { $stability.X = 25; $stability.Y = 28; $stability.Z = 25 }
            }
        } else {
            Set-Prop $car "Breakable Penalty" 0.0
            Set-Prop $car "Mass" 420
            Set-Prop $car "Max Braking Force" 65000
            $camera = Get-Prop $car "Camera"
            if ($camera) {
                Set-Prop $camera "Ideal Distance" 6
                Set-Prop $camera "Ideal Pitch" -18
                Set-Prop $camera "Lag Distance" 0.25
                Set-Prop $camera "Max Stay Behind Factor" 1.0
            }
            $chassis = Get-Prop $car "Chassis"
            if ($chassis) { Set-Prop $chassis "Drag Coeff" 0.035 }
            $suspension = Get-Prop $car "Suspension"
            if ($suspension) {
                Set-Prop $suspension "Damping Coeff" 12000.0
                Set-Prop $suspension "Lower Spring Coeff" 62000.0
                Set-Prop $suspension "Upper Spring Coeff" 124000.0
                Set-Prop $suspension "Power Slide Coeff" 0.1
                Set-Prop $suspension "Rollover Resistance" 12.0
                Set-Prop $suspension "Wheelie Resistance" 12.0
            }
        }
    }
}

Touch-JsonFile (Join-Path $db "CarUpgradeDB.bin.json") {
    param($doc)
    foreach ($entryProp in $doc.VuDBAsset.PSObject.Properties) {
        $entry = $entryProp.Value
        $engine = Get-Prop $entry "Engine"
        if ($engine) {
            Set-Prop $engine "Max Forward Speed" 720
            Set-Prop $engine "Max Power" 5200
            $curve = Get-Prop $engine "Torque Curve"
            if ($curve) {
                foreach ($point in $curve) {
                    if ($point.Count -ge 2) { $point[1] = 950 }
                }
            }
        }
        $stats = Get-Prop $entry "Stats"
        if ($stats) {
            Set-Prop $stats "Accel" 99
            Set-Prop $stats "Speed" 99
            Set-Prop $stats "Tough" 99
        }
    }
}

Touch-JsonFile (Join-Path $db "PowerUpDB.bin.json") {
    param($doc)
    foreach ($powerProp in $doc.VuDBAsset.PSObject.Properties) {
        $levels = Get-Prop $powerProp.Value "Levels"
        if (-not $levels) { continue }
        foreach ($level in $levels) {
            if (Get-Prop $level "Duration") { Set-Prop $level "Duration" 120 }
            if (Get-Prop $level "Power") { Set-Prop $level "Power" 12.0 }
            if (Get-Prop $level "Speed") { Set-Prop $level "Speed" 950 }
            if (Get-Prop $level "Distance") { Set-Prop $level "Distance" 260 }
            if (Get-Prop $level "SuckTime") { Set-Prop $level "SuckTime" 0.02 }
            if (Get-Prop $level "Coins") { Set-Prop $level "Coins" 50000 }
            Set-Prop $level "CoinBonus" 25
            Set-Prop $level "Penalty" 0
            Set-Prop $level "SmashCars" $true
            foreach ($size in @("Tiny", "Small", "Medium", "Large", "Car")) {
                $impact = Get-Prop $level $size
                if ($impact -and (Get-Prop $impact "Coins")) { Set-Prop $impact "Coins" 1000 }
            }
        }
    }
}

Touch-JsonFile (Join-Path $db "UpgradeDB.bin.json") {
    param($doc)
    foreach ($upgradeProp in $doc.VuDBAsset.PSObject.Properties) {
        $levels = Get-Prop $upgradeProp.Value "Levels"
        if (-not $levels) { continue }
        foreach ($level in $levels) {
            if (Get-Prop $level "TimeBonus") { Set-Prop $level "TimeBonus" 60 }
            if (Get-Prop $level "TimeBonusDist") { Set-Prop $level "TimeBonusDist" 0 }
            Set-Prop $level "CoinBonus" 1000
            Set-Prop $level "CoinBonusDist" 0
        }
    }
}

Touch-JsonFile (Join-Path $db "RewardDB.bin.json") {
    param($doc)
    foreach ($rewardProp in $doc.VuDBAsset.PSObject.Properties) {
        $reward = $rewardProp.Value
        if (Get-Prop $reward "Coins") { Set-Prop $reward "Coins" 999999 }
        if (Get-Prop $reward "ExtraTime") { Set-Prop $reward "ExtraTime" 999 }
    }
}

Touch-JsonFile (Join-Path $db "SurfaceDB.bin.json") {
    param($doc)
    foreach ($surfaceProp in $doc.VuDBAsset.PSObject.Properties) {
        $surface = $surfaceProp.Value
        if (Get-Prop $surface "Friction") {
            if ($surfaceProp.Name -eq "<none>") { Set-Prop $surface "Friction" 1.2 }
            elseif ($surfaceProp.Name -eq "Ice") { Set-Prop $surface "Friction" 1.6 }
            else { Set-Prop $surface "Friction" 2.4 }
        }
    }
}

$foliageDir = Join-Path $root "VuTemplateAsset\Foliage"
Get-ChildItem -LiteralPath $foliageDir -Filter "*.json" | ForEach-Object {
    Touch-JsonFile $_.FullName {
        param($doc)
        ForEach-Node $doc {
            param($node)
            if ($node -isnot [pscustomobject]) { return }
            $components = Get-Prop $node "Components"
            $transform = Get-Prop $components "VuTransformComponent"
            $props = Get-Prop $transform "Properties"
            if ($props) {
                $scale = if ($_.FullName -match "Grasses") { 4.0 } else { 7.0 }
                Set-Prop $props "Scale" (Vec3 $scale $scale $scale)
            }
            $properties = Get-Prop $node "Properties"
            if ($properties) { Set-Prop $properties "Draw Distance" 1200 }
        }
    }
}

foreach ($palmTemplate in @("Breakable_Palm.bin.json", "Breakable_Palm_B.bin.json", "Breakable_Evergreen.bin.json")) {
    $path = Join-Path $root ("VuTemplateAsset\Breakable\" + $palmTemplate)
    if (Test-Path -LiteralPath $path) {
        Touch-JsonFile $path {
            param($doc)
            ForEach-Node $doc {
                param($node)
                if ($node -isnot [pscustomobject]) { return }
                $props = Get-Prop (Get-Prop $node "Vu3dDrawStaticModelComponent") "Properties"
                $components = Get-Prop $node "Components"
                if ($components) {
                    $draw = Get-Prop $components "Vu3dDrawStaticModelComponent"
                    $drawProps = Get-Prop $draw "Properties"
                    if ($drawProps) {
                        Set-Prop $drawProps "Draw Distance" 1800
                        Set-Prop $drawProps "LOD 0 Draw Distance" 900
                    }
                    $body = Get-Prop $components "VuRigidBodyComponent"
                    $bodyProps = Get-Prop $body "Properties"
                    if ($bodyProps) {
                        Set-Prop $bodyProps "Collision Radius" 3.0
                        Set-Prop $bodyProps "Collision Size" (Vec3 5 5 22)
                    }
                }
            }
        }
    }
}

function Add-Setup-Clones($container, [string]$fileStem) {
    if ($container -isnot [System.Array]) { return $container }
    $new = @()
    foreach ($item in $container) { $new += $item }

    $palmCount = 0
    $coinCount = 0
    $obstacleCount = 0

    foreach ($entity in $container) {
        if ($entity -isnot [pscustomobject]) { continue }
        $type = Get-Prop $entity "type"
        $name = Get-Prop $entity "name"
        $props = Transform-Props $entity
        if (-not $props) { continue }
        $pos = Get-Prop $props "Position"
        if (-not $pos) { continue }

        if ($type -like "#Breakable/Breakable_Palm*") {
            Set-Prop $props "Scale" (Vec3 4.5 4.5 4.5)
            if ($palmCount -lt 18) {
                foreach ($i in 1..2) {
                    $clone = Clone-Json $entity
                    Set-Prop $clone "name" ("{0}_GIANT{1:D2}" -f $name, $i)
                    $cprops = Transform-Props $clone
                    $cpos = Get-Prop $cprops "Position"
                    $cpos.X = [double]$cpos.X + (14 * $i) + (($palmCount % 3) * 9)
                    $cpos.Y = [double]$cpos.Y + (22 * $i)
                    $cpos.Z = [double]$cpos.Z + 0.5
                    Set-Prop $cprops "Scale" (Vec3 (5.5 + $i) (5.5 + $i) (5.5 + $i))
                    $new += $clone
                }
                $palmCount++
            }
        } elseif ($type -eq "#Powerup/Powerup_Coin") {
            if ($coinCount -lt 10) {
                foreach ($i in 1..3) {
                    $clone = Clone-Json $entity
                    Set-Prop $clone "name" ("{0}_RAIN{1:D2}" -f $name, $i)
                    $cprops = Transform-Props $clone
                    $cpos = Get-Prop $cprops "Position"
                    $cpos.X = [double]$cpos.X + (($i - 2) * 5)
                    $cpos.Y = [double]$cpos.Y + (1.5 * $i)
                    $cpos.Z = [double]$cpos.Z + 2
                    Set-Prop $cprops "Scale" (Vec3 2.2 2.2 2.2)
                    $new += $clone
                }
                $coinCount++
            }
        } elseif ($type -like "#Dynamic/Dynamic_*" -or $type -like "#Breakable/Breakable_Barrel*" -or $type -like "#Breakable/Breakable_Crate*" -or $type -like "#Breakable/Breakable_TurnSign*") {
            if ($obstacleCount -lt 8) {
                $clone = Clone-Json $entity
                Set-Prop $clone "name" ("{0}_CHAOS{1:D2}" -f $name, ($obstacleCount + 1))
                $cprops = Transform-Props $clone
                $cpos = Get-Prop $cprops "Position"
                $cpos.X = [double]$cpos.X + ((($obstacleCount % 4) - 1.5) * 8)
                $cpos.Y = [double]$cpos.Y + (10 + ($obstacleCount * 3))
                $cpos.Z = [double]$cpos.Z + 1
                Set-Prop $cprops "Scale" (Vec3 2.8 2.8 2.8)
                $new += $clone
                $obstacleCount++
            }
        }
    }
    return @($new)
}

function Mod-Setup-Node($node, [string]$fileStem) {
    if ($node -isnot [pscustomobject]) { return }

    foreach ($p in @($node.PSObject.Properties)) {
        if ($p.Name -like "Foliage_*" -and $p.Value -is [pscustomobject]) {
            $components = Get-Prop $p.Value "Components"
            $transform = Get-Prop $components "VuTransformComponent"
            $props = Get-Prop $transform "Properties"
            if ($props) { Set-Prop $props "Scale" (Vec3 5.5 5.5 5.5) }
        }

        if ($p.Name -eq "ChildEntities" -and $p.Value -is [System.Array]) {
            $node.PSObject.Properties[$p.Name].Value = Add-Setup-Clones $p.Value $fileStem
        }
    }
}

$setupsDir = Join-Path $root "VuProjectAsset\Setups"
Get-ChildItem -LiteralPath $setupsDir -Filter "*.json" | Where-Object {
    $_.Name -match "Shore|Cave|Swamp|Temple|Snow|Volcano"
} | ForEach-Object {
    $path = $_.FullName
    $stem = $_.BaseName
    Touch-JsonFile $path {
        param($doc)
        ForEach-Node $doc { param($node) Mod-Setup-Node $node $stem }
    }
}

Write-Host "Backups saved in: $backupRoot"
