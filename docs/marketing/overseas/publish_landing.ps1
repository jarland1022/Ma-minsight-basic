#Requires -Version 5.1
<#
.SYNOPSIS
  Build site/index.html from landing.html + landing.env, then print GitHub Pages next steps.

.EXAMPLE
  cd docs/marketing/overseas
  copy landing.env.example landing.env
  .\publish_landing.ps1

.EXAMPLE
  .\publish_landing.ps1 -PushGhPages
#>
param(
  [switch]$PushGhPages,
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $Here "..\..\..")).Path
}

$EnvFile = Join-Path $Here "landing.env"
# Canonical source for Pages workflow is docs/marketing/landing.html
$Src = Join-Path $Here "..\landing.html"
if (-not (Test-Path $Src)) { $Src = Join-Path $Here "landing.html" }
$SiteDir = Join-Path $RepoRoot "site"
$Out = Join-Path $SiteDir "index.html"

if (-not (Test-Path $Src)) { throw "Missing $Src" }
if (-not (Test-Path $EnvFile)) {
  Write-Host "Create landing.env first:" -ForegroundColor Yellow
  Write-Host "  copy `"$Here\landing.env.example`" `"$EnvFile`""
  Write-Host "  notepad `"$EnvFile`""
  exit 1
}

$replacements = @{}
Get-Content $EnvFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $i = $line.IndexOf("=")
  if ($i -lt 1) { return }
  $k = $line.Substring(0, $i).Trim()
  $v = $line.Substring($i + 1).Trim()
  $replacements[$k] = $v
}

$required = @("YOUR_WHATSAPP_URL", "YOUR_CALENDLY_URL", "YOUR_GITHUB_URL", "YOUR_EMAIL", "YOUR_COMPANY")
foreach ($k in $required) {
  if (-not $replacements.ContainsKey($k) -or -not $replacements[$k] -or $replacements[$k] -match "YOUR_|example\.com|XXXXXXXX") {
    Write-Warning "Please set a real value for $k in landing.env"
  }
}

$html = Get-Content -Raw -Encoding UTF8 $Src
foreach ($k in $replacements.Keys) {
  $html = $html.Replace($k, $replacements[$k])
}

if ($html -match "YOUR_WHATSAPP_URL|YOUR_CALENDLY_URL|YOUR_GITHUB_URL|YOUR_EMAIL|YOUR_COMPANY") {
  Write-Warning "Some YOUR_* placeholders remain — edit landing.env and re-run."
}

New-Item -ItemType Directory -Force -Path $SiteDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($Out, $html, $utf8NoBom)

$CnameExample = Join-Path $SiteDir "CNAME.example"
if (-not (Test-Path $CnameExample)) {
  Set-Content -Path $CnameExample -Value "www.example.com" -Encoding ASCII
}

Write-Host ""
Write-Host "Built: $Out" -ForegroundColor Green
Write-Host ""
Write-Host "Next (pick one):" -ForegroundColor Cyan
Write-Host "  A) GitHub Actions (recommended)"
Write-Host "     1. Commit and push Ma-minsight-basic (includes pages-landing.yml)"
Write-Host "     2. Settings → Pages → Source: GitHub Actions"
Write-Host "     3. Variables: WHATSAPP_URL, CALENDLY_URL, GITHUB_URL, EMAIL, COMPANY"
Write-Host "     4. Actions → Deploy landing (GitHub Pages) → Run workflow"
Write-Host "     URL: https://jarland1022.github.io/Ma-minsight-basic/"
Write-Host ""
Write-Host "  B) One-shot orphan branch from this machine"
Write-Host "     .\publish_landing.ps1 -PushGhPages"
Write-Host ""

if (-not $PushGhPages) { exit 0 }

Push-Location $RepoRoot
try {
  $branch = "gh-pages"
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
  $tmp = Join-Path $env:TEMP "ma-minsight-gh-pages-$(Get-Random)"
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  Copy-Item $Out (Join-Path $tmp "index.html")
  if (Test-Path (Join-Path $SiteDir "CNAME")) {
    Copy-Item (Join-Path $SiteDir "CNAME") (Join-Path $tmp "CNAME")
  }

  Push-Location $tmp
  git init -b $branch | Out-Null
  git add index.html
  if (Test-Path "CNAME") { git add CNAME }
  git -c user.email="pages@ma-minsight.local" -c user.name="MA-MinSight Pages" commit -m "landing: $stamp" | Out-Null
  $remote = (git -C $RepoRoot remote get-url origin)
  git remote add origin $remote
  Write-Host "Pushing orphan $branch to origin (force)..." -ForegroundColor Yellow
  git push -f origin "${branch}:${branch}"
  Pop-Location
  Remove-Item -Recurse -Force $tmp

  Write-Host "Done. Set Pages source to branch gh-pages / root." -ForegroundColor Green
  Write-Host "Settings → Pages → Deploy from branch → gh-pages → / (root)"
}
finally {
  Pop-Location
}
