## 0.4.5b1

- Add app-owned IEEE 2030.5 identity lifecycle: reuse, safe legacy migration, or one-time generation.
- Verify migrated identity retains the exact same certificate-derived LFDI before use.
- Refuse to overwrite partial/conflicting app-owned identity files.
- Persist non-secret identity status in `/config/certs/identity.json`.
- Allow identity creation/migration and LFDI presentation before `meter_ip` is configured; treat that state as onboarding pending rather than a meter-health failure.
- Classify an explicit TLS client-certificate rejection for a newly generated, never-authenticated identity as possible Launchpad provisioning-pending; keep migrated/previously active identity failures visible as real errors.
- Align certificate validation with the Xcel SDK profile, including self-signed P-256/SHA-256, critical IEEE policy, and critical KeyUsage containing `digitalSignature`.
- Relax imported KeyUsage validation so `digitalSignature` may coexist with other usages, matching the SDK wording.
- Expand ReadingType classification to the SDK's documented v1/v2-compatible and v3 metering types.
- Add Itron list paging using returned `results` counts when the meter returns fewer items than requested.
- Use `Accept: application/sep+xml;level=-S1` for IEEE 2030.5 requests.
- Centralize app version reporting and add CI root/add-on source parity checks.
- Preserve 0.4.4 real-hardware freshness, cached-profile, meter-health, and MQTT outage/recovery behavior.

## 0.4.4b3

- Treat temporary MQTT broker/Supervisor outages as warnings while meter polling continues.
- Clarify meter-poll failures and MQTT disconnect messages, with automatic retry on the next poll.
- Keep Supervisor authentication/configuration HTTP errors visible as errors instead of masking them as temporary MQTT outages.

## 0.4.4b2

- Preserve meter-reported Reading `timePeriod.start` and `duration` as first-class sample metadata.
- Reject Instantaneous Demand older than 120 seconds as stale, retain the meter profile, and avoid publishing stale power as current.
- Keep meters that do not report source timestamps compatible; freshness remains unavailable rather than failing the poll.
- Preserve missing sample duration as unknown and reject meter timestamps more than 5 seconds in the future while tolerating small clock skew.

## 0.4.4b1

- Add temporary real-meter instrumentation for instantaneous-reading timestamp metadata.
- Probe IEEE 2030.5 Reading timePeriod/source timestamp fields before finalizing freshness behavior.
- No user-facing freshness entities are added yet; this prerelease is for hardware validation.

## 0.4.3

### Added

- Added typed meter HTTP failure metadata for transport, HTTP status,
  request path, and cache-invalidation decisions.
- Added regression tests for meter-profile cache behavior.
- Added Meter Health diagnostic with stable `Healthy` and `Problem`
  states.
- Added separate physical-meter availability from application/MQTT
  availability.

### Changed

- Transient meter transport failures now retain the cached meter profile
  instead of forcing full meter rediscovery on the next poll.
- Ordinary timeout and connection-reset failures receive one conservative
  retry where appropriate.
- Cached meter profiles are invalidated when a cached resource returns
  HTTP 404 or 410.
- HTTP 5xx and transient transport failures no longer cause unnecessary
  22-resource meter rediscovery.
- Measurement entities now require both the application and physical
  meter to be available.
- Meter diagnostics remain available when the application is online even
  if the physical meter cannot currently be read.
- Replaced the standalone Last Successful Read entity with Meter Health
  to reduce Home Assistant Activity/logbook noise.
- Existing Last Successful Read MQTT discovery is explicitly removed
  during upgrade.
- Meter Health intentionally uses only `Healthy` and `Problem`; startup,
  restart, and recovery do not publish synthetic transitional states.

### Automation safety

- Meter Health state is retained through MQTT.
- A Home Assistant or app restart does not intentionally publish
  `Problem`.
- Physical-meter failure is represented separately from application
  availability.
- Automations should use explicit transitions such as
  `from: Healthy` / `to: Problem` to avoid treating Home Assistant startup
  states such as unavailable as a real meter failure.

## 0.4.2

### Added

- Added `energy_export_enabled` configuration option.
- Grid-export / Energy Received monitoring can now be disabled for homes
  that do not export electricity.
- Added Client LFDI diagnostic.
- Added Certificate Expiration diagnostic.
- Added Certificate Days Remaining diagnostic.
- Added readable Home Assistant formatting for meter and client LFDIs.

### Changed

- Export-disabled installations now poll only Instantaneous Power and
  Energy Delivered as required core readings.
- Core health becomes 2/2 when export monitoring is disabled and remains
  3/3 when export monitoring is enabled.
- Energy Received is omitted from MQTT state and Home Assistant discovery
  when export monitoring is disabled.
- Existing Energy Received MQTT discovery is explicitly cleaned up when
  export monitoring is disabled.
- Certificate diagnostics reuse the already validated client certificate
  information instead of rereading the certificate.
- Raw LFDI identity values remain unchanged internally; formatting is
  presentation-only.

# Changelog

## 0.4.1

- Added four Home Assistant diagnostic entities to the existing Xcel Energy Smart Meter MQTT device:
  - Last Successful Read
  - Meter LFDI
  - Itron Agent Version
  - Meter Software Version
- Marked these entities with Home Assistant's diagnostic entity category.
- Added a timestamp entity for the locally observed time of the most recent successful validated meter read.
- Extended the retained MQTT state payload with meter identity and version information.
- MQTT discovery logging now reports the actual number of published Home Assistant entities.
- Added regression coverage for the new diagnostic entities and state payload.

## 0.4.0

- Added the first Home Assistant MQTT integration layer.
- Added Home Assistant MQTT device discovery for the three real-meter validated readings:
  - Instantaneous Power
  - Energy Delivered
  - Energy Received
- Added retained availability and state topics.
- Added Home Assistant Supervisor MQTT service discovery so broker credentials do not need to be stored manually in app options.
- Added `mqtt_enabled` as an opt-in setting for the initial 0.4.0 rollout.
- MQTT publishing occurs only after a successful meter poll with all three required core readings.
- Added MQTT runtime and discovery regression coverage.
- Certificate files remain read-only and are never regenerated or modified by the app.

## 0.3.6

- Added one automatic retry for the transient TLS handshake timeout observed during real Xcel/Itron meter discovery.
- The retry remains deliberately conservative: only the first transient handshake failure is retried.
- Existing `BAD_SIGNATURE` retry behavior is preserved.
- Added regression coverage for identifying handshake timeouts without treating normal connection-refused errors as transient handshake failures.

## 0.3.5

- Added reusable meter-profile discovery so the Itron meter layout does not need to be rediscovered on every poll.
- The initial poll still discovers UsagePoint, MeterReading resources, ReadingTypes, and the three validated core reading paths.
- Subsequent successful polls reuse the cached core reading paths and fetch only Instantaneous Demand, Current Summation Delivered, and Current Summation Received.
- The cached meter profile is automatically discarded after a failed poll so the next cycle can rediscover the meter layout.
- Added regression coverage proving that repeated reads with a cached profile do not repeat meter discovery.

## 0.3.4

- Marked Instantaneous Demand, Current Summation Delivered, and Current Summation Received as validated against real Xcel/Itron hardware.
- Added one automatic retry for the transient TLS `BAD_SIGNATURE` condition observed during real-meter testing.
- `RESULT: PASS` now requires all three core meter readings to be available.
- Added connection-health and last-successful-read diagnostics.
- Moved individual MeterReading discovery details and normalized JSON snapshots to DEBUG logging.
- Added a README Mermaid overview of validated and discovered meter capabilities.
- Expanded real-meter documentation and data-provenance guidance.

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
