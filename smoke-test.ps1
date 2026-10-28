param(
    [string]$ApiBaseUrl = "http://localhost:8001",
    [string]$FrontendBaseUrl = "http://localhost:8502",
    [string]$PrometheusBaseUrl = "http://localhost:9091",
    [string]$GrafanaBaseUrl = "http://localhost:3001",
    [string]$OpenSearchBaseUrl = "http://localhost:9201",
    [int]$TimeoutSeconds = 8
)

$ErrorActionPreference = "Stop"
$checks = [System.Collections.Generic.List[object]]::new()

function Add-SmokeCheck {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    try {
        $detail = & $Action
        $checks.Add([pscustomobject]@{
            Name = $Name
            Passed = $true
            Detail = [string]$detail
        })
    } catch {
        $checks.Add([pscustomobject]@{
            Name = $Name
            Passed = $false
            Detail = $_.Exception.Message
        })
    }
}

function Test-HttpEndpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedContent
    )

    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 400) {
        throw "$Name returned HTTP $($response.StatusCode): $Url"
    }

    if ($ExpectedContent -and $response.Content -notmatch $ExpectedContent) {
        throw "$Name returned HTTP $($response.StatusCode), but expected content pattern '$ExpectedContent' was absent."
    }

    return "HTTP $($response.StatusCode) $Url"
}

function Test-PrometheusTarget {
    param([string]$JobName)

    $targetResponse = Invoke-RestMethod `
        -Uri "$PrometheusBaseUrl/api/v1/targets" `
        -TimeoutSec $TimeoutSeconds
    if ($targetResponse.status -ne "success") {
        throw "Prometheus targets API returned status '$($targetResponse.status)'."
    }

    $target = @($targetResponse.data.activeTargets | Where-Object {
        $_.labels.job -eq $JobName
    })
    if ($target.Count -eq 0) {
        throw "No active Prometheus target found for job '$JobName'."
    }

    $down = @($target | Where-Object { $_.health -ne "up" })
    if ($down.Count -gt 0) {
        $details = ($down | ForEach-Object {
            "$($_.scrapeUrl): $($_.lastError)"
        }) -join "; "
        throw "Prometheus target '$JobName' is not UP: $details"
    }

    return "$($target.Count) target(s) UP"
}

function Test-AnonymousItemRoute {
    param(
        [string]$Method,
        [string]$Url,
        [string]$Body
    )

    $request = [System.Net.HttpWebRequest]::Create($Url)
    $request.Method = $Method
    $request.Timeout = $TimeoutSeconds * 1000
    if ($Body) {
        $request.ContentType = "application/json"
        $bytes = [Text.Encoding]::UTF8.GetBytes($Body)
        $request.ContentLength = $bytes.Length
        $stream = $request.GetRequestStream()
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Dispose()
    }

    try {
        $response = $request.GetResponse()
        $statusCode = [int]$response.StatusCode
        $response.Dispose()
    } catch [System.Net.WebException] {
        if (-not $_.Exception.Response) {
            throw $_.Exception
        }
        $statusCode = [int]$_.Exception.Response.StatusCode
        $_.Exception.Response.Dispose()
    }

    if ($statusCode -ne 401) {
        throw "$Method $Url should reject anonymous access with HTTP 401, received HTTP $statusCode."
    }

    return "$Method returned HTTP 401 without a Bearer token"
}

Write-Host "AgroTech Enterprise - smoke test"
Write-Host "API: $ApiBaseUrl | Prometheus: $PrometheusBaseUrl | Grafana: $GrafanaBaseUrl"
Write-Host ""

Add-SmokeCheck "Docker Compose config" {
    $output = & docker compose config --quiet 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose config failed: $($output -join ' ')"
    }
    return "Compose configuration valid"
}

