# Secure Xcel SDK Meter Simulator validation

This directory contains the automated client-side harness for validating Xcel Meter HA against the **secure** Meter Agent Simulator supplied in Xcel's `energy-launchpadsdk-client` meter-simulator branch.

The simulator must be run in `Production` mode for certificate-authenticated IEEE 2030.5 testing. Do not use a development/Swagger configuration that disables certificate security and then treat the result as a secure interoperability test.

## Automated PowerShell path

`run-secure-simulator.ps1`:

1. builds the local Xcel Meter HA client image;
2. generates a disposable P-256/SHA-256 IEEE 2030.5 identity;
3. proves a second identity initialization is blocked and leaves both certificate/key hashes unchanged;
4. proves an intentionally wrong expected LFDI returns the explicit mismatch failure;
5. builds the supplied Xcel simulator source;
6. starts a secure simulator without that LFDI and expects HTTP `403`;
7. restarts with the exact generated LFDI on the ACL;
8. requires `ECDHE-ECDSA-AES128-CCM8`;
9. runs secure discovery/read against requested Agent v1/v3 variants.

Run from the repository root:

```powershell
.\tools\simulator\run-secure-simulator.ps1 `
  -SdkRoot "C:\path\to\energy-launchpadsdk-client-feature-meter-simulator"
```

Use `-KeepWork` only when you intentionally want to inspect the disposable identity after the run.

## Linux/manual path

For Docker Engine/Linux hosts, including an isolated internal-network workflow and the extended regression cases first exercised during the 0.4.5b2 campaign, see:

[`../../docs/TESTING_WITH_XCEL_SDK_SIMULATOR.md`](../../docs/TESTING_WITH_XCEL_SDK_SIMULATOR.md)

## Safety

- Never mount the Home Assistant production certificate into the simulator.
- Never register a disposable simulator LFDI in the real Launchpad portal.
- Keep SDK source outside this public repository.
- A simulator pass is not a claim about Xcel's real provisioning time, meter Wi-Fi behavior, or every field firmware version.
