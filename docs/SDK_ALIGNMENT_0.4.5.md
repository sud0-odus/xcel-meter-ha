# 0.4.5 SDK alignment review

This document records the 0.4.5 alignment pass against the Xcel Energy Launchpad materials supplied for development:

- `energy-launchpadsdk-client` main
- `energy-launchpadsdk-cloud` main
- `energy-launchpadsdk-client` meter-simulator feature branch
- the production-meter behavior already validated by `xcel-meter-ha`

The client SDK is the protocol/reference source. Production-meter evidence wins when the sample SDK and the deployed meter behave differently.

## Primary SDK source locations reviewed

- certificate/LFDI implementation: `src/Ieee2030dot5/Ieee20305dot5Authentication/CertificateUtility.cs`
- IEEE 2030.5 HTTP media type/TLS client: `src/Ieee2030dot5/Ieee20305dot5Authentication/Ieee2030dot5HttpClient.cs` and `Ieee20305dot5TlsClient.cs`
- older-agent definitions: `src/Ieee2030dot5/Ieee2030dot5.Itron/ReadingTypes/Utilities/ItronReadingTypeProvider_V1_V2.cs`
- v3 definitions: `src/Ieee2030dot5/Ieee2030dot5.Itron/ReadingTypes/Utilities/ItronReadingTypeProvider_V3.cs`
- list/support behavior: `docs/ItronAgentApiImplementationNotes.md`
- discovery/client usage: `docs/Ieee2030dot5LibrariesUsageGuide.md`
- secure simulator/authentication: `src/AgentSimulator/MeterAgentSimulator/Authentication/`
- mDNS advertisement: `src/AgentSimulator/MeterAgentSimulator/Ieee20305AspNetExtensions/WebApplicationExtensions.cs`


## Changes adopted from the client SDK

### IEEE 2030.5 client identity

`xcel-meter-ha` now validates/generates the same core client profile used by the SDK `CertificateUtility`:

- self-signed client identity
- EC P-256 / `secp256r1`
- ECDSA with SHA-256
- critical KeyUsage containing `digitalSignature`
- critical IEEE 2030.5 self-signed-client certificate policy `1.3.6.1.4.1.40732.2.2`
- LFDI = first 20 octets / 40 hexadecimal characters of SHA-256 over the DER certificate

Import validation no longer requires `digitalSignature` to be the *only* KeyUsage bit. The SDK text says at least `digitalSignature`, with other usages permitted where appropriate.

### Native identity lifecycle

0.4.5 adds app-owned durable identity handling:

1. Reuse a valid app-owned identity if one already exists.
2. With `identity_source: auto`, safely copy a valid legacy `xcel-itron-mqtt` identity into app-owned storage when `migrate_legacy_identity` is enabled.
3. Verify that migration did not change the LFDI.
4. If no identity exists and `generate_identity_if_missing` is enabled, generate one app-owned identity once and keep it.
5. Never overwrite a partial or conflicting app-owned identity.
6. Persist a non-secret `identity.json` status file alongside the certificate files.

A newly generated LFDI must still be registered through Xcel Energy Launchpad. The app retries normally while utility provisioning completes; it does not regenerate an identity because authentication has not started working yet. If the meter explicitly rejects a newly generated, never-authenticated certificate during TLS, the runtime labels that as possible provisioning-pending. Other transport failures are not guessed to be provisioning.

### ReadingType definitions

The classifier now mirrors the SDK's v1/v2-compatible and v3 ReadingType providers for the currently documented Itron metering set, including:

- Instantaneous Demand
- Current Summation Delivered / Received
- VAh Delivered / Received
- VARh Delivered / Received
- Max Demand Delivered / Received
- TOU Wh Delivered / Received
- Wh, VAh, and VARh interval delivered / received, plus Wh net
- Power Factor aggregate and phases A/B/C

TOU Wh and Current Summation Wh share a v3 ReadingType tuple, so the MeterReading description remains necessary to disambiguate them.

### Agent version behavior

The SDK documentation says Xcel has Itron Metering Agent versions 1 and 3 and uses the shared v1/v2 definitions for older agents. `xcel-meter-ha` now labels that family `1.x/2.x`.

Unlike the sample parser, this project intentionally keeps the agent version `unknown` when `/sdev/sdi` omits `softwareVersion`. The real production meter has demonstrated that omission, and ReadingType metadata is sufficient for capability discovery.

### List paging

Itron's implementation notes say an agent may return fewer list items than requested because of device resource limits. MeterReading discovery now advances using the returned `results` count until the list `all` count is satisfied instead of assuming one response contains the complete list.

### IEEE media type

GET requests now use the SDK's IEEE 2030.5 media type:

`Accept: application/sep+xml;level=-S1`

## Intentional differences from SDK samples

### Fresh TLS connection per GET remains

The SDK HTTP implementation demonstrates persistent connections, but the production Xcel/Itron meter used for this project has been most reliable with a fresh TLS connection and `Connection: close` for each GET. 0.4.5 keeps that real-hardware-proven behavior.

### Meter server certificate verification is not tightened yet

