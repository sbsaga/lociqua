param([ValidateSet('app','worker','redis','postgres')] [string] $Service = 'app')

# Run only in a planned maintenance window or disposable environment. This
# intentionally restarts exactly one named compose service, never the full stack.
$ErrorActionPreference = 'Stop'
docker compose -f docker-compose.production.yml restart $Service
if ($LASTEXITCODE -ne 0) { throw "Could not restart $Service" }
Start-Sleep -Seconds 8
if ($Service -eq 'app' -or $Service -eq 'postgres') {
  $response = Invoke-WebRequest -UseBasicParsing http://127.0.0.1/readyz -TimeoutSec 20
  if ($response.StatusCode -ne 200) { throw "Readiness did not recover after $Service restart." }
}
docker compose -f docker-compose.production.yml ps
Write-Host "recovery smoke passed for $Service"