if (Get-Command kubectl -ErrorAction SilentlyContinue) {
    Add-SmokeCheck "Kubernetes Kustomize manifests" {
        $output = & kubectl apply --dry-run=client -k k8s 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Kubernetes manifest validation failed: $($output -join ' ')"
        }
        return "Kustomize bundle passed client dry-run; no resources were applied"
    }
} else {
    Write-Host "[SKIP] Kubernetes manifest validation: kubectl is not installed." -ForegroundColor Yellow
}

Add-SmokeCheck "PostgreSQL connection and SELECT 1" {
    $postgresUser = (& docker compose exec -T db_v2 printenv POSTGRES_USER 2>&1 | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $postgresUser) {
        throw "Could not read POSTGRES_USER from the database container."
    }

    $databaseName = (& docker compose exec -T db_v2 printenv POSTGRES_DB 2>&1 | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $databaseName) {
        throw "Could not read POSTGRES_DB from the database container."
    }

    $readyOutput = & docker compose exec -T db_v2 pg_isready -U $postgresUser -d $databaseName 2>&1
    $readyExitCode = $LASTEXITCODE
    if ($readyExitCode -ne 0) {
        throw "pg_isready failed (exit $readyExitCode): $($readyOutput -join ' ')"
    }

    $output = & docker compose exec -T db_v2 psql -U $postgresUser -d $databaseName -Atqc "SELECT 1" 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "PostgreSQL query failed (exit $exitCode): $($output -join ' ')"
    }
    if (($output -join "`n") -notmatch "(?m)^1\s*$") {
        throw "PostgreSQL connected but SELECT 1 did not return 1: $($output -join ' ')"
    }
    return "pg_isready passed; SELECT 1 returned 1"
}

Add-SmokeCheck "FastAPI docs" {
    Test-HttpEndpoint "FastAPI docs" "$ApiBaseUrl/docs" "swagger"
}

Add-SmokeCheck "FastAPI Prometheus metrics" {
    Test-HttpEndpoint "FastAPI metrics" "$ApiBaseUrl/metrics" "http_requests_total"
}

Add-SmokeCheck "Protected item read/write routes reject anonymous access" {
    $read = Test-AnonymousItemRoute "GET" "$ApiBaseUrl/items/" ""
    $write = Test-AnonymousItemRoute "POST" "$ApiBaseUrl/items/" '{"name":"smoke-test-auth-denied"}'
    "$read; $write"
}

Add-SmokeCheck "Streamlit health" {
    Test-HttpEndpoint "Streamlit" "$FrontendBaseUrl/_stcore/health" "ok"
}

Add-SmokeCheck "Prometheus health" {
    Test-HttpEndpoint "Prometheus" "$PrometheusBaseUrl/-/healthy" "Prometheus"
}

Add-SmokeCheck "Prometheus FastAPI scrape target" {
    Test-PrometheusTarget "fastapi"
}

Add-SmokeCheck "Prometheus PostgreSQL exporter scrape target" {
    Test-PrometheusTarget "postgres"
}

Add-SmokeCheck "Grafana health" {
    Test-HttpEndpoint "Grafana" "$GrafanaBaseUrl/api/health" '"database"\s*:\s*"ok"'
}

Add-SmokeCheck "OpenSearch health" {
    Test-HttpEndpoint "OpenSearch" "$OpenSearchBaseUrl/" '"cluster_name"'
}

Write-Host "Resultados:"
foreach ($check in $checks) {
    if ($check.Passed) {
        Write-Host "[PASS] $($check.Name): $($check.Detail)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $($check.Name): $($check.Detail)" -ForegroundColor Red
    }
}

$failedChecks = @($checks | Where-Object { -not $_.Passed })
Write-Host ""
if ($failedChecks.Count -gt 0) {
    Write-Host "$($failedChecks.Count) de $($checks.Count) verificacoes falharam." -ForegroundColor Red
    Write-Host "Diagnostico: execute 'docker compose ps' e 'docker compose logs --tail 100 <servico>'."
    exit 1
}

Write-Host "Todas as $($checks.Count) verificacoes passaram." -ForegroundColor Green
exit 0
