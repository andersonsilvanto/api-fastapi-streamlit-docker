param(
    [switch]$DevelopmentDefaults
)

$ErrorActionPreference = "Stop"

function Read-SecretValue {
    param(
        [string]$Prompt,
        [int]$MinimumLength,
        [switch]$DevelopmentMode,
        [string]$DevelopmentDefault = "1234"
    )

    $secureValue = Read-Host -Prompt $Prompt -AsSecureString
    $credential = [System.Net.NetworkCredential]::new("", $secureValue)
    $value = $credential.Password
    if ($DevelopmentMode -and [string]::IsNullOrEmpty($value)) {
        $value = $DevelopmentDefault
    }

    if ($DevelopmentMode) {
        if ($value.Length -lt 4 -or $value.Length -gt 8) {
            throw "Development secret values must contain between 4 and 8 characters."
        }
    } elseif ($value.Length -lt $MinimumLength) {
        throw "Secret value must contain at least $MinimumLength characters."
    }

    return $value
}

function ConvertTo-SecretData {
    param([string]$Value)

    return [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Value))
}

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl was not found on PATH."
}

$context = & kubectl config current-context
if ($LASTEXITCODE -ne 0) {
    throw "Could not read the active Kubernetes context."
}
Write-Host "Active Kubernetes context: $context"

if ($DevelopmentDefaults -and $context -notmatch "^(kind-|minikube|docker-desktop)") {
    throw "Development defaults are allowed only on local kind, Minikube, or Docker Desktop contexts."
}

& kubectl apply -f (Join-Path $PSScriptRoot "namespace.yaml")
if ($LASTEXITCODE -ne 0) {
    throw "Could not create namespace app."
}

$appEnvironment = "production"
$bootstrapUsername = "admin"
if ($DevelopmentDefaults) {
    Write-Warning "Using weak development-only credentials. Do not expose this cluster or reuse these values."
    $appEnvironment = "development"
    $postgresPassword = Read-SecretValue "PostgreSQL password (Enter for development default 1234)" 4 -DevelopmentMode
    if ($postgresPassword -notmatch "^[A-Za-z0-9._~-]+$") {
        throw "PostgreSQL password must use URL-safe letters, numbers, dot, underscore, tilde or hyphen."
    }

    $bootstrapPassword = Read-SecretValue "Initial admin password (Enter for development default 1234)" 4 -DevelopmentMode
    $jwtSecret = "admin_secret_key_123"
} else {
    $postgresPassword = Read-SecretValue "PostgreSQL password (minimum 16 characters)" 16
    if ($postgresPassword -notmatch "^[A-Za-z0-9._~-]+$") {
        throw "PostgreSQL password must use URL-safe letters, numbers, dot, underscore, tilde or hyphen."
    }

    $bootstrapPassword = Read-SecretValue "Initial admin password (minimum 8 characters, must be changed at first login)" 8
    if (
        $bootstrapPassword.Length -lt 8 -or
        $bootstrapPassword -cnotmatch "[A-Z]" -or
        $bootstrapPassword -cnotmatch "[a-z]" -or
        $bootstrapPassword -notmatch "[0-9]" -or
        $bootstrapPassword -notmatch "[^a-zA-Z0-9\s]"
    ) {
        throw "Initial admin password must meet the API password policy."
    }

    $jwtSecret = Read-SecretValue "JWT signing secret (minimum 32 characters)" 32
}

$existingPostgresSecret = & kubectl get secret postgres-credentials -n app -o name 2>$null
$secretQueryExitCode = $LASTEXITCODE
$existingPostgresVolume = & kubectl get pvc postgres-data-postgres-0 -n app -o name 2>$null
$volumeQueryExitCode = $LASTEXITCODE
if (
    ($secretQueryExitCode -eq 0 -and $existingPostgresSecret) -or
    ($volumeQueryExitCode -eq 0 -and $existingPostgresVolume)
) {
    $confirmation = Read-Host "PostgreSQL credentials or persistent data already exist. Replacing a Secret alone does not rotate the database password. Have you rotated the database role and verified its PVC? Continue? (yes/no)"
    if ($confirmation -ne "yes") {
        throw "Secret replacement cancelled. Existing cluster state was not changed."
    }
}

$grafanaPassword = Read-SecretValue "Grafana admin password (minimum 16 characters)" 16 -DevelopmentMode:$DevelopmentDefaults

$secrets = @{
    apiVersion = "v1"
    kind = "List"
    items = @(
        @{
            apiVersion = "v1"
            kind = "Secret"
            metadata = @{ name = "postgres-credentials"; namespace = "app" }
            type = "Opaque"
            data = @{
                POSTGRES_USER = (ConvertTo-SecretData "admin")
                POSTGRES_PASSWORD = (ConvertTo-SecretData $postgresPassword)
                POSTGRES_DB = (ConvertTo-SecretData "appdb")
            }
        },
        @{
            apiVersion = "v1"
            kind = "Secret"
            metadata = @{ name = "grafana-admin"; namespace = "app" }
            type = "Opaque"
            data = @{
                username = (ConvertTo-SecretData "admin")
                password = (ConvertTo-SecretData $grafanaPassword)
            }
        },
        @{
            apiVersion = "v1"
            kind = "Secret"
            metadata = @{
                name = "backend-auth"
                namespace = "app"
                labels = @{ environment = $appEnvironment }
            }
            type = "Opaque"
            data = @{
                JWT_SECRET_KEY = (ConvertTo-SecretData $jwtSecret)
                APP_ENV = (ConvertTo-SecretData $appEnvironment)
                AUTH_DEFAULT_USERNAME = (ConvertTo-SecretData $bootstrapUsername)
                AUTH_DEFAULT_PASSWORD = (ConvertTo-SecretData $bootstrapPassword)
            }
        }
    )
} | ConvertTo-Json -Depth 8 -Compress

$secrets | & kubectl apply -f -
if ($LASTEXITCODE -ne 0) {
    throw "Could not apply Kubernetes Secrets. No secret values were written to a file."
}

$postgresPassword = $null
$bootstrapPassword = $null
$grafanaPassword = $null
$jwtSecret = $null
$secrets = $null
Write-Host "PostgreSQL, Grafana and backend JWT Secrets were applied to namespace app."
Write-Host "The Ingress TLS Secret agrotech-tls must be provisioned separately before public exposure."
