# Real Itron Meter Reading Discovery

This document records MeterReading resources observed from a real
Xcel Energy / Itron meter during `xcel-meter-ha` development.

The purpose is to distinguish:

- what the meter actually advertised;
- what the project has successfully read and validated;
- what is still being investigated;
- what a value may mean to a Home Assistant user.

> Example values below are illustrative. They are not readings from the
> test household and must not be interpreted as actual utility usage.

## Status terminology

| Status | Meaning |
|---|---|
| Discovered | The meter advertised the resource and its ReadingType was inspected. |
| Core target | The project is actively implementing this as a primary sensor. |
| Validated | A real-meter value has been successfully retrieved and interpreted. |
| Future | Useful resource discovered, but full retrieval/support is not implemented yet. |

## Discovery summary

The real meter advertised **22 MeterReading resources** under `/upt/1/mr`.

| # | Meter resource | Reading path | ReadingType | Technical description | User-friendly description | Illustrative example | Possible Home Assistant value |
|---:|---|---|---|---|---|---|---|
| 1 | Instantaneous Demand | `/upt/1/mr/1/r` | `/rt/1` | Current active-power demand | How much electricity the home is using right now | `1.24 kW` | Live power gauge, load alerts, appliance/load analysis |
| 2 | Current Summation Received | `/upt/1/mr/2/r` | `/rt/2` | Cumulative active energy received by the grid | Total energy exported from the property | `823 kWh` | Solar/export tracking |
| 3 | Current Summation Delivered | `/upt/1/mr/3/r` | `/rt/3` | Cumulative active energy delivered by the grid | Total electricity imported from the utility | `12,345 kWh` | Primary HA Energy Dashboard import source |
| 4 | VAh Received | `/upt/1/mr/4/r` | `/rt/4` | Cumulative received apparent energy | Apparent energy flowing toward the grid | `900 kVAh` | Advanced export / power-quality analysis |
| 5 | VAh Delivered | `/upt/1/mr/5/r` | `/rt/5` | Cumulative delivered apparent energy | Total electrical loading including reactive effects | `13,100 kVAh` | Advanced electrical diagnostics |
| 6 | VARh Received | `/upt/1/mr/6/r` | `/rt/6` | Cumulative received reactive energy | Reactive energy flowing toward the grid | `120 kvarh` | Advanced power-quality diagnostics |
| 7 | VARh Delivered | `/upt/1/mr/7/r` | `/rt/7` | Cumulative delivered reactive energy | Reactive energy used by motors, HVAC, transformers, etc. | `1,420 kvarh` | HVAC/motor/power-quality analysis |
| 8 | TOU WH Received | `/upt/1/mr/8/r` | `/rt/8` | Time-of-use cumulative received Wh | Exported energy associated with a utility time bucket | `340 kWh` | Future TOU/export tariff analysis |
| 9 | TOU WH Delivered | `/upt/1/mr/9/r` | `/rt/9` | Time-of-use cumulative delivered Wh | Imported energy associated with a utility time bucket | `4,210 kWh` | Future tariff / seasonal / TOU analysis |
| 10 | WH Net (Interval) | No direct ReadingLink observed | `/rt/10` | Net active energy for an interval | Import minus export during one measurement period | `241 Wh` | Net-usage history and analytics |
| 11 | WH Received (Interval) | No direct ReadingLink observed | `/rt/11` | Active energy received during an interval | Energy exported during one measurement period | `84 Wh` | Solar/export interval graphs |
| 12 | WH Delivered (Interval) | No direct ReadingLink observed | `/rt/12` | Active energy delivered during an interval | Energy consumed during one measurement period | `325 Wh` | Fine-grained usage history |
| 13 | VAh Received (Interval) | No direct ReadingLink observed | `/rt/13` | Received apparent energy for an interval | Apparent export during a measurement period | `90 VAh` | Advanced interval diagnostics |
| 14 | VAh Delivered (Interval) | No direct ReadingLink observed | `/rt/14` | Delivered apparent energy for an interval | Apparent electrical load during a measurement period | `350 VAh` | Power-quality / equipment analysis |
| 15 | VARh Received (Interval) | No direct ReadingLink observed | `/rt/15` | Received reactive energy for an interval | Reverse reactive energy during a measurement period | `8 varh` | Advanced diagnostics |
| 16 | VARh Delivered (Interval) | No direct ReadingLink observed | `/rt/16` | Delivered reactive energy for an interval | Reactive behavior during a measurement period | `22 varh` | Motor/HVAC diagnostics |
| 17 | Max Demand Received | `/upt/1/mr/17/r` | `/rt/17` | Maximum reverse demand | Highest export level recorded | `5.2 kW` | Solar/export peak monitoring |
| 18 | Max Demand Delivered | `/upt/1/mr/18/r` | `/rt/18` | Maximum delivered demand | Highest electrical load recorded | `8.7 kW` | Peak-demand monitoring |
| 19 | Power Factor | `/upt/1/mr/19/r` | `/rt/19` | Aggregate power factor | How effectively apparent power is converted to useful real power | `0.96` | Power-quality diagnostics |
| 20 | Power Factor Phase A | `/upt/1/mr/20/r` | `/rt/20` | Phase-A power factor | Electrical efficiency / phase relationship on phase A | `0.97` | Advanced phase diagnostics |
| 21 | Power Factor Phase B | `/upt/1/mr/21/r` | `/rt/21` | Phase-B power factor | Electrical efficiency / phase relationship on phase B | `0.95` | Advanced phase diagnostics |
| 22 | Power Factor Phase C | `/upt/1/mr/22/r` | `/rt/22` | Phase-C power factor | Electrical efficiency / phase relationship on phase C | `0.96` | Advanced phase diagnostics |

## Core values targeted first

The first three values being promoted to supported Home Assistant entities are:

1. **Instantaneous Demand**
2. **Current Summation Delivered**
3. **Current Summation Received**

These were selected because they are direct meter facts and map naturally to:

- current power;
- grid import energy;
- grid export energy.

They should be preferred over locally reconstructed equivalents whenever the
meter provides reliable authoritative values.

## Important real-meter findings

### softwareVersion may be absent

The test meter did not expose a usable `softwareVersion` through `/sdev/sdi`.

The application must therefore report the agent/software version as unknown
rather than silently assuming version 2.

### phase may be omitted

For aggregate values such as Instantaneous Demand and Current Summation,
the real meter omitted the `phase` element rather than returning an explicit
phase value of `0`.

The classifier therefore treats an omitted phase as the aggregate/default
phase for classification purposes.

The original XML value remains authoritative; normalization is only used when
matching the ReadingType signature.

### Interval resources differ from direct readings

Several interval resources did not expose a direct `ReadingLink` in the
MeterReading response observed during testing.

Those resources remain documented as discovered, but interval retrieval must
be implemented and validated separately before they are advertised as
supported Home Assistant sensors.

## Trust and provenance principle

`xcel-meter-ha` follows this preference order:

1. **Meter-reported facts**
2. **Utility-provided facts**
3. **Locally derived values**

Derived values should be clearly identified as calculated estimates rather
than presented as if they came directly from the meter or utility.
