[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SdkRoot,

    [ValidateSet(1, 3)]
    [int[]]$AgentVersion = @(1, 3),

    [int]$HostPort = 8081,

    [switch]$KeepWork
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Remove-SimulatorContainer {
    param([string]$Name)
    & docker rm -f $Name *> $null
}

function Invoke-Client {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    $output = & docker run --rm `
        --add-host "host.docker.internal:host-gateway" `
        -v "${script:CertDir}:/certs:ro" `
        $script:ClientImage @Arguments 2>&1
    $code = $LASTEXITCODE
    return [pscustomobject]@{ Code = $code; Output = @($output) }
}

function Get-IdentityHashes {
    $python = 'import hashlib,pathlib; [print(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest(), p) for p in ("/certs/.cert.pem", "/certs/.key.pem")]'
    $output = & docker run --rm `
        -v "${script:CertDir}:/certs:ro" `
        --entrypoint python `
        $script:ClientImage -c $python 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to hash the disposable identity: $($output -join [Environment]::NewLine)"
    }
    return @($output | ForEach-Object { "$_" })
}

function Wait-For-Simulator {
    param([int]$Version)

    for ($attempt = 1; $attempt -le 30; $attempt++) {
        $probe = Invoke-Client probe --host host.docker.internal --port $script:HostPort `
            --dir /certs --path /dcap --timeout 2
        if ($probe.Code -eq 0) {
            Write-Host "Simulator v$Version is accepting secure IEEE 2030.5 connections."
            return
        }
        Start-Sleep -Seconds 1
    }

    & docker logs $script:ContainerName
    throw "Simulator v$Version did not become ready on port $script:HostPort."
}

function Start-Simulator {
    param(
        [int]$Version,
        [string]$AllowedLfdi
    )

    Remove-SimulatorContainer $script:ContainerName

    Invoke-Docker run -d `
        --name $script:ContainerName `
        -p "${script:HostPort}:8081" `
        -e "ASPNETCORE_ENVIRONMENT=Production" `
        -e "ASPNETCORE_URLS=https://+:8081" `
        -e "ItronAgentVersion=$Version" `
        -e "LFDIs__0=$AllowedLfdi" `
        $script:SimulatorImage | Out-Null

    Wait-For-Simulator $Version
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required for the secure Xcel SDK simulator test."
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$ResolvedSdkRoot = (Resolve-Path $SdkRoot).Path

if (Test-Path (Join-Path $ResolvedSdkRoot "launchpad\Dockerfile")) {
    $LaunchpadRoot = Join-Path $ResolvedSdkRoot "launchpad"
} elseif (Test-Path (Join-Path $ResolvedSdkRoot "Dockerfile")) {
    $LaunchpadRoot = $ResolvedSdkRoot
} else {
    throw "SdkRoot must point to the Xcel energy-launchpadsdk-client checkout or its launchpad folder."
}

$script:HostPort = $HostPort
$script:ClientImage = "xcel-meter-ha-sim-client:0.4.5b3"
$script:SimulatorImage = "xcel-launchpad-meter-simulator:local"
$script:ContainerName = "xcel-meter-sdk-simulator-secure"
$WorkRoot = Join-Path $env:TEMP ("xcel-meter-ha-simulator-" + [guid]::NewGuid().ToString("N"))
$script:CertDir = Join-Path $WorkRoot "certs"
New-Item -ItemType Directory -Force -Path $script:CertDir | Out-Null

try {
    Write-Host "Building disposable xcel-meter-ha client image..."
    Invoke-Docker build -t $script:ClientImage -f (Join-Path $ScriptDir "Dockerfile.client") $ProjectRoot

    Write-Host "Generating a disposable SDK-aligned IEEE 2030.5 identity..."
    $identityOutput = & docker run --rm -v "${script:CertDir}:/certs" `
        $script:ClientImage cert init --dir /certs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Disposable identity generation failed: $($identityOutput -join [Environment]::NewLine)"
    }
    $identityOutput | ForEach-Object { Write-Host $_ }

    $lfdiMatch = $identityOutput | Select-String -Pattern '^LFDI:\s*([0-9A-Fa-f]{40})\s*$' | Select-Object -First 1
    if (-not $lfdiMatch) {
        throw "Could not parse the generated LFDI."
    }
    $Lfdi = $lfdiMatch.Matches[0].Groups[1].Value.ToUpperInvariant()
    Write-Host "Disposable client LFDI: $Lfdi"

    Write-Host "Verifying that identity initialization cannot overwrite the generated certificate/key..."
    $beforeHashes = Get-IdentityHashes
    $regenerationOutput = & docker run --rm -v "${script:CertDir}:/certs" `
        $script:ClientImage cert init --dir /certs 2>&1
    $regenerationCode = $LASTEXITCODE
    $regenerationOutput | ForEach-Object { Write-Host $_ }
    if ($regenerationCode -eq 0) {
        throw "Identity regeneration unexpectedly succeeded over an existing certificate/key pair."
    }
    $afterHashes = Get-IdentityHashes
    if (($beforeHashes -join "`n") -ne ($afterHashes -join "`n")) {
        throw "Disposable certificate/key bytes changed after a blocked regeneration attempt."
    }
    Write-Host "PASS: blocked regeneration left both identity files byte-for-byte unchanged."

    $WrongLfdi = "0000000000000000000000000000000000000000"
    if ($WrongLfdi -eq $Lfdi) {
        $WrongLfdi = "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
    }
    $mismatch = Invoke-Client cert show --dir /certs --expected-lfdi $WrongLfdi
    $mismatch.Output | ForEach-Object { Write-Host $_ }
    $mismatchText = $mismatch.Output -join "`n"
    if ($mismatch.Code -eq 0 -or $mismatchText -notmatch 'LFDI check: MISMATCH') {
        throw "Expected-LFDI mismatch guard did not fail as expected."
    }
    Write-Host "PASS: expected-LFDI mismatch is detected before meter testing."

    Write-Host "Building the Xcel SDK Meter Agent Simulator from the supplied SDK checkout..."
    Invoke-Docker build -t $script:SimulatorImage -f (Join-Path $LaunchpadRoot "Dockerfile") $LaunchpadRoot

    foreach ($version in $AgentVersion) {
        Write-Host ""
        Write-Host "=== Xcel SDK secure simulator: Agent v$version ==="

        # The SDK simulator intentionally returns HTTP 403 for an unregistered LFDI.
        # Its own README notes that real agents use 401 for this condition.
        Write-Host "Starting simulator with the disposable LFDI intentionally NOT registered..."
        Start-Simulator -Version $version -AllowedLfdi $WrongLfdi

        $denied = Invoke-Client probe --host host.docker.internal --port $script:HostPort `
            --dir /certs --path /upt --timeout 8
        $denied.Output | ForEach-Object { Write-Host $_ }
        $deniedText = $denied.Output -join "`n"
        if ($denied.Code -eq 0 -or $deniedText -notmatch 'HTTP 403') {
            throw "Expected the SDK simulator to reject the unregistered LFDI with HTTP 403."
        }
        Write-Host "PASS: unregistered LFDI was rejected with the SDK simulator's documented HTTP 403 behavior."

        Write-Host "Restarting simulator with the exact generated LFDI on its ACL..."
        Start-Simulator -Version $version -AllowedLfdi $Lfdi

        $authorized = Invoke-Client probe --host host.docker.internal --port $script:HostPort `
            --dir /certs --path /upt --timeout 8
        $authorized.Output | ForEach-Object { Write-Host $_ }
        if ($authorized.Code -ne 0) {
            throw "Authorized secure probe failed for Agent v$version."
        }
        $authorizedText = $authorized.Output -join "`n"
        if ($authorizedText -notmatch 'ECDHE-ECDSA-AES128-CCM8') {
            throw "Secure probe did not negotiate ECDHE-ECDSA-AES128-CCM8."
        }

        $reading = Invoke-Client read --host host.docker.internal --port $script:HostPort `
            --dir /certs --timeout 8 --pretty
        $reading.Output | ForEach-Object { Write-Host $_ }
        if ($reading.Code -ne 0) {
            throw "SDK simulator discovery/read failed for Agent v$version."
        }

        Write-Host "PASS: generated identity authenticated and xcel-meter-ha discovered/read Agent v$version over secure IEEE 2030.5."
        Remove-SimulatorContainer $script:ContainerName
    }

    Write-Host ""
    Write-Host "SECURE XCEL SDK SIMULATOR RESULT: PASS"
    Write-Host "Identity overwrite and expected-LFDI mismatch protections passed."
    Write-Host "The disposable identity was rejected before ACL registration and accepted afterward."
    Write-Host "Both requested Itron agent versions completed secure discovery/read validation."
}
finally {
    Remove-SimulatorContainer $script:ContainerName
    if ($KeepWork) {
        Write-Host "Disposable simulator work retained at: $WorkRoot"
    } else {
        Remove-Item -Recurse -Force $WorkRoot -ErrorAction SilentlyContinue
    }
}
