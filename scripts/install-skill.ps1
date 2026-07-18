param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ClaudeSkillsRoot = (Join-Path $env:USERPROFILE ".claude\skills"),
    [string]$AgentsSkillsRoot = (Join-Path $env:USERPROFILE ".agents\skills")
)

$VoidscapeSource = Join-Path $RepoRoot "skill"
$LegacySource = Join-Path $RepoRoot "compat\read-video"

function Install-SkillTo {
    param(
        [string]$Label,
        [string]$TargetRoot,
        [string]$Name,
        [string]$Source
    )

    $Dest = Join-Path $TargetRoot $Name
    try {
        if (-not (Test-Path $Source)) { throw "source not found: $Source" }
        New-Item -ItemType Directory -Path $Dest -Force | Out-Null
        Copy-Item -Path (Join-Path $Source "*") -Destination $Dest -Recurse -Force
        [Console]::WriteLine("RESULT $Label $Name copy OK")
        return $Dest
    } catch {
        [Console]::WriteLine("RESULT $Label $Name copy FAILED $($_.Exception.Message)")
        return $null
    }
}

function Test-Frontmatter {
    param([string]$Label, [string]$Name, [string]$Dest)
    try {
        $SkillMdPath = Join-Path $Dest "SKILL.md"
        if (-not (Test-Path $SkillMdPath)) { throw "SKILL.md not found" }
        $content = Get-Content $SkillMdPath -Raw
        if ($content -notmatch '(?s)^---\s*(.*?)\s*---') { throw "no frontmatter block found" }
        $frontmatter = $Matches[1]
        if ($frontmatter -notmatch 'name:\s*\S+') { throw "missing name key" }
        if ($frontmatter -notmatch 'description:') { throw "missing description key" }
        Write-Output "RESULT $Label $Name verify:frontmatter OK"
    } catch {
        Write-Output "RESULT $Label $Name verify:frontmatter FAILED $($_.Exception.Message)"
    }
}

function Test-CliRuns {
    param([string]$Label, [string]$Name, [string]$Dest)
    try {
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python not found on PATH" }
        $ScriptPath = Join-Path $Dest "scripts\video.py"
        & python $ScriptPath probe --help *> $null
        if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
        Write-Output "RESULT $Label $Name verify:cli OK"
    } catch {
        Write-Output "RESULT $Label $Name verify:cli FAILED $($_.Exception.Message)"
    }
}

$targets = @(
    @{ Label = "claude"; Root = $ClaudeSkillsRoot },
    @{ Label = "agents"; Root = $AgentsSkillsRoot }
)
$anySucceeded = $false

foreach ($t in $targets) {
    $voidscape = Install-SkillTo -Label $t.Label -TargetRoot $t.Root -Name "voidscape" -Source $VoidscapeSource
    if ($voidscape) {
        $anySucceeded = $true
        Test-Frontmatter -Label $t.Label -Name "voidscape" -Dest $voidscape
        Test-CliRuns -Label $t.Label -Name "voidscape" -Dest $voidscape
    }
    $legacy = Install-SkillTo -Label $t.Label -TargetRoot $t.Root -Name "read-video" -Source $LegacySource
    if ($legacy) {
        $anySucceeded = $true
        Test-Frontmatter -Label $t.Label -Name "read-video" -Dest $legacy
        Test-CliRuns -Label $t.Label -Name "read-video" -Dest $legacy
    }
}

if (-not $anySucceeded) {
    [Console]::WriteLine("SUMMARY all targets FAILED")
    exit 1
}
[Console]::WriteLine("SUMMARY install complete: Voidscape primary, read-video compatibility retained")
exit 0
