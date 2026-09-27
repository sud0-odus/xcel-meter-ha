# Upstream Issue Review

Last reviewed: 2026-09-27

This document records issues, implementation lessons, and compatibility
concerns discovered while reviewing the projects that preceded
`xcel-meter-ha`.

The goal is not to copy upstream behavior blindly. Instead, each issue is
evaluated against:

- behavior observed on a real Xcel Energy / Itron meter;
- the current `xcel-meter-ha` architecture;
- Home Assistant requirements;
- data provenance and identity safety;
- whether the upstream workaround is appropriate for this project.

## Upstream projects reviewed

- wingrunr21/hassio-xcel-itron-mqtt
  https://github.com/wingrunr21/hassio-xcel-itron-mqtt

- zaknye/xcel_itron2mqtt
  https://github.com/zaknye/xcel_itron2mqtt

These projects were important references for this implementation, but
`xcel-meter-ha` contains its own IEEE 2030.5 protocol, discovery, retry,
caching, MQTT, and Home Assistant logic.

## Status terminology

| Status | Meaning |
|---|---|
| COVERED | Current implementation already addresses the concern. |
| PARTIAL | Some protections exist, but additional work is justified. |
| PLANNED | The upstream report identifies useful work we intend to add. |
| INVESTIGATE | More real-meter or protocol evidence is required first. |
| NOT ADOPTED | The upstream workaround conflicts with this project's design or trust model. |
| REVERIFY | The upstream report was noted during review but its details should be rechecked before implementation. |

## Issue review

### wingrunr21 #28 - Read timed out

Source:

https://github.com/wingrunr21/hassio-xcel-itron-mqtt/issues/28

Status: PARTIAL

Upstream concern:

Users have reported meter HTTP/TLS requests timing out even after the
meter has been successfully enrolled and is reachable.

Relevant behavior observed during `xcel-meter-ha` development:

- TLS `BAD_SIGNATURE` was observed transiently.
- A TLS handshake timeout was observed during full MeterReading discovery.
- A later retry succeeded without changing the certificate or meter.
- Normal cached polling is dramatically lighter than full discovery.

Current protection:

- one retry for transient `BAD_SIGNATURE`;
- one retry for the observed TLS handshake timeout;
- configurable request timeout;
- serialized polling;
- 60 second default polling;
- cached meter profile dramatically reduces routine requests.

Remaining work:

1. Classify ordinary response/read timeouts separately from permanent
   connection failures.
2. Consider one conservative retry for a normal response timeout.
3. Record retry reason and failure counts for Home Assistant diagnostics.
4. Avoid causing additional meter load while recovering.

Design rule:

Transient communication failures must never trigger certificate regeneration.

---

### wingrunr21 #39 - Showing Demand during Power Outage

Source:

https://github.com/wingrunr21/hassio-xcel-itron-mqtt/issues/39

Status: PLANNED / INVESTIGATE

Upstream concern:

A user reported Instantaneous Demand continuing to show a nearly constant
positive value during a utility outage.

We should not assume that this means the correct value is zero.

Possible explanations include:

- an old/stale reading still being served;
- meter-side semantics during an outage;
- meter power supplied independently of grid service;
- interaction with batteries or distributed generation;
- another IEEE 2030.5 behavior not yet characterized.

Planned approach:

1. Inspect the real Instantaneous Demand XML for meter-provided timestamp
   information.
2. Capture the source measurement timestamp when available.
3. Add diagnostics such as:
   - Meter Sample Time
   - Meter Sample Age
   - Reading Stale
4. Keep Last Successful Poll separate from Meter Sample Time.

Important distinction:

A successful network request proves that communication is current.

It does NOT prove that the measurement returned by the meter is current.

We should never silently replace a meter-reported power value with zero
without authoritative evidence.

---

### wingrunr21 #41 - Itron firmware 3.2.50 support

Source:

https://github.com/wingrunr21/hassio-xcel-itron-mqtt/issues/41

Status: COVERED BY ARCHITECTURE / TESTS PLANNED

Upstream concern:

Firmware 3.2.50 required changes to the underlying meter implementation and
endpoint handling.

Current `xcel-meter-ha` design intentionally avoids making firmware version
the primary routing mechanism.

Current discovery flow:

