param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ClaudeSkillsRoot = (Join-Path $env:USERPROFILE ".claude\skills"),
    [string]$AgentsSkillsRoot = (Join-Path $env:USERPROFILE ".agents\skills")
)

$SkillSource = Join-Path $RepoRoot "skill"

function Install-SkillTo {
    param(
        [string]$Label,
        [string]$TargetRoot
    )

    $Dest = Join-Path $TargetRoot "read-video"

    try {
        if (-not (Test-Path $TargetRoot)) {
            New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
        }
        if (-not (Test-Path $Dest)) {
            New-Item -ItemType Directory -Path $Dest -Force | Out-Null
        }

        Copy-Item -Path (Join-Path $SkillSource "*") -Destination $Dest -Recurse -Force

        [Console]::WriteLine("RESULT $Label copy OK")
        return $Dest
    } catch {
        [Console]::WriteLine("RESULT $Label copy FAILED $($_.Exception.Message)")
        return $null
    }
}

$targets = @(
    @{ Label = "claude"; Root = $ClaudeSkillsRoot },
    @{ Label = "agents"; Root = $AgentsSkillsRoot }
)

$anySucceeded = $false

foreach ($t in $targets) {
    $dest = Install-SkillTo -Label $t.Label -TargetRoot $t.Root
    if ($dest) {
        $anySucceeded = $true
    }
}

if (-not $anySucceeded) {
    [Console]::WriteLine("SUMMARY all targets FAILED")
    exit 1
} else {
    [Console]::WriteLine("SUMMARY install complete")
    exit 0
}
