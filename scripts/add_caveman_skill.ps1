<#
.SYNOPSIS
    Copies the caveman skill from the user's global config to each agent's skills folder.
.DESCRIPTION
    Ensures each agent (performance, security, sre) has access to the caveman skill
    to enable ultra-compressed communication and token savings when requested.
#>

$ErrorActionPreference = "Stop"

$sourceSkillPath = "C:\Users\Fred\.gemini\config\skills\caveman\SKILL.md"
if (-not (Test-Path $sourceSkillPath)) {
    Write-Error "Source caveman skill not found at $sourceSkillPath"
    exit 1
}

$agentsDir = Join-Path $PSScriptRoot "..\app\agents" | Resolve-Path
$roles = @("performance", "security", "sre")

Write-Host "Deploying caveman skill to agent directories..." -ForegroundColor Cyan

foreach ($role in $roles) {
    $targetDir = Join-Path $agentsDir "$role\skills\caveman"
    $targetFile = Join-Path $targetDir "SKILL.md"

    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    Copy-Item -Path $sourceSkillPath -Destination $targetFile -Force
    Write-Host "  [+] Copied caveman skill -> $role\skills\caveman\SKILL.md" -ForegroundColor Green
}

Write-Host "`nCaveman skill deployment complete!" -ForegroundColor Cyan
