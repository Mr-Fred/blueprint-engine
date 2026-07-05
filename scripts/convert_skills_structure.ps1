<#
.SYNOPSIS
    Converts skill files from app/agents/<role>/skills/<skill-name>.md to app/agents/<role>/skills/<skill-name>/SKILL.md
.DESCRIPTION
    Scans all agent skill directories for standalone Markdown files and restructures them into canonical skill folders.
#>

$ErrorActionPreference = "Stop"

$agentsDir = Join-Path $PSScriptRoot "..\app\agents" | Resolve-Path
if (-not (Test-Path $agentsDir)) {
    Write-Error "Agents directory not found at $agentsDir"
    exit 1
}

Write-Host "Scanning agent skill folders in $agentsDir..." -ForegroundColor Cyan

$mdFiles = Get-ChildItem -Path $agentsDir -Filter "*.md" -Recurse | Where-Object {
    $_.Directory.Name -eq "skills" -and $_.Name -ne "SKILL.md"
}

if ($mdFiles.Count -eq 0) {
    Write-Host "No standalone skill markdown files found to convert." -ForegroundColor Green
    exit 0
}

foreach ($file in $mdFiles) {
    $skillName = $file.BaseName
    $targetDir = Join-Path $file.DirectoryName $skillName
    $targetFile = Join-Path $targetDir "SKILL.md"

    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    Move-Item -Path $file.FullName -Destination $targetFile -Force
    Write-Host "  [+] Converted: $($file.Name) -> $skillName\SKILL.md" -ForegroundColor Green
}

Write-Host "`nConversion complete! All skills are now structured as skills/<skill-name>/SKILL.md." -ForegroundColor Cyan
