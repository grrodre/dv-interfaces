# Drivers reference

Device-specific notes for each supported driver.

---

## SolarLog

**Driver name:** `solarlog`  
**Default port:** `502`  
**Slave ID:** `1`  
**Byte order:** big-endian  
**Word order:** little-endian  

### Licence requirement

The SolarLog device must have the **Modbus TCP DPM** licence enabled. Without it the Modbus port is open but all register reads return errors.

You can check the licence status programmatically:

```python
with get_interface('solarlog', '192.168.1.100') as iface:
    status = iface.status()
    # 0 = OK, 1 = licence not activated or insufficient
```

### Register reads

All base dataset metrics are read from **input registers** (FC04) in a single batched call covering addresses 10900–10911. `read_dataset()` is therefore one TCP round-trip for the supported readback values.

### Writing setpoints

Setpoints use a control block written to **holding registers** at addresses 10400, 10401, and 10404–10405:

| Address | Register | Description |
|---------|----------|-------------|
| 10400 | Control_Tag | Mode: `1` = relative %, `2` = fixed 0% |
| 10401 | Control_Value | Setpoint value (0–100) |
| 10404–10405 | WatchDog_Tag | 32-bit counter, must increment each call |

`turn_on()` writes mode `1` with value `100`.  
`turn_off()` writes mode `2` with value `0`.  
`set_limitation_dv_percent(percent)` writes mode `1` with the given percentage.

### Watt-based limits

`set_limitation_dv_w()` is not supported. `supports_dv_watt_limit` is `False`, and calling the method raises `ErrorUnsupportedOperationDVInterface`. Use `set_limitation_dv_percent` for all setpoints.

### Extended reads

```python
# Estimated possible plant power (W) — 0 if no optional power sensor fitted
possible = iface.read_possible_production_w()

# Battery charging power (W) — 0 if no battery; firmware >= 6.0.1 required
charge = iface.read_battery_charge_w()

# Battery discharging power (W) — 0 if no battery; firmware >= 6.0.1 required
discharge = iface.read_battery_discharge_w()
```

Note that `read_limitation_dv_percent()` and `read_limitation_dv_w()` both return `None` — the DV setpoint registers (10400–10401) are write-only and there is no readback register in the SolarLog DPM interface.

---

## SMA

**Driver name:** `sma`  
**Default port:** `502`  
**Slave ID:** `2` (fixed)  
**Byte order:** big-endian  
**Word order:** big-endian  

### NaN sentinels

SMA devices use specific bit patterns to indicate "not available":

| Type | Sentinel | Meaning |
|------|----------|---------|
| `uint32` | `0xFFFFFFFF` | Not available |
| `int32` | `0x80000000` | Not available |
| `uint64` | `0xFFFFFFFFFFFFFFFF` | Not available |

When a sentinel is detected, the driver returns `0` for production/consumption/gridfeed, or `None` for limitation and extended fields.

### Register reads

Production, consumption, grid feed, and limitation readbacks are read from **input registers** (FC04). Direktvermarkter percent setpoints are written to holding register 40493.

### Extended reads

SMA exposes additional metrics beyond the base `DVDataset`:

```python
# Grid frequency (Hz) — None if not available
freq = iface.read_grid_frequency_hz()

# Battery state of charge (%) — None if no battery
soc = iface.read_battery_soc_percent()
```

### Watt-based limits

`set_limitation_dv_w()` is not supported. `supports_dv_watt_limit` is `False`, and calling the method raises `ErrorUnsupportedOperationDVInterface`.

---

## Meteocontrol

**Driver name:** `meteocontrol`  
**Default port:** `502`  
**Slave ID:** `10` (fixed)  
**Byte order:** big-endian  
**Word order:** little-endian  
**Register type:** holding registers (FC03) with 32-bit float values  

### NaN handling

Registers containing `NaN` (IEEE 754) are treated as `None` in limitation fields.

### Setpoint registers

| Address | Description |
|---------|-------------|
| 5000 | Direktvermarkter limit in % (float32) |
| 5002 | Direktvermarkter limit in W (float32) |

Both watt-based and percentage-based setpoints are supported.

### Limitation values > 100%

Meteocontrol devices can return limitation values above 100% (e.g. 125%) — these represent "no curtailment" signals on some firmware versions. `DVDataset` stores them as-is.

---

## Smartdog (ecodata PowerDog / SmartDog)

**Driver name:** `smartdog`  
**Default port:** `502`  
**Slave ID:** `2` (fixed)  
**Byte order:** big-endian  
**Word order:** big-endian  
**Register type:** holding registers (FC03) with signed 32-bit integers  

### Grid feed polarity

Smartdog uses **Verbraucherpfeilsystem** (consumer arrow convention), the opposite of the standard generator convention. Grid feed register 40000 must be negated:

- Device register positive → grid is *consuming* → `grid_feed` is negative
- Device register negative → grid is *feeding* → `grid_feed` is positive

The driver applies this negation automatically.

This matches the SmartDog Modbus list: values are documented in Verbraucherpfeilsystem, with register 40090 called out separately as Erzeugerpfeilsystem. The public `DVDataset.grid_feed` contract stays generator-oriented across all drivers: positive means export/feed-in, negative means import/draw.

### NaN sentinel

`-1` is the NaN sentinel for optional fields (limitation, battery SOC). The driver returns `None` when `-1` is read.

### Setpoint registers and watchdog

Activating a Direktvermarkter limit requires two writes:

| Address | Description |
|---------|-------------|
| 40004 | Power setpoint in W (int32) |
| 40014 | Activation flag: `1` = active, `0` = inactive |

**The setpoint registers have a 5-minute hardware timeout.** If no Modbus communication arrives within 5 minutes, the device resets to unrestricted output. Repeat the setpoint write at least once every 4 minutes to maintain continuous curtailment.

### Extended reads

```python
# Battery state of charge (%) — None if no battery or sentinel -1
soc = iface.read_battery_soc_percent()
```
