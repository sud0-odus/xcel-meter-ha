# Changelog

## 0.3.3

- Added support for real-world Itron ReadingType responses where `phase` may be omitted instead of explicitly reported as `0`.
- Meter software/agent version is now reported as `unknown` when `/sdev/sdi` does not provide enough information instead of silently assuming version 2.
- Added real-meter regression tests for Instantaneous Demand, Current Summation Delivered, and Current Summation Received.
- Real-meter discovery identified 22 MeterReading resources, including:
  - Instantaneous Demand
  - Current Summation Delivered / Received
  - TOU WH Delivered / Received
  - WH Interval Delivered / Received / Net
  - VAh Delivered / Received and interval variants
  - VARh Delivered / Received and interval variants
  - Max Demand Delivered / Received
  - Power Factor overall and Phase A / B / C
- Added `docs/discovered-meter-readings.md` with technical descriptions, user-friendly descriptions, illustrative examples, provenance notes, and potential Home Assistant uses.

## 0.3.2

- Added detailed MeterReading discovery diagnostics for real Itron meters.
- Logs advertised and parsed reading counts, ReadingType tuples, links, and classifications.
- Does not log certificate private key material or raw sensitive identity files.

## 0.3.1

- Added compatibility for Itron meters requiring legacy TLS server renegotiation support with modern OpenSSL.
- Retains TLS 1.2 and the IEEE 2030.5 cipher configuration.

## 0.3.0

- First Home Assistant-native diagnostic app.
- Read-only discovery of legacy Xcel iTron MQTT app identity.
- Certificate-derived LFDI validation.
- Direct IEEE 2030.5 meter discovery and core reading validation.
- No MQTT publishing and no certificate mutation.


