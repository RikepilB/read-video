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

function Test-Frontmatter {
    param(
        [string]$Label,
        [string]$Dest
    )

    $SkillMdPath = Join-Path $Dest "SKILL.md"
    try {
        if (-not (Test-Path $SkillMdPath)) {
            throw "SKILL.md not found"
        }
        $content = Get-Content $SkillMdPath -Raw
        if ($content -notmatch '(?s)^---\s*(.*?)\s*---') {
            throw "no frontmatter block found"
        }
        $fm = $Matches[1]
        if ($fm -notmatch 'name:\s*\S+') { throw "missing name key" }
        if ($fm -notmatch 'description:') { throw "missing description key" }
        Write-Output "RESULT $Label verify:frontmatter OK"
    } catch {
        Write-Output "RESULT $Label verify:frontmatter FAILED $($_.Exception.Message)"
    }
}

function Test-CliRuns {
    param(
        [string]$Label,
        [string]$Dest
    )

    $ScriptPath = Join-Path $Dest "scripts\video.py"
    try {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "python not found on PATH" }
        & python $ScriptPath probe --help *> $null
        if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
        Write-Output "RESULT $Label verify:cli OK"
    } catch {
        Write-Output "RESULT $Label verify:cli FAILED $($_.Exception.Message)"
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
        Test-Frontmatter -Label $t.Label -Dest $dest
        Test-CliRuns -Label $t.Label -Dest $dest
    }
}

if (-not $anySucceeded) {
    [Console]::WriteLine("SUMMARY all targets FAILED")
    exit 1
} else {
    [Console]::WriteLine("SUMMARY install complete")
    exit 0
}