The SDK client accepts the meter's self-signed server certificate rather than applying ordinary public-CA hostname validation. `xcel-meter-ha` continues the same model. Whether a client should additionally pin/correlate the server identity is an open Xcel/Itron question.

### mDNS is documented but not enabled in this build

The SDK documents discovery of `upt._sub._smartenergy._tcp.local.` and the simulator advertises Smart Energy TXT records. The current production setup already has a stable meter address. Automatic mDNS discovery is intentionally deferred until we confirm that Xcel expects those records to be a production contract across currently deployed meter generations.

0.4.5b2 does **not** require `meter_ip` merely to generate/migrate and persist the client identity or present its LFDI. A manual/fixed `meter_ip` is required only when local meter validation/polling begins; until then the runtime reports an onboarding-pending state instead of a physical-meter failure.

### Cloud SDK is not inserted into the data path

The cloud SDK is useful as an MQTT publishing reference, but Home Assistant already has a direct local MQTT presentation layer with device discovery, retained state, split app/meter availability, and meter-health semantics. Routing through the cloud SDK would add an unnecessary layer and would not improve the local-first design.

### Simulator feature branch is not treated as a secure production profile as-is

The supplied feature branch is useful for development, but its Docker compose selects `LinuxSwagger`, a mode the SDK documentation describes as disabling certificate authentication. It is therefore suitable for API/resource exploration but not by itself an authoritative mutual-TLS validation harness. 0.4.5b2 now includes and has exercised a secure `Production`-mode simulator path before claiming simulator-based identity authentication coverage.

## Questions still worth asking Xcel / Itron

The SDK answered the basic certificate profile, LFDI derivation, supported ReadingType definitions, simulator existence, and much of the client behavior. The remaining high-value questions are lifecycle/production-contract questions:

1. **Provisioning state:** Is there a documented way to distinguish a newly registered LFDI that is still propagating from an invalid/unregistered LFDI? What failure should a client expect before provisioning completes?
2. **Certificate renewal:** What overlap/renewal process is intended when a new certificate creates a new LFDI? Is there a recommended renewal window?
3. **Polling policy:** The SDK examples demonstrate frequent polling, but what intervals/rate limits does Xcel recommend for production third-party clients?
4. **Physical meter replacement:** Does the customer's existing client authorization migrate to the replacement meter? What should be expected for meter LFDI and cumulative counters?
5. **Server identity:** Beyond the client LFDI ACL, should third-party clients pin or correlate the meter's TLS/server identity with `/sdev/sdi`?
6. **mDNS contract:** Can third-party clients rely on `upt._sub._smartenergy._tcp.local.` and the documented TXT records across Xcel's supported deployed Itron population?
7. **Version metadata:** Should `softwareVersion` be considered optional in production, with ReadingType metadata treated as the compatibility authority when absent?
8. **SDK baseline:** Which branch/tag/release should third-party developers treat as the currently supported reference, especially for the Meter Agent Simulator?

## 0.4.5b2 validation status

Completed on production hardware:

- migrated a working legacy identity and verified the app-owned copy retained the exact LFDI;
- authenticated the migrated identity to the production meter;
- restarted the app and verified the app-owned identity was reused;
- removed the legacy add-on and verified standalone production operation;
- retained the 0.4.4 meter/MQTT outage and freshness behavior.

Completed with the secure Xcel SDK simulator:

- generated disposable native identities and verified certificate/LFDI profile;
- rejected an unregistered LFDI, then accepted the exact same identity after ACL registration;
- validated Agent v1 and v3 secure discovery/read;
- exercised multi-page MeterReading discovery;
- exercised pending -> active -> revoked/error -> restored onboarding history;
- confirmed server-certificate-derived LFDI matched `/sdev/sdi` in the simulator;
- confirmed an advertised v3 interval resource can have an empty ReadingList.

Still intentionally not forced on the production account:

- replacing the already provisioned production identity solely to test a brand-new real Launchpad enrollment.

That remaining real-world onboarding step should be done only when there is a deliberate lifecycle reason or a safe separate meter/account path. The secure simulator already covers the client-side state machine without risking the working production identity.

## 0.4.5b2 simulator/authentication findings

The supplied Meter Agent Simulator documents an intentional difference from a real Itron agent when an LFDI is not registered:

- simulator: HTTP **403 Forbidden** because ASP.NET certificate authentication cannot re-challenge after TLS;
- real Itron agent: SDK notes describe HTTP **401 Unauthorized** for the failed-registration condition.

For a **newly generated identity that has never authenticated successfully**, `xcel-meter-ha` therefore treats TLS client-certificate rejection, HTTP 401, and HTTP 403 as possible provisioning-pending signals. This special classification is deliberately not used for migrated identities or identities that have authenticated before.

The meter-simulator feature branch's development compose file runs `LinuxSwagger`, which its documentation says disables certificate security and is not IEEE 2030.5 compatible. The 0.4.5b2 test harness instead launches the supplied simulator in `Production` over HTTPS and injects the disposable LFDI through .NET configuration environment variables. The SDK source remains external/private and is not copied into this repository.

The harness validates both the v1 and v3 simulator modes because Xcel's SDK materials identify those as the deployed Itron agent families of interest.
