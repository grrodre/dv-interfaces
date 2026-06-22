# dv-interfaces

[![PyPI version](https://img.shields.io/pypi/v/dv-interfaces.svg)](https://pypi.org/project/dv-interfaces/)
[![Python versions](https://img.shields.io/pypi/pyversions/dv-interfaces.svg)](https://pypi.org/project/dv-interfaces/)
[![CI](https://github.com/grrodre/dv-interfaces/actions/workflows/ci.yml/badge.svg)](https://github.com/grrodre/dv-interfaces/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Unified Modbus TCP driver library for solar plant hardware used in Direktvermarktung (direct energy marketing).

Each device — SolarLog, SMA, Meteocontrol, Smartdog — exposes a different Modbus register map. `dv-interfaces` abstracts all of it into one consistent Python API for reading production data and sending output curtailment commands.

**[Full documentation →](https://grrodre.github.io/dv-interfaces/)**

---

## Context

Each device — SolarLog, SMA, Meteocontrol, SmartDog — exposes a different Modbus register map with different byte orders, slave IDs, and conventions. Without a shared layer, every integration has to rediscover and reimplement the same mapping work.

`dv-interfaces` removes that undifferentiated effort so you can build polling jobs, control paths, and validation tooling without touching raw register math.

The library covers **Modbus TCP**, the most common protocol for Fernsteuerbarkeit in Direktvermarktung. IEC 60870-5-104 is used in this space too but is not currently supported.

---

## Installation

```bash
uv add dv-interfaces
# or
pip install dv-interfaces
```

---

## Try it without installing

```bash
uvx --from dv-interfaces dv-detect 192.168.1.100
uvx --from dv-interfaces dv-read solarlog 192.168.1.100
```

![dv-read output](https://raw.githubusercontent.com/grrodre/dv-interfaces/main/docs/imgs/screenshot_dv_read_solarlog.png)

## Quick example

```python
from dv_interfaces import get_interface

with get_interface('solarlog', '192.168.1.100') as iface:
    ds = iface.read_dataset()
    print(f'Production: {ds.production} W')
    print(f'Grid feed:  {ds.grid_feed:+d} W')
```

---

## Supported devices

| Driver | Device | Protocol | Spec |
|--------|--------|----------|------|
| `solarlog` | SolarLog (Modbus TCP DPM licence required) | Modbus TCP | [Datasheet](https://www.solar-log.com/fileadmin/user_upload/documents/Datenblaetter/de_DE/Komponenten/Kommunikation/SolarLog_Datasheet_Modbus_TCP_DPM_DE.pdf) |
| `sma` | SMA cluster | Modbus TCP | [TI Direktvermarktung](https://files.sma.de/downloads/Direktvermarktung-TI-de-11.pdf) |
| `meteocontrol` | Meteocontrol blue'Log XC | Modbus TCP | [Remote Power Control](https://www.meteocontrol.com/fileadmin/Daten/Dokumente/DE/2_SCADA_Parkregelung/1_Produkte/1_blueLog_XC/blueLog_XC_DE/DB_Remote_Power_Control_blueLog_XC_de.pdf) |
| `smartdog` | ecodata PowerDog / SmartDog | Modbus TCP | [Modbus Register List](https://anleitung.smart-dog.eu/books/modbus-registerliste/page/modbus-registerliste-auch-fur-pave) |

---

## Features

- Unified `read_dataset()` → `DVDataset` across all drivers
- Write API: `turn_on()`, `turn_off()`, `limit_plant(percent)`
- Typed Modbus configuration with driver default slave IDs
- `stream(iface)` generator — yields readings continuously, errors yielded not raised
- `detect_interface(host)` — identify an unknown device by probing Modbus registers
- `read_dataset_result().to_dict()` — flat dict for direct DB insertion or task queue backends
- Auto-reconnect on dropped TCP connections
- PEP 561 typed

---

## Issues and bugs

If you find a bug, a wrong register interpretation, or a device-specific edge case, please [open an issue](https://github.com/grrodre/dv-interfaces/issues). Include the driver name, device model/firmware if known, the relevant Modbus register values, and the expected behaviour.

---

## Development

```bash
uv sync
uv run pytest -m "not hardware"
uv run ruff check src/ tests/
uv run ty check
uv run mkdocs serve   # local docs preview
```

### Hardware tests

Set one or more `DV_TEST_<DRIVER>_HOST` variables and run the `hardware` marker:

```bash
DV_TEST_SOLARLOG_HOST=192.168.1.100 uv run pytest -m hardware -v
```

Tests for drivers whose host variable is not set are automatically skipped. Multiple drivers can be tested at once:

```bash
DV_TEST_SOLARLOG_HOST=192.168.1.100 \
DV_TEST_SMA_HOST=192.168.1.101 \
uv run pytest -m hardware -v
```

See the [hardware testing docs](https://grrodre.github.io/dv-interfaces/testing/) for the full variable reference.

![Hardware tests](https://raw.githubusercontent.com/grrodre/dv-interfaces/main/docs/imgs/screenshot_hardware_tests.png)

## License

MIT, see [LICENSE](LICENSE).

---

## About

Built by Gregorio Rodrigo  
Making energy market data easier to work with

[grrodre@gmail.com](mailto:grrodre@gmail.com)
