# Community Rate Profiles

This directory is a versioned, reviewable catalog of utility rate examples that can be translated into Home Assistant tariff helpers and, later, an optional Xcel Meter HA rate adapter.

Profiles are **not authoritative billing data** and are not currently loaded by the add-on.

## Goals

A profile should answer, in a machine-readable way:

- Which Xcel service region/rate plan is this?
- When was it effective or last verified?
- Which timezone applies?
- Which TOU periods exist?
- Which days and times activate each period?
- How do seasons change the energy rates?
- What public source supports the values?
- Is the profile current, historical, or community-submitted?
- Does it represent only energy charges or a broader bill estimate?

## Directory layout

```text
rate_profiles/
  README.md
  profile-template.toml
  profiles/
    us-mn-xcel-a72-a74-2022.toml
```

Use lowercase file names with country, state, provider, rate code/name, and a distinguishing year when useful.

## Catalog

Keep this table as the human-readable master index. Add a row when a reviewed profile is added; retain historical rows instead of silently replacing them.

| Service region | Plan | Rate code | Status | Evidence | Last verified | Profile |
|---|---|---|---|---|---|---|
| Minnesota | Residential Time of Use Pilot Program | A72/A74 | Historical example | Official Xcel publication | 2026-09-28 | [`us-mn-xcel-a72-a74-2022.toml`](profiles/us-mn-xcel-a72-a74-2022.toml) |

The long-term goal is at least one well-sourced example for each Xcel state/service region represented by contributors, while preserving rate-code and effective-date differences inside each region.

## Evidence levels

Use one of these values for `evidence_level`:

- `official-publication` - values transcribed from an official public utility/regulator source linked in the profile.
- `community-submitted` - values supplied by a user from a bill, portal, or other account-specific source and not yet independently confirmed.
- `maintainer-reviewed` - a community submission that has been cross-checked against a public source or multiple consistent reports.

`official-publication` describes the source of the data. It does **not** mean Xcel Energy endorses this repository or guarantees that the profile applies to a particular account.

## Profile status

Use one of:

- `current-example` - believed current as of `last_verified`, but users must still verify their own plan.
- `historical-example` - intentionally retained to document an older plan/effective period or demonstrate the schema.
- `submitted` - awaiting review.

Profiles should not silently disappear when a tariff changes. Prefer adding a new dated profile or updating status/effective dates so the repository keeps a useful history.

## Billing scope

The initial schema intentionally focuses on time-varying energy charges.

Use `billing_scope = "energy-only"` unless the profile explicitly models every component needed for the stated estimate. Xcel bills may also include customer charges, fuel clauses, riders, taxes, credits, demand charges, and other adjustments.

A profile therefore must never be presented as a guaranteed bill calculator.

## Generate a Home Assistant TOU package

Phase 2 includes a small standard-library generator that translates a validated profile into an opt-in Home Assistant package. It keeps the meter add-on rate-agnostic while making the profile immediately useful for tariff tracking.

First find the actual Home Assistant entity ID for Xcel Meter HA **Energy Delivered**. Then run, for example:

```bash
python tools/generate_ha_tou_package.py \
  rate_profiles/profiles/us-mn-xcel-a72-a74-2022.toml \
  --source-entity sensor.your_energy_delivered_entity \
  --output xcel_tou.yaml
```

The generator creates:

- a Home Assistant Utility Meter with one bucket per profile period;
- a current-period template sensor;
- a current-season template sensor;
- a current configured energy-rate sensor;
- an automation that keeps the Utility Meter tariff selector synchronized;
- a provider-holiday date helper when the profile marks a period with `exclude_holidays = true`.

The generator intentionally does **not** create a final-bill or monthly-cost sensor yet. Applying the current season's rate to an entire accumulated billing period can be wrong across seasonal/rate-effective boundaries, and riders/taxes/adjustments may be outside the profile.

See [`../docs/TOU_AND_RATE_PROFILES.md`](../docs/TOU_AND_RATE_PROFILES.md) and [`../examples/home-assistant/README.md`](../examples/home-assistant/README.md) for installation and validation.

## Contributing a new profile

The easiest path is the repository's **Rate profile submission** GitHub issue form. Provide a public official rate-book/tariff URL when one exists.

If you submit a pull request instead:

1. Copy [`profile-template.toml`](profile-template.toml).
2. Put the new file in `rate_profiles/profiles/`.
3. Fill every required field.
4. Remove account-specific information.
5. Run:

```bash
python tools/check_rate_profiles.py
python tools/check_docs.py
```

6. In the pull request, explain which source you used and whether the profile is current or historical.

## Privacy rules

Do not commit:

- account numbers;
- customer names/addresses;
- meter numbers or LFDIs;
- private keys/certificates;
- screenshots of bills or portals that still contain identifying information.

Rates and schedules are useful. Account identity is not.

## Schema notes

The schema starts deliberately small. It supports seasonal TOU plans with named periods and per-kWh rates. It does not yet attempt to model every tariff construct in every Xcel jurisdiction.

If a real rate plan cannot be represented without awkward workarounds, open a rate-profile issue describing the missing concept before expanding the schema. Examples might include:

- demand charges;
- critical-peak events;
- tiered consumption blocks;
- dynamic hourly pricing;
- export compensation;
- holidays with provider-specific observance rules;
- monthly riders that change independently of base rates.

Keeping these as explicit extensions is safer than pretending all tariffs are simple peak/off-peak schedules.