Meter
  -> Device Information
  -> active electricity UsagePoint
  -> MeterReadingListLink
  -> advertised MeterReading resources
  -> ReadingType resources
  -> classify available readings

This has already allowed a real meter to work even though the meter does not
expose a usable softwareVersion.

Current behavior:

- missing softwareVersion becomes `unknown`;
- it is never silently treated as firmware 2.x;
- ReadingType evidence is used to identify supported readings.

Remaining work:

Add regression fixtures representing known firmware layouts, including:

- 2.x style ReadingTypes;
- current real-meter / unknown-version behavior;
- 3.2.50 style resources.

Suggested compatibility table:

| Meter profile | Test status |
|---|---|
| Real meter, version unavailable | Real-hardware validated |
| Agent 2.x ReadingType pattern | Fixture tested |
| Agent 3.x ReadingType pattern | Fixture tested |
| Firmware 3.2.50 layout | Planned fixture |
| Unknown future firmware | Dynamic discovery fallback |

---

### wingrunr21 #36 - Supervisor MQTT service unavailable

Source:

https://github.com/wingrunr21/hassio-xcel-itron-mqtt/issues/36

Status: COVERED

Upstream concern:

When the Home Assistant Supervisor MQTT service was unavailable, an empty
MQTT host reached the MQTT library and caused the add-on to crash with an
invalid-host error.

Current `xcel-meter-ha` behavior:

- Supervisor MQTT service information is validated before use;
- an empty or unavailable broker is rejected explicitly;
- MQTT initialization failure does not invalidate meter communication;
- MQTT publishing is isolated from meter polling;
- MQTT is opt-in during the early 0.4.x rollout.

Future enhancement:

Support an optional manually configured external MQTT broker when Supervisor
MQTT is unavailable.

Preferred future order:

1. Home Assistant Supervisor MQTT service
2. explicitly configured external MQTT broker
3. MQTT disabled with clear diagnostics

---

### zaknye - repeated timeout / BAD_SIGNATURE behavior

Source repository:

https://github.com/zaknye/xcel_itron2mqtt/issues

Status: REVERIFY / PARTIAL

A previously reviewed upstream report described frequent meter request
timeouts together with occasional TLS `BAD_SIGNATURE` errors while useful
meter data could still be retrieved.

The exact upstream issue details should be re-verified before using them as
the basis for a specific compatibility claim.

The general failure pattern is independently relevant because
`xcel-meter-ha` has observed both:

- transient `BAD_SIGNATURE`;
- transient TLS handshake timeout.

Current protection:

- one retry for `BAD_SIGNATURE`;
- one retry for the observed handshake timeout;
- cached core-reading paths;
- 60 second default poll interval.

Important remaining improvement:

The current runtime clears the cached MeterProfile after a failed poll.

That is appropriate if the layout is actually invalid, but undesirable for a
single transient communication failure because the next cycle performs a full
rediscovery and places more load on the meter.

Planned improvement:

Differentiate transient transport failure from profile/layout failure.

Suggested behavior:

Transient transport failure
  -> retry request once
  -> if still unsuccessful, mark current poll failed
  -> publish unavailable/offline if appropriate
  -> KEEP cached MeterProfile
  -> retry the same three known endpoints next cycle

Profile/layout failure
  -> invalidate cached MeterProfile
  -> rediscover UsagePoint and MeterReadings next cycle

Possible reasons to invalidate the profile:

- expected endpoint returns HTTP 404 or equivalent;
- ReadingType/resource has disappeared;
- UsagePoint is no longer available;
- repeated failures exceed a conservative threshold;
- explicit meter restart/layout-change evidence exists.

---

## Certificate identity lessons

Status: COVERED / INTENTIONAL DESIGN DIFFERENCE

Some predecessor troubleshooting guidance has treated deletion and
regeneration of certificate files as a recovery step.

`xcel-meter-ha` deliberately does not use that model once an identity has
been provisioned with Xcel Launchpad.

Project rule:

A provisioned client certificate is identity, not disposable configuration.

Current behavior:

- derive the client LFDI from the actual certificate;
- validate certificate/key match;
- validate IEEE 2030.5 certificate policy;
- validate EC P-256 curve;
- validate digital-signature usage;
- compare certificate-derived LFDI to the configured/Launchpad LFDI;
- warn before expiration;
- never silently regenerate identity.

