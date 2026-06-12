# Reading data

## DVDataset

`DVDataset` is a frozen Pydantic model. It is the output of every `read_dataset()` call.

| Field | Type | Description |
|-------|------|-------------|
| `production` | `int` | Realtime AC production in W |
| `consumption` | `int` | Realtime consumption in W |
| `grid_feed` | `int` | Grid exchange in W — positive = feeding, negative = consuming |
| `limitation_nb_percent` | `float \| None` | Active Netzbetreiber curtailment in % |
| `limitation_nb_w` | `float \| None` | Active Netzbetreiber curtailment in W |
| `limitation_dv_percent` | `float \| None` | Active Direktvermarkter curtailment in % |
| `limitation_dv_w` | `float \| None` | Active Direktvermarkter curtailment in W |

`None` means the driver either does not support that field or the device did not return a meaningful value. There are no field-level constraints — out-of-range hardware values are stored as-is so reads never raise a `ValidationError` on unexpected device behaviour.

---

## read_dataset()

Reads all metrics in one call:

```python
ds = iface.read_dataset()

ds.production            # 5000
ds.consumption           # 1200
ds.grid_feed             # 3800
ds.limitation_nb_percent # 100.0 or None
ds.limitation_nb_w       # None
ds.limitation_dv_percent # 80.0  or None
ds.limitation_dv_w       # None
```

Modbus drivers override `read_dataset()` to batch all register reads into a single TCP request. Calling `read_dataset()` is therefore faster and more reliable than calling individual read methods back to back.

---

## Individual read methods

Use these when you only need a single value:

```python
iface.read_production()             # int, W
iface.read_consumption()            # int, W
iface.read_gridfeed()               # int, W
iface.read_limitation_nb_percent()  # float | None
iface.read_limitation_nb_w()        # float | None
iface.read_limitation_dv_percent()  # float | None
iface.read_limitation_dv_w()        # float | None
```

Each call is a separate TCP round-trip. Prefer `read_dataset()` when you need several values at once.

---

## DVReadResult

`read_dataset_result()` returns a `DVReadResult` wrapping the dataset with timing and identity metadata:

```python
result = iface.read_dataset_result()

result.interface   # 'solarlog'
result.host        # '192.168.1.100'
result.elapsed_s   # 0.043  (rounded to 3 decimal places)
result.read_at     # datetime in UTC, set at the start of the read
result.dataset     # DVDataset
```

### to_dict()

`to_dict()` flattens the dataset fields inline with the result metadata — ready for database insertion:

```python
result.to_dict()
# {
#     'interface': 'solarlog',
#     'host': '192.168.1.100',
#     'elapsed_s': 0.043,
#     'read_at': '2026-05-21T08:12:33.421000+00:00',
#     'production': 5000,
#     'consumption': 1200,
#     'grid_feed': 3800,
#     'limitation_nb_percent': 100.0,
#     'limitation_nb_w': None,
#     'limitation_dv_percent': 80.0,
#     'limitation_dv_w': None,
# }
```

### age_s and is_stale()

Track how old a cached result is:

```python
result = iface.read_dataset_result()

# ... some time passes ...

print(result.age_s)              # seconds since the read was initiated
if result.is_stale(max_age_s=300):
    result = iface.read_dataset_result()
```

### diff()

Compare two `DVDataset` objects to detect what changed between readings:

```python
prev = iface.read_dataset()
# ... wait ...
curr = iface.read_dataset()

changed = prev.diff(curr)
# {'production': (5000, 4800), 'grid_feed': (3800, 3600)}

if changed:
    logger.info('plant state changed: %s', changed)
```

`diff()` returns a `{field: (old_value, new_value)}` dict. Empty dict means nothing changed.
