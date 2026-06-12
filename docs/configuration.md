# Configuration

## DVModbusConfiguration

All Modbus drivers accept `modbus_config` as either a dict or a `DVModbusConfiguration` instance. Pydantic validates it at construction time, and unknown keys raise a `ValidationError` immediately.

```python
iface = get_interface('solarlog', '192.168.1.100', modbus_config={
    'slave_id': 3,
    'timeout': 10.0,
    'max_retries': 2,
    'retry_delay': 0.5,
})
```

```python
from dv_interfaces import DVModbusConfiguration, get_interface

config = DVModbusConfiguration(slave_id=3, timeout=10.0)
iface = get_interface('solarlog', '192.168.1.100', modbus_config=config)
```

| Key | Type | Default | Constraint | Description |
|-----|------|---------|------------|-------------|
| `slave_id` | `int` | driver default | 1–247 | Modbus unit identifier |
| `timeout` | `float` | `5.0` | > 0 | TCP connection timeout in seconds |
| `max_retries` | `int` | `0` | ≥ 0 | Extra register-read attempts on transient failure |
| `retry_delay` | `float` | `0.2` | ≥ 0 | Seconds between retry attempts |

If `slave_id` is omitted, each driver applies its own default: SolarLog `1`, SMA `2`, SmartDog `2`, Meteocontrol `10`.

`max_retries` retries individual register reads before raising — separate from task-level retries in your scheduler or async framework. Bus noise (transient CRC error) and device unreachability (TCP timeout) are different failure modes with different backoff strategies.

---

## From environment variables

### DVModbusConfiguration.from_env()

Build a configuration from environment variables without passing a dict:

```python
from dv_interfaces import DVModbusConfiguration

cfg = DVModbusConfiguration.from_env()
# reads DV_SLAVE_ID, DV_TIMEOUT, DV_MAX_RETRIES, DV_RETRY_DELAY
```

Use a custom prefix for multiple devices in the same process:

```python
cfg_a = DVModbusConfiguration.from_env(prefix='PLANT_A')
cfg_b = DVModbusConfiguration.from_env(prefix='PLANT_B')
```

Variables with the prefix:

| Variable | Maps to |
|----------|---------|
| `{prefix}_SLAVE_ID` | `slave_id` |
| `{prefix}_TIMEOUT` | `timeout` |
| `{prefix}_MAX_RETRIES` | `max_retries` |
| `{prefix}_RETRY_DELAY` | `retry_delay` |

---

## Polling task integration

`read_dataset_result` is designed as the entry point for polling tasks. Errors propagate as typed exceptions so the caller can apply appropriate retry logic per failure mode:

```python
import asyncio
import logging
from dv_interfaces import get_interface
from dv_interfaces.exceptions import ErrorReadDVInterface, ErrorConnectionDVInterface

logger = logging.getLogger(__name__)

async def poll_plant(driver: str, host: str, interval_s: float = 60.0) -> None:
    read_retries = 0
    while True:
        try:
            with get_interface(driver, host, modbus_config={'max_retries': 2}) as iface:
                result = iface.read_dataset_result()
                logger.info('read: %s', result.to_dict())
                read_retries = 0
        except ErrorReadDVInterface as exc:
            read_retries += 1
            backoff = min(2 ** read_retries, 30)
            logger.warning('read failed (%s), retry in %ss', exc, backoff)
            await asyncio.sleep(backoff)
            continue
        except ErrorConnectionDVInterface as exc:
            logger.error('device unreachable (%s:%s), retry in 60s', exc.host, exc.port)
            await asyncio.sleep(60)
            continue
        await asyncio.sleep(interval_s)
```

---

## Exceptions

All exceptions inherit from `ErrorDVInterface`:

```
ErrorDVInterface
├── ErrorConnectionDVInterface   device unreachable or socket lost
├── ErrorReadDVInterface         register read failed
├── ErrorTurnOnDVInterface       turn-on command failed
├── ErrorTurnOffDVInterface      turn-off command failed
├── ErrorLimitingDVInterface     power limit command failed
└── ErrorUnsupportedOperationDVInterface unsupported driver operation
```

`ErrorConnectionDVInterface` carries `host` and `port` attributes:

```python
from dv_interfaces.exceptions import ErrorConnectionDVInterface

try:
    iface.connect()
except ErrorConnectionDVInterface as exc:
    logger.error('cannot reach %s:%s', exc.host, exc.port)
```

---

## Logging

The library logs under the `dv_interfaces` logger hierarchy. Enable debug output to see every reconnect and register read attempt:

```python
import logging
logging.getLogger('dv_interfaces').setLevel(logging.DEBUG)
```