If identity does not match Launchpad, the correct action is to determine
which identity should be provisioned or restored.

Generating a new certificate creates a new identity and therefore requires
new Launchpad provisioning.

---

## MQTT architecture lessons

Status: MOSTLY COVERED

Current implementation already provides:

- Supervisor MQTT service discovery;
- validated broker configuration;
- one MQTT device representing the physical meter;
- Home Assistant device discovery;
- retained discovery;
- retained state;
- retained availability;
- Last Will offline availability;
- MQTT failures isolated from IEEE 2030.5 meter polling.

Planned:

- optional external/manual MQTT broker;
- expose MQTT connection health as a diagnostic entity;
- expose last MQTT publish time;
- expose MQTT reconnect/failure count.

---

## Polling and meter-load lessons

Status: COVERED / CONTINUE MONITORING

Initial implementation performed full meter discovery every poll.

Real-hardware timing showed that full discovery could take roughly 10-20
seconds because every advertised ReadingType required another TLS request.

The meter advertises 22 MeterReading resources.

Current optimized behavior:

Startup
  -> discover meter layout
  -> identify three validated core reading paths
  -> cache MeterProfile

Routine poll
  -> Instantaneous Demand
  -> Current Summation Delivered
  -> Current Summation Received

Observed cached polling completes much faster than initial discovery.

This reduces:

- TLS handshakes;
- load on the Itron meter;
- probability of transient failures;
- latency before MQTT publication.

---

## Data provenance rules

Upstream issue review reinforces the project's existing data trust model.

Preferred order:

1. Meter-reported facts
2. Utility-provided facts
3. Locally derived values

Examples:

Meter-reported:
- Instantaneous Demand
- Current Summation Delivered
- Current Summation Received
- meter LFDI

Locally observed:
- Last Successful Read
- poll duration
- connection health
- retry count

Derived:
- rate calculations
- bill estimates
- stale-reading flags
- net calculations when not directly supplied

Derived or locally observed values must never be presented as though the
meter itself reported them.

---

## Prioritized engineering backlog from upstream review

### P1 - transient communication resilience

- distinguish transport failures from meter-profile failures;
- preserve cached MeterProfile after isolated transient failures;
- add ordinary read-timeout handling;
- expose consecutive failure count;
- expose last meter error;
- expose last retry reason;
- expose poll duration.

### P1 - measurement freshness

- inspect real Reading XML for source timestamps;
- parse source timestamp when present;
- expose Meter Sample Time;
- expose Meter Sample Age;
- expose Reading Stale;
- document outage behavior.

### P2 - firmware compatibility

- add 3.2.50 fixture;
- maintain 2.x fixture;
- maintain 3.x fixture;
- maintain real-meter/unknown-version fixture;
- document compatibility based on evidence rather than assumptions.

### P2 - MQTT resilience

- optional external broker configuration;
- MQTT connection diagnostic;
- last MQTT publish diagnostic;
- MQTT failure/reconnect counters.

### P3 - expanded readings

Only after reliability/freshness work is stable:

- TOU Wh Delivered / Received;
- interval Wh Delivered / Received / Net;
- Maximum Demand;
- Power Factor;
- VAh;
- VARh.

---

## Issues we should not solve by guessing

The following should require protocol evidence or real-meter validation before
production behavior is changed:

- forcing Instantaneous Demand to zero during an outage;
- assuming meter firmware based on missing softwareVersion;
- regenerating a certificate after TLS authentication failure;
- treating all timeouts as evidence that meter discovery is invalid;
- inferring unsupported meter readings only from their descriptions.

---

## Review process

Periodically review both upstream issue trackers for newly discovered meter
behavior:

https://github.com/wingrunr21/hassio-xcel-itron-mqtt/issues?q=is%3Aissue

https://github.com/zaknye/xcel_itron2mqtt/issues?q=is%3Aissue

For each useful report:

1. record the upstream issue;
2. determine whether it reproduces against current architecture;
3. distinguish confirmed behavior from speculation;
4. add a fixture or regression test when possible;
5. update this document with COVERED, PARTIAL, PLANNED, INVESTIGATE,
   NOT ADOPTED, or REVERIFY;
6. only change production behavior when supported by evidence.
