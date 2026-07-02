# CumminsIQ - one-shot publish script
# Run from any PowerShell terminal: .\publish.ps1

$GH      = "C:\Program Files\GitHub CLI\gh.exe"
$RepoDir = "C:\Projects\CumminsIQ"

Set-Location $RepoDir

Write-Host "`n=== Step 1/4  GitHub auth ===" -ForegroundColor Cyan
& $GH auth login --web --git-protocol https
if ($LASTEXITCODE -ne 0) { Write-Host "Auth failed - aborting." -ForegroundColor Red; exit 1 }

Write-Host "`n=== Step 2/4  Create GitHub repo ===" -ForegroundColor Cyan
& $GH repo create CumminsIQ `
  --public `
  --description "AI-powered predictive operations platform - multi-agent orchestration, real-time WebSocket, FastAPI + React" `
  --source . `
  --remote origin `
  --push
if ($LASTEXITCODE -ne 0) { Write-Host "Repo create failed - aborting." -ForegroundColor Red; exit 1 }

Write-Host "`n  GitHub: https://github.com/rajeshgohad/CumminsIQ" -ForegroundColor Green

Write-Host "`n=== Step 3/4  Deploy frontend to Vercel ===" -ForegroundColor Cyan
Set-Location "$RepoDir\frontend"
npx vercel --yes

Write-Host "`n=== Step 4/4  Backend on Railway ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Go to https://railway.app -> New Project -> Deploy from GitHub repo"
Write-Host "  2. Pick  rajeshgohad/CumminsIQ  ->  Root Directory: backend"
Write-Host "  3. Railway auto-runs: uvicorn main:app --host 0.0.0.0 --port PORT"
Write-Host "  4. Copy your Railway public URL, then add these env vars in Vercel:"
Write-Host "       VITE_WS_URL  = wss://<your-railway-url>"
Write-Host "       VITE_API_URL = https://<your-railway-url>"
Write-Host "  5. In Railway -> Variables add:"
Write-Host "       ALLOWED_ORIGINS = https://<your-vercel-url>"
Write-Host ""
Write-Host "Done!" -ForegroundColor Green
