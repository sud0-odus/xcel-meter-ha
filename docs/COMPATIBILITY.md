# Compatibility Strategy

Xcel Meter HA treats Xcel Energy's Launchpad client SDK as the protocol/reference source while keeping production-meter evidence authoritative when deployed hardware behaves differently from a sample implementation.

## Current compatibility targets

- IEEE 2030.5 mutual TLS on TCP `8081`.
- EC P-256 / secp256r1 self-signed client identity.
- ECDSA/SHA-256 certificate signature.
- Critical Digital Signature KeyUsage and IEEE 2030.5 client policy.
- LFDI = first 20 bytes of SHA-256 over DER certificate, rendered as 40 hexadecimal characters.
- TLS 1.2 with `ECDHE-ECDSA-AES128-CCM8` for the validated production meter/simulator path.
- IEEE media type `application/sep+xml;level=-S1`.
- `/sdev/sdi` meter/device information when available.
- `/upt` dynamic active-electricity UsagePoint discovery.
- paged MeterReading + ReadingType discovery.
- Xcel SDK Itron v1/v2-compatible and v3 ReadingType definitions.
- core Instantaneous Demand and Current Summation Delivered; Current Summation Received when export monitoring is enabled and supported.

## Evidence matrix

| Area | Evidence |
|---|---|
| Production mutual TLS/live reads | Production validated |
| Production meter with missing `softwareVersion` | Production validated |
| v1-compatible reading layout | Xcel SDK secure simulator validated |
| v3 reading layout | Xcel SDK secure simulator validated |
| Paging when list returns fewer items than advertised | Xcel SDK secure simulator validated |
| Native client identity generation | Automated + Xcel SDK secure simulator validated |
| New-identity pending -> active -> revoked -> restored state logic | Xcel SDK secure simulator validated |
| Source freshness with 1-second timestamp metadata | Production validated |
| Missing source timestamp metadata | Xcel SDK simulator validated |
| Physical meter replacement | Not yet validated |
| Real interval-history samples | Not yet validated |

See [`VALIDATION_0.4.5.md`](VALIDATION_0.4.5.md) for the full record.

## Certificate lifecycle

A client certificate is the identity Xcel/Itron authorizes. Regenerating it changes the LFDI and therefore creates a different Launchpad identity.

The app/CLI can compare `expected_lfdi` to the certificate-derived LFDI before relying on meter communication. Existing identities are reused; migration verifies the LFDI is unchanged; first-time generation happens only when no usable identity exists.

An explicit authentication rejection has context:

- newly generated identity that has never authenticated -> may still be provisioning;
- migrated or previously successful identity -> authorization error, not first-time provisioning.

Transport failure, Wi-Fi failure, MQTT failure, or an ordinary restart never justifies silent identity regeneration.

## Itron agent versions

Xcel's supplied SDK materials identify Itron Metering Agent families v1 and v3, with shared v1/v2-compatible ReadingType definitions for older agents.

Xcel Meter HA does not require an authoritative firmware/version string to discover capabilities. If `/sdev/sdi` omits `softwareVersion`, the app reports `unknown` and classifies the advertised ReadingTypes instead.

This is important because the production meter used during development omitted a usable software version while still exposing enough ReadingType metadata for correct discovery.

## Paging and resource availability

The Itron implementation can return fewer list items than requested. Discovery follows the returned `results` count/start offset until the advertised list is inspected.

A resource link also does not guarantee data exists behind it. The secure v3 simulator advertised a Wh interval ReadingSet while the linked ReadingList returned `all="0" results="0"`. Interval history is therefore not promoted merely because the resource is present.

## Failure classification

Keep failure domains separate:

- TLS client-auth / 401 / 403 -> identity/authorization context;
- timeout / connection reset / connection refused -> transport/network context;
- 404 / 410 on cached resource -> possible profile/layout change;
- MQTT broker/Supervisor failure -> downstream publication context;
- stale source timestamp -> data freshness context.

Only the evidence appropriate to that domain should change state. For example, a broker outage does not make a healthy meter unhealthy, and a timeout does not delete an identity.

## Server identity

The secure Xcel simulator's TLS server certificate-derived LFDI matched `/sdev/sdi` exactly during validation. Xcel Meter HA records the meter LFDI but does not yet pin the TLS endpoint to it because physical meter replacement and server-certificate rotation policy have not been established for production deployments.

## Open compatibility/lifecycle questions

- Xcel's authoritative production polling/rate-limit guidance.
- Physical meter replacement: client authorization migration and cumulative counter semantics.
- Certificate renewal/overlap process when a new certificate creates a new LFDI.
- Whether third-party production clients should pin/correlate the TLS server certificate LFDI with `/sdev/sdi`.
- Whether the SDK mDNS subtype/TXT records are a stable production contract across deployed meters.
- Real interval-history availability and semantics.
