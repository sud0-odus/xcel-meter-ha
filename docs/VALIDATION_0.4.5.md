# 0.4.5 Validation Record

This document separates production-hardware evidence, Xcel SDK simulator evidence, and automated-test evidence. A simulator result is not silently promoted to a production-meter claim.

## Production meter - validated 2026-09-28

The 0.4.5b1 candidate completed the following against a provisioned production Xcel/Itron meter:

- GitHub CI passed lint, root/add-on source parity, package/app version parity, and the Python 3.12/3.13/3.14 pytest matrix.
- The legacy `xcel-itron-mqtt` client certificate/key were migrated into Xcel Meter HA app-owned `/config/certs` storage.
- Certificate-derived LFDI remained unchanged during migration.
- The migrated pair passed P-256, SHA-256, key-match, IEEE 2030.5 policy, critical KeyUsage, and self-signed checks.
- The production meter accepted the app-owned identity and returned live readings.
- After restart, Xcel Meter HA reused `Identity source: own` without repeating migration.
- After the legacy add-on was uninstalled, Xcel Meter HA restarted again using only the app-owned identity and continued to pass TLS/IEEE 2030.5, meter health, core readings, and MQTT publication.

Related production evidence from 0.4.4 also remains applicable:

- source `timePeriod.start + duration` freshness handling was exercised with real 1-second meter samples;
- meter/network outage and recovery retained the cached profile;
- Mosquitto outage made Home Assistant entities unavailable while real meter polling remained healthy;
- MQTT publication recovered without restarting Xcel Meter HA.

No production identifiers or private-key material are recorded here.

## Secure Xcel SDK simulator campaign - 0.4.5b2

A disposable Linux/Docker environment was used with Xcel's meter-simulator branch in secure `Production` mode. It was isolated from Home Assistant, the production meter, and production identity.

### Native identity generation

PASS:

- generated P-256 / secp256r1 identity;
- SHA-256 certificate signature;
- Digital Signature key usage present/critical;
- IEEE 2030.5 client policy present/critical;
- self-signed client certificate;
- certificate/key pair matched;
- certificate-derived LFDI printed before any real Launchpad registration.

### Unregistered -> registered authorization

PASS for Agent v1:

- same disposable identity with wrong simulator ACL -> HTTP `403`, non-zero probe;
- exact client LFDI added to ACL -> HTTP `200`;
- negotiated `ECDHE-ECDSA-AES128-CCM8`;
- discovery/read succeeded.

PASS for Agent v3:

- same client identity accepted;
- HTTP `200`;
- same required cipher;
- discovery/read succeeded.

### v1/v3 reading behavior

Agent v1 and v3 both provided the core readings used by the app:

- Instantaneous Demand;
- Current Summation Delivered;
- Current Summation Received.

The simulator Instantaneous Demand sample omitted source timestamp metadata; Xcel Meter HA returned freshness fields as unavailable/null instead of inventing a timestamp.

### Identity overwrite protection

PASS:

- certificate and private-key SHA-256 hashes were recorded;
- a second `cert init` refused to overwrite the existing pair and exited non-zero;
- certificate hash remained identical;
- private-key hash remained identical.

### Expected-LFDI mismatch protection

PASS:

- `cert show` with an intentionally wrong expected LFDI reported `LFDI check: MISMATCH`;
- command exited non-zero.

### Live SDK paging

PASS against Agent v3 with MeterReading list forced to one result per page.

Observed request progression:

```text
/upt/0/mr?l=1
/upt/0/mr?l=1&s=1
/upt/0/mr?l=1&s=2
/upt/0/mr?l=1&s=3
```

Four resources were discovered/classified:

| Description | Classification | ReadingType signature |
|---|---|---|
| Instantaneous Demand | `instantaneous_demand` | `(12,0,1,8,0,38)` |
| Current Summation Delivered | `current_summation_delivered` | `(9,0,1,12,0,72)` |
| Current Summation Received | `current_summation_received` | `(9,0,19,12,0,72)` |
| Wh Interval Delivered | `wh_interval_delivered` | `(4,0,1,12,0,72)` |

This directly exercised the SDK-aligned paging work against the live simulator rather than only fixtures/unit tests.

### Onboarding state machine

A second freshly generated identity was used.

PASS:

1. Identity absent from ACL -> `ONBOARDING_PENDING`; manifest recorded `meter_authenticated: false` and `onboarding_state: register_or_wait_for_provisioning`.
2. Exact same LFDI added -> active read succeeded; manifest changed to `meter_authenticated: true`, `onboarding_state: active`, with a last-authenticated timestamp.
3. ACL removed after prior success -> HTTP `403` surfaced as authorization error, **not** first-time onboarding pending; historical successful-authentication state was retained.
4. Same LFDI restored -> active read succeeded again without generating a new identity; last-authenticated timestamp advanced.

This is the key behavioral distinction between a never-proven fresh identity and a previously working identity that loses authorization.

### Simulator server identity

PASS/OBSERVATION:

- SHA-256-derived LFDI of the TLS server certificate (first 20 bytes) exactly matched the LFDI returned by `/sdev/sdi` in the simulator.

This is not currently enforced/pinned in production because Xcel's meter-replacement/certificate-rotation expectations remain an open lifecycle question.

### v3 interval resource

OBSERVATION:

- `Wh Interval Delivered` was advertised;
- its ReadingSet contained a 43,200-second time period;
- linked ReadingList advertised `all="0"`;
- direct GET returned `all="0" results="0"`.

Conclusion: resource/link presence is not sufficient evidence that interval samples are available. Interval history remains out of scope until actual support/semantics are proven.

## Automated repository gates

CI for the 0.4.5b2 line includes:

- Ruff/lint checks;
- root/add-on `xcel_meter` source parity;
- package/app/runtime version parity;
- pytest on supported Python versions;
- parser/syntax validation for the PowerShell secure-simulator harness.

## Still not proven by 0.4.5 simulator work

- real Xcel provisioning duration/state API;
- production meter Wi-Fi onboarding semantics;
- every deployed Itron firmware/resource layout;
- physical meter replacement and cumulative-counter reset behavior;
- production requirement/recommendation for TLS-server LFDI pinning;
- real interval-history availability;
- certificate renewal/migration policy after the current identity expires.

Those remain vendor questions or future controlled validation items, not assumptions to fill in silently.
