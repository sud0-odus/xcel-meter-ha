# xcel-meter-ha

A maintained, local-first Xcel Energy / Itron IEEE 2030.5 smart-meter bridge for Home Assistant.

The project is validated against a production Xcel/Itron meter and uses the Xcel Energy Launchpad client SDK as the protocol/reference implementation for certificate identity, Itron ReadingType semantics, and meter behavior.

## Status: 0.4.5b1 native identity + SDK alignment candidate

0.4.4 completed the production-meter freshness and MQTT outage/recovery work. 0.4.5b1 is the first larger native-onboarding candidate.

Current capabilities include:

- IEEE 2030.5 P-256 client identity generation and inspection
- certificate-derived LFDI and Launchpad LFDI mismatch protection
- safe one-time migration of the existing legacy `xcel-itron-mqtt` identity into this app's own persistent storage
- one-time generation of a durable app-owned identity when no identity exists
- TLS 1.2 / `ECDHE-ECDSA-AES128-CCM8` meter connectivity
- dynamic active electricity UsagePoint and MeterReading discovery
- SDK-aligned Itron v1/v2-compatible and v3 ReadingType classification
- SDK-aligned paging when a meter returns fewer list items than requested
- Instantaneous Demand and cumulative Energy Delivered; Energy Received is optional
- source timestamp freshness protection without fabricating `0 W` on stale/lost data
- cached meter profile with conservative invalidation
- Home Assistant MQTT device discovery, state, availability, diagnostics, and stable Meter Health
- MQTT outage isolation: broker failure does not redefine meter health

See [`docs/SDK_ALIGNMENT_0.4.5.md`](docs/SDK_ALIGNMENT_0.4.5.md) for the source-by-source alignment review and remaining Xcel/Itron questions.

## Identity safety is the first rule

A Launchpad client certificate is durable identity. A new certificate creates a new LFDI and requires utility provisioning.

`identity_source: auto` now follows this order:

1. Reuse an existing app-owned identity.
2. If configured, migrate a valid legacy identity into app-owned `/config/certs` storage and verify the LFDI is unchanged.
3. If no identity exists and generation is enabled, generate one identity once and display its LFDI for Launchpad registration.

The app refuses to overwrite an incomplete/conflicting app-owned identity and never regenerates identity because of meter, Wi-Fi, MQTT, Home Assistant, or provisioning failures.

A non-secret `/config/certs/identity.json` records the LFDI, certificate expiration, origin, and last successful meter authentication. The private key is never written to that status file or logs.

## Home Assistant app

The Home Assistant app remains under `xcel-meter-diagnostic/` for upgrade compatibility; its displayed name is now **Xcel Meter HA**.

Recommended 0.4.5b1 options for an existing installation:

```yaml
meter_ip: 192.168.1.122
meter_port: 8081
expected_lfdi: YOUR_EXISTING_LAUNCHPAD_LFDI
identity_source: auto
migrate_legacy_identity: true
generate_identity_if_missing: true
legacy_addon_slug: ""
timeout: 8
poll_interval: 60
log_level: INFO
mqtt_enabled: true
energy_export_enabled: false
```

For an existing user, the first 0.4.5b1 hardware validation should confirm a log similar to:

```text
Legacy identity safely migrated into app-owned storage with unchanged LFDI: ...
Identity source: own
Certificate-derived LFDI: ...
Expected/Launchpad LFDI: ...
LFDI validation: MATCH
TLS/IEEE 2030.5 connection: PASS
Connection health: HEALTHY
RESULT: PASS
MQTT state published: ...
```

Once that succeeds across a restart, the old add-on is no longer the active identity store and can be removed after the user confirms the new app continues to authenticate.

## New-install onboarding

If no existing identity is found, 0.4.5b1 can generate an app-owned identity once. A `meter_ip` is not required just to create/persist the identity: the log prints the LFDI first so the user can register it in Xcel Energy Launchpad, then reports onboarding as pending until the meter address is configured.

Once `meter_ip` is configured, the app keeps that same identity and retries normally while provisioning completes. Missing meter configuration is treated as an onboarding state rather than a physical-meter health failure. An explicit TLS client-certificate rejection is also treated as possible provisioning-pending only for a newly generated identity that has never authenticated successfully; the identity is never replaced automatically.

There is intentionally no generic **Regenerate** workflow. Replacing a provisioned identity should be a deliberate, warned operation because it changes the LFDI.

## Real-meter validation already completed

- mutual TLS against a production Xcel/Itron meter
- certificate/LFDI validation
- active electricity UsagePoint discovery
- 22 MeterReading resources observed
- Instantaneous Demand
- Current Summation Delivered
- Current Summation Received when export monitoring is enabled
- one-second source metadata observed on the production meter
- stale sample rejection while keeping timestamp-less meters compatible
- meter/Wi-Fi outage detection and automatic recovery
- cached profile retention across transient transport failure
- Home Assistant/app restart behavior without false Meter Health problems
- Mosquitto outage: HA entities unavailable while meter polling remains HEALTHY/PASS
- Mosquitto recovery without restarting Xcel Meter HA

## SDK alignment highlights

The 0.4.5 pass incorporates the useful behavior already provided by the official client SDK rather than rebuilding it indirectly:

- official certificate/LFDI profile
- full documented Itron ReadingType signature catalog used for discovery
- v1/v2-compatible versus v3 reading providers
- list paging using returned `results`
- IEEE media type `application/sep+xml;level=-S1`

Intentional production-meter-driven differences are documented in `docs/SDK_ALIGNMENT_0.4.5.md`.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

CI tests Python 3.12, 3.13, and 3.14 and also verifies that the root package and Home Assistant app package contain identical `xcel_meter` source trees.

## Security

- Never commit or log the private key.
- Never delete/regenerate identity as a generic troubleshooting step.
- Persist identity before registering its LFDI with Launchpad.
- Validate migrated identity before removing the legacy add-on.
- Treat certificate renewal as a lifecycle event requiring a new LFDI unless Xcel documents another mechanism.
- Keep the meter interaction read-only.

## Project direction after 0.4.5

- production validation of native migration/generation
- meter replacement/counter-reset safeguards
- optional mDNS discovery after confirming Xcel's production contract
- sanitized firmware fixtures and simulator-backed regression coverage
- optional advanced diagnostics
- interval history only after its semantics and support are proven
- tariffs/rates as a later layer, separate from the transport core
