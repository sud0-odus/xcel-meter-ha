# Secure Xcel SDK Meter Agent Simulator validation

This harness validates `xcel-meter-ha` against the **secure** Meter Agent Simulator supplied in the Xcel Energy `energy-launchpadsdk-client` meter-simulator branch.

It deliberately does not use the branch's development `docker-compose.yml` because that compose file sets `ASPNETCORE_ENVIRONMENT=LinuxSwagger`, which the SDK documentation says disables certificate security and is not IEEE 2030.5 compatible. The upstream compose also health-checks `/health`, but the supplied simulator source does not implement that endpoint.

The harness builds the supplied simulator source without copying it into this repository and runs it with:

- `ASPNETCORE_ENVIRONMENT=Production`
- HTTPS on port 8081
- TLS 1.2
- `TLS_ECDHE_ECDSA_WITH_AES_128_CCM_8`
- client certificate authentication
- LFDI ACL authorization

It generates a **disposable** `xcel-meter-ha` identity in the system temporary directory. It never touches the Home Assistant production identity.

## What the test proves

For each requested Itron agent version (v1 and v3 by default), the script:

1. Generates a new P-256/SHA-256 IEEE 2030.5 client identity with the same certificate profile used by `xcel-meter-ha` 0.4.5.
2. Starts the SDK simulator without that LFDI on its ACL.
3. Confirms the simulator rejects `/upt` with HTTP 403. The SDK simulator README explicitly documents this as a simulator limitation; real Itron agents are documented there as using HTTP 401 for failed registration.
4. Restarts the simulator with the exact generated LFDI on its ACL.
5. Confirms secure authentication and negotiation of `ECDHE-ECDSA-AES128-CCM8`.
6. Runs `xcel-meter read` to exercise discovery/classification and core readings.
7. Repeats the secure discovery/read test for v1 and v3.

The private key exists only in a temporary directory and is deleted when the script completes unless `-KeepWork` is supplied.

## Requirements

- Docker Desktop (or Docker Engine reachable from PowerShell)
- a local checkout/extraction of the supplied Xcel `energy-launchpadsdk-client` meter-simulator branch
- this `xcel-meter-ha` repository checkout

No local Python or pytest installation is required; the test client runs in Docker.

## Run from PowerShell

From the `xcel-meter-ha` repository root:

```powershell
.\tools\simulator\run-secure-simulator.ps1 `
  -SdkRoot "C:\path\to\energy-launchpadsdk-client-feature-meter-simulator"
```

If the path already points to the SDK's `launchpad` folder, that is accepted too.

To retain the disposable certificate files for manual inspection:

```powershell
.\tools\simulator\run-secure-simulator.ps1 `
  -SdkRoot "C:\path\to\energy-launchpadsdk-client-feature-meter-simulator" `
  -KeepWork
```

Do not register the disposable test LFDI in Xcel Energy Launchpad. It is only for the local SDK simulator.
