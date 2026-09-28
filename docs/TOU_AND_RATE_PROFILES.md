# Time-of-Use Rates and Community Rate Profiles

Xcel Meter HA should keep meter acquisition separate from utility pricing. The meter tells us how much energy crossed the grid boundary. A tariff tells us what that energy may cost and when different rates apply.

This page records the current design direction for time-of-use (TOU) support and the community-maintained rate-profile catalog.

## Current recommendation

For now, keep the core Xcel Meter HA runtime rate-agnostic and use Home Assistant's built-in Utility Meter helper for tariff buckets.

Home Assistant already supports:

- a cumulative source sensor such as Xcel Meter HA **Energy Delivered**;
- multiple tariff buckets such as `on_peak`, `mid_peak`, and `off_peak`;
- a select entity that represents the active tariff;
- automations that change the active tariff based on time or another source;
- helper and template entities for user-editable rates and estimated cost.

See:

- [Home Assistant Utility Meter](https://www.home-assistant.io/integrations/utility_meter/)
- [Home Assistant electricity grid and tariffs](https://www.home-assistant.io/docs/energy/electricity-grid/)
- [Home Assistant Number helper](https://www.home-assistant.io/integrations/input_number/)

This gives us a useful user workflow now without mixing billing logic into the IEEE 2030.5 meter client.

## Why TOU is not just another add-on toggle

The existing export option changes which meter reading Xcel Meter HA publishes. TOU is different: it is policy layered on top of the same energy measurements.

A rate plan can vary by:

- state and Xcel operating company;
- rate code or pilot program;
- season;
- weekday, weekend, and provider-defined holidays;
- time of day;
- import versus export direction;
- fixed customer charges, riders, fuel adjustments, credits, and taxes;
- effective date.

Xcel also publishes adjustments that can change independently of a base energy rate. For example, Minnesota fuel and rider values are published separately and can change over time. A simple dollars-per-kWh profile therefore should be treated as an **energy-cost estimate**, not a reproduction of the final bill.

Useful public references include:

- [Xcel Energy rate books](https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_books)
- [Xcel Energy rate riders](https://www.xcelenergy.com/company/rates_and_regulations/rates/rate_riders)
- [Xcel Energy Minnesota Flex Pricing Pilot](https://www.xcelenergy.com/company/rates_and_regulations/filings/flex_pricing_pilot)

## What Xcel already demonstrates

Xcel's own My Energy Connection materials combine meter usage with current-rate/TOU context and estimated energy cost. Xcel also labels those displayed values as estimates rather than final billing data. That is a useful product model for this project: show actionable rate context while keeping a clear boundary between an estimate and the utility bill.

See Xcel's [My Energy Connection program material](https://www.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20%26%20Regulations/22A-0315EG%20Q2%202023%20DSM%20Roundtable%20PPT.pdf) and the public [Integrated Distribution Plan appendix showing current rate/TOU presentment](https://prod2.xcelenergy.com/staticfiles/xe-responsive/Company/Rates%20%26%20Regulations/Regulatory%20Filings/202311-200135-01.pdf).

Those materials do not establish where the tariff metadata comes from. It may be account/cloud context rather than an IEEE 2030.5 resource exposed by the meter. Xcel Meter HA should keep that distinction explicit.

## What the IEEE 2030.5 standard can represent

IEEE 2030.5 includes a pricing function set with concepts such as `TariffProfile`, `RateComponent`, `TimeTariffInterval`, and `ConsumptionTariffInterval`. Those resources can model time-differentiated pricing.

That does **not** prove that Xcel's production meter agent exposes those resources to Launchpad clients.

The Xcel SDK meter-simulator source reviewed for the 0.4.5 work is metering-focused. Its `DeviceCapability` model and simulator route expose the UsagePoint/metering path, and the reviewed source does not implement the tariff/pricing resources above. Therefore Xcel Meter HA should not assume that a production meter provides an authoritative rate plan until that is demonstrated separately.

Future protocol research can safely probe for pricing links as a read-only diagnostic. Absence must remain a normal result, not an error.

## Community rate profiles

The repository now has a [`rate_profiles/`](../rate_profiles/README.md) catalog. Profiles are intended to be:

- human-readable examples;
- source-linked;
- dated;
- explicit about service region and rate code;
- clear about whether the values are historical, community-submitted, or verified against an official public source.

They are **not** currently loaded by the add-on at runtime.

A rate profile is useful even before native TOU support exists because it gives users a common description that can be translated into Home Assistant helpers and automations.

## Suggested Home Assistant path

The exact entity IDs vary by installation, so configure this through Home Assistant's UI where possible.

1. Go to **Settings -> Devices & services -> Helpers**.
2. Create a **Utility Meter** helper.
3. Use Xcel Meter HA **Energy Delivered** as the input sensor.
4. Choose the cycle you want to track, for example monthly.
5. Add the tariff names used by your plan, for example `on_peak`, `mid_peak`, and `off_peak`.
6. Create an automation that changes the Utility Meter tariff select entity according to your plan's schedule.
7. Optionally create Number helpers for the current rate of each tariff and Template sensors for estimated cost.

Do not use a rate profile as proof of the amount Xcel will bill. Fixed charges, riders, fuel adjustments, credits, taxes, demand charges, and other billing rules may not be represented.

## Architecture direction

```mermaid
flowchart LR
    Meter["Xcel / Itron meter"] -->|"Delivered / received energy"| Bridge["Xcel Meter HA"]
    Bridge --> HA["Home Assistant"]
    Profile["Community or provider rate profile"] --> Tariff["TOU helper / rate adapter"]
    HA --> Tariff
    Tariff --> Buckets["Peak / mid-peak / off-peak usage"]
    Tariff --> Estimate["Estimated energy cost"]

    Provider["Future authoritative provider source"] -. "if one becomes available" .-> Profile
    Pricing["Future IEEE 2030.5 pricing probe"] -. "only if exposed" .-> Profile
```

The meter path remains useful even if rate logic changes completely.

## Proposed phases

### Phase 1 - contribution and documentation foundation

Current scope:

- a versioned profile format;
- one historical, source-backed Xcel Minnesota example;
- a profile validator in CI;
- a GitHub rate-profile submission form;
- a structured support request form and support checklist;
- Home Assistant guidance using Utility Meter tariffs and helpers.

### Phase 2 - reusable Home Assistant recipe

After the profile format receives real-world submissions, build a supported example package or generator that can translate a profile into:

- tariff Utility Meter helpers;
- rate Number helpers;
- active-period automation;
- estimated-cost sensors.

This should remain opt-in and user-editable.

### Phase 3 - optional native rate adapter

Only after the model is proven across multiple service regions should Xcel Meter HA consider native rate entities such as:

- current tariff period;
- current configured energy rate;
- next tariff period and change time;
- estimated cost today/billing cycle;
- usage accumulated by tariff bucket.

If Xcel later provides an authoritative rate API or exposes IEEE 2030.5 pricing resources on production meters, that source can be added behind the same rate-profile abstraction rather than rewriting meter acquisition.

## What would change this design

The architecture should be revisited if any of these are demonstrated:

- a production Launchpad meter exposes a usable pricing function set;
- Xcel publishes an authenticated customer-rate API suitable for local integrations;
- Home Assistant gains a better provider-neutral tariff import format;
- submitted profiles reveal billing structures that the initial schema cannot represent cleanly.

Until then, rate profiles are intentionally advisory and Xcel Meter HA remains a read-only meter-data bridge.
