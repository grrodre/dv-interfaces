# Controlling output

Write methods raise `ErrorLimitingDVInterface` (or `ErrorTurnOnDVInterface` / `ErrorTurnOffDVInterface`) if the Modbus write fails. Unsupported operations raise `ErrorUnsupportedOperationDVInterface`. See [Exceptions](configuration.md#exceptions).

---

## turn_on()

Set the plant to maximum output — removes any active Direktvermarkter limitation:

```python
iface.turn_on()
```

Internally this writes the driver's "no limitation / 100%" command to the device.

---

## turn_off()

Set the plant to minimum output:

```python
iface.turn_off()
```

Equivalent to sending a 0% setpoint. The exact effect depends on the device — most inverters ramp to near-zero rather than hard-stopping.

---

## limit_plant(percent)

Convenience method with built-in range validation:

```python
iface.limit_plant(80)    # 80% of rated output
iface.limit_plant(0)     # minimum
iface.limit_plant(100)   # full power
```

Raises `ValueError` for values outside `[0, 100]`. Use this in production code to catch programming errors early.

---

## set_limitation_dv_percent(percent)

Same as `limit_plant` but without the range check. Accepts any float:

```python
iface.set_limitation_dv_percent(80.0)
```

Use when the setpoint comes from a validated external source (e.g. a polling task that already validated the market signal).

---

## set_limitation_dv_w(watts)

Limit by absolute watt value instead of percentage:

```python
iface.set_limitation_dv_w(50000.0)  # cap at 50 kW
```

!!! warning "Not supported by all drivers"
    SolarLog and SMA do not support watt-based Direktvermarkter limits — these drivers set `supports_dv_watt_limit = False` and raise `ErrorUnsupportedOperationDVInterface`. Check `iface.supports_dv_watt_limit` or use `set_limitation_dv_percent` for portable code.

    Meteocontrol and Smartdog support watt-based limits.

---

## Watchdog behaviour (Smartdog)

The Smartdog's setpoint registers have a **5-minute timeout** — if no Modbus communication arrives within 5 minutes, the device resets to unrestricted output. For continuous curtailment, repeat the `set_limitation_dv_percent` call at least once every 4 minutes:

```python
from dv_interfaces import get_interface, stream
from itertools import islice

with get_interface('smartdog', '10.8.0.42') as iface:
    iface.set_limitation_dv_percent(70.0)

    # Refresh setpoint every 240 s to stay inside the 300 s watchdog window
    for result in stream(iface, interval_s=240):
        iface.set_limitation_dv_percent(70.0)
```

---

## Watchdog behaviour (SolarLog)

SolarLog similarly requires the Direktvermarkter to write a WatchDog_Tag (a 32-bit counter) along with each setpoint update. The driver handles this automatically — each call to `set_limitation_dv_percent` or `turn_on`/`turn_off` writes the full 3-register control block (watchdog tag + mode + value).
