$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    Write-Host "A atualizar o ficheiro hosts do Windows. Será solicitado acesso de administrador."
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $process = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    exit $process.ExitCode
}

Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker não foi encontrado. Instale o Docker Desktop e execute este instalador novamente."
}

docker compose version
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose não está disponível. Atualize ou instale o Docker Desktop."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "O Docker não está ativo. Inicie o Docker Desktop e execute este instalador novamente."
}

$envPath = Join-Path $PSScriptRoot ".env"
$exampleEnvPath = Join-Path $PSScriptRoot ".env.example"
if (-not (Test-Path -LiteralPath $envPath)) {
    if (-not (Test-Path -LiteralPath $exampleEnvPath)) {
        throw "Não foi encontrado .env.example para criar a configuração inicial."
    }

    Copy-Item -LiteralPath $exampleEnvPath -Destination $envPath
    Write-Host "Ficheiro .env criado a partir de .env.example."
} else {
    Write-Host "Ficheiro .env existente preservado."
}

docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "A configuração do Docker Compose é inválida."
}

$hostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$beginMarker = "# BEGIN app_v2 AgroTech local hosts"
$endMarker = "# END app_v2 AgroTech local hosts"
$managedHosts = @("agrotech.local", "grafana.local", "prometheus.local")
$hostsContent = [System.IO.File]::ReadAllText($hostsPath)
$hostLines = @($hostsContent -split "\r?\n")
$beginIndexes = @(
    for ($index = 0; $index -lt $hostLines.Count; $index++) {
        if ($hostLines[$index].Trim() -eq $beginMarker) { $index }
    }
)
$endIndexes = @(
    for ($index = 0; $index -lt $hostLines.Count; $index++) {
        if ($hostLines[$index].Trim() -eq $endMarker) { $index }
    }
)

if ($beginIndexes.Count -ne $endIndexes.Count -or $beginIndexes.Count -gt 1) {
    throw "Os marcadores geridos pelo instalador no ficheiro hosts estão incompletos ou duplicados."
}

$unmanagedLines = $hostLines
if ($beginIndexes.Count -eq 1) {
    if ($beginIndexes[0] -ge $endIndexes[0]) {
        throw "A ordem dos marcadores geridos no ficheiro hosts é inválida."
    }

    $unmanagedLines = @(
        for ($index = 0; $index -lt $hostLines.Count; $index++) {
            if ($index -lt $beginIndexes[0] -or $index -gt $endIndexes[0]) {
                $hostLines[$index]
            }
        }
    )
}

$existingHosts = @{}
foreach ($line in $unmanagedLines) {
    $entry = ($line -split "#", 2)[0].Trim()
    if (-not $entry) { continue }

    $parts = @($entry -split "\s+")
    if ($parts.Count -lt 2) { continue }

    foreach ($hostname in $managedHosts) {
        if ($parts[1..($parts.Count - 1)] -contains $hostname) {
            if ($parts[0] -ne "127.0.0.1") {
                throw "O hostname $hostname já está associado a $($parts[0]) fora da secção gerida. Corrija essa entrada manualmente."
            }
            $existingHosts[$hostname] = $true
        }
    }
}

$newEntries = @(
    foreach ($hostname in $managedHosts) {
        if (-not $existingHosts.ContainsKey($hostname)) {
            "127.0.0.1`t$hostname"
        }
    }
)
$managedSection = @($beginMarker) + $newEntries + @($endMarker)
$updatedLines = @($unmanagedLines)
if ($updatedLines.Count -gt 0 -and $updatedLines[-1] -ne "") {
    $updatedLines += ""
}
$updatedLines += $managedSection
[System.IO.File]::WriteAllText(
    $hostsPath,
    (($updatedLines -join [Environment]::NewLine).TrimEnd() + [Environment]::NewLine),
    [System.Text.UTF8Encoding]::new($false)
)
ipconfig /flushdns | Out-Null
Write-Host "Endereços locais configurados no ficheiro hosts."

Write-Host "A construir e iniciar a stack AgroTech Enterprise..."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "Não foi possível iniciar a stack. Consulte as mensagens do Docker Compose acima."
}

Write-Host ""
Write-Host "Stack iniciada. Endereços locais:"
Write-Host "Frontend Streamlit: http://agrotech.local:8502"
Write-Host "API FastAPI:        http://agrotech.local:8001/docs"
Write-Host "Grafana:            http://grafana.local:3001"
Write-Host "Prometheus:         http://prometheus.local:9091"
Write-Host "Grafana utilizador: admin"
Write-Host "Consulte GRAFANA_ADMIN_PASSWORD no .env para a palavra-passe."
