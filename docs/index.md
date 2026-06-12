# dv-interfaces

[![PyPI version](https://img.shields.io/pypi/v/dv-interfaces.svg)](https://pypi.org/project/dv-interfaces/)
[![Python versions](https://img.shields.io/pypi/pyversions/dv-interfaces.svg)](https://pypi.org/project/dv-interfaces/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/grrodre/dv-interfaces/blob/main/LICENSE)

Unified Modbus TCP driver library for solar plant hardware used in Direktvermarktung (direct energy marketing).

Each solar monitoring device — SolarLog, SMA, Meteocontrol, Smartdog — exposes a different Modbus register map with different byte orders, slave IDs, and NaN conventions. `dv-interfaces` abstracts all of that into one consistent Python API for reading production data and sending output curtailment commands.

---

## Features

- **Four drivers out of the box**: SolarLog, SMA cluster, Meteocontrol blue'Log XC, ecodata SmartDog
- **Unified read API**: `read_dataset()` returns the same `DVDataset` regardless of the underlying device
- **Write API**: `turn_on()`, `turn_off()`, `limit_plant(percent)`, `set_limitation_dv_percent()`, `set_limitation_dv_w()`
- **Typed Modbus configuration**: pass `modbus_config` as a dict or `DVModbusConfiguration`; omitted slave IDs use driver defaults
- **Auto-reconnect**: `_ensure_connected` transparently recovers dropped TCP connections before every register operation
- **Streaming generator**: `stream(iface)` yields readings continuously; errors are yielded as exceptions rather than crashing the loop
- **Driver detection**: `detect_interface(host)` probes registered drivers on known ports using each driver's probe registers and slave ID
- **Context-manager API**: guarantees clean socket release
- **Task-queue-ready**: `read_dataset_result().to_dict()` produces a flat dict for direct database insertion or task queue result backends
- **PEP 561 typed**: full type annotations, `py.typed` marker

---

## Try it without installing

```bash
uvx --from dv-interfaces dv-detect 192.168.1.100
uvx --from dv-interfaces dv-read solarlog 192.168.1.100
```

## Quick install

```bash
uv add dv-interfaces
# or
pip install dv-interfaces
```

---

## Quick example

```python
from dv_interfaces import get_interface

with get_interface('solarlog', '192.168.1.100') as iface:
    ds = iface.read_dataset()
    print(f'Production: {ds.production} W')
    print(f'Grid feed:  {ds.grid_feed:+d} W')
```

Then read [Getting started](getting-started.md) for the full picture.

---

## Supported devices

| Driver | Device | Protocol |
|--------|--------|----------|
| `solarlog` | SolarLog (all models with Modbus TCP DPM licence) | Modbus TCP |
| `sma` | SMA cluster (Sunny Home Manager, STP, etc.) | Modbus TCP |
| `meteocontrol` | Meteocontrol blue'Log XC | Modbus TCP |
| `smartdog` | ecodata PowerDog / SmartDog | Modbus TCP |
