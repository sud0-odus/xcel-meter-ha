# Home Assistant TOU Package Example

Xcel Meter HA publishes the meter's cumulative **Energy Delivered** value. Home Assistant's native Utility Meter integration can split that cumulative source into tariff buckets without putting utility pricing logic inside the meter add-on.

The repository's rate-profile generator turns a validated profile into a Home Assistant package that does that wiring for you.

## 1. Find your Energy Delivered entity ID

In Home Assistant:

1. Open **Settings -> Devices & services -> Devices**.
2. Open **Xcel Energy Smart Meter**.
3. Open **Energy Delivered**.
4. Note the entity ID. Entity IDs vary by installation, so do not copy an ID from someone else's screenshot.

The source must be the cumulative Energy Delivered sensor, not Instantaneous Power.

## 2. Verify the rate profile

Choose a profile under [`../../rate_profiles/profiles/`](../../rate_profiles/profiles/). Read its `status`, `last_verified`, source, effective dates, and notes before using it.

A `historical-example` is a schema/example artifact, **not** a recommendation to use those rates today.

## 3. Generate the package

From the repository root:

```bash
python tools/generate_ha_tou_package.py \
  rate_profiles/profiles/us-mn-xcel-a72-a74-2022.toml \
  --source-entity sensor.your_energy_delivered_entity \
  --output xcel_tou.yaml
```

Optional arguments:

- `--namespace my_tou` changes generated entity IDs so multiple independent packages can coexist.
- `--cycle daily`, `--cycle weekly`, or `--cycle monthly` selects the Utility Meter reset cycle. `monthly` is the default.

The generator refuses profile features it cannot translate safely. For example, Phase 2 currently rejects non-fallback periods that cross midnight rather than guessing which calendar day's rule should win.

If your account differs from a repository example, copy the TOML profile, edit the copy to match your documented plan, validate it with `python tools/check_rate_profiles.py` when it lives in the repository catalog, and regenerate the package. Prefer changing the profile over hand-editing generated YAML so the rate definition remains reviewable.

## 4. Install as a Home Assistant package

One supported Home Assistant layout is:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Place the generated file at, for example:

```text
/config/packages/xcel_tou.yaml
```

Before restarting Home Assistant, run **Settings -> System -> YAML -> Check configuration** (or the equivalent configuration validation available in your installation).

Then restart Home Assistant so the package is loaded.

## 5. Validate the entities

A default-namespace monthly package should create entities equivalent to:

- `sensor.xcel_tou_current_period`
- `sensor.xcel_tou_current_season`
- `sensor.xcel_tou_current_rate`
- `select.xcel_tou_monthly_energy`
- one Utility Meter sensor for each tariff bucket
- `input_datetime.xcel_tou_provider_holiday` when the profile has provider-defined holiday exclusions

Exact friendly names are shown in Home Assistant; entity IDs can change if there is an existing naming collision.

Check that:

1. **Current Period** matches the rate period you expect for the current local day/time.
2. **Current Season** matches the profile's seasonal date range.
3. **Current Rate** matches the selected period/season value in the TOML profile.
4. The Utility Meter tariff select follows **Current Period** within a few seconds.
5. Energy accumulates into the active tariff bucket when Energy Delivered advances.

## Holiday override

If the profile marks a period with `exclude_holidays = true`, the generated package includes a provider-holiday date helper. Set it only to a date that the selected tariff actually treats as excluded. The override is active only when that saved date equals today, so it cannot be accidentally left on for the next day.

Choosing the date is manual on purpose. The current profile schema does not yet encode enough provider-specific holiday/observance data to automate that safely.

## What this package does not claim

The generated current rate is rate-profile context, not an authoritative Xcel bill calculation. The package does not model every possible fixed charge, fuel clause, rider, tax, credit, demand charge, export credit, or rate change within a billing cycle.

The first goal is dependable tariff-period **classification and usage bucketing**. Cost accumulation can be added later after real profiles prove how effective-date, season, holiday, and rider boundaries need to behave.
