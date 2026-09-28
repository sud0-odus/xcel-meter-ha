# Milestone 2: live meter discovery and core readings

> **Historical milestone document.** This file records an earlier implementation stage and is retained for project history. For current installation and behavior, use the root `README.md`, `docs/GETTING_STARTED.md`, and `docs/VALIDATION_0.4.5.md`.


This milestone moves beyond TLS diagnostics and implements the minimum useful vertical slice
against the Xcel Energy Launchpad / Itron IEEE 2030.5 interface.

## Implemented

- Reuse an existing certificate identity; support both `cert.pem/key.pem` (HA add-on) and
  `.cert.pem/.key.pem` (upstream container) naming.
- Optional expected/Launchpad LFDI comparison before any meter connection.
- TLS 1.2 + `ECDHE-ECDSA-AES128-CCM8` HTTP client.
- `/sdev/sdi` DeviceInformation query and Itron agent-version detection.
- `/upt` active electricity UsagePoint discovery.
- Dynamic MeterReadingList and ReadingType discovery.
- Official Xcel SDK reading-type classification for Itron agent v2/v3 core readings.
- Itron v3 TOU-vs-summation description disambiguation.
- Core reads:
  - instantaneous demand (W)
  - current summation delivered (Wh)
  - current summation received (Wh)
- `powerOfTenMultiplier` scaling.
- JSON output designed to become the MQTT normalization boundary in Milestone 3.

## Real-meter test

Use a COPY of your existing cert/key directory. Never regenerate a working identity just to test.

```bash
xcel-meter read \
  --host 192.0.2.10 \
  --port 8081 \
  --dir ./certs \
  --expected-lfdi YOUR_REGISTERED_CLIENT_LFDI \
  --pretty
```

The command first validates the local certificate and refuses to connect when the expected LFDI
and certificate-derived LFDI differ.

## Not implemented yet

- MQTT publishing / Home Assistant discovery
- interval reading paging
- TOU tier values
- reconnect service loop
- Home Assistant add-on image and configuration UI

Those are intentionally after the direct meter read is verified on real hardware.

## Extracting the current HA add-on identity for a one-time live test

A Home Assistant partial backup of the existing Xcel add-on can be used without generating a new
identity. The repository includes a standard-library-only helper that extracts only `cert.pem` and
`key.pem` from that backup:

```bash
python scripts/extract_ha_identity.py xcel_cert_snapshot.tar --out ./certs
```

Keep the resulting `certs` directory private and delete the copy after the live validation if it is
no longer needed. The original Home Assistant add-on identity is not modified.
