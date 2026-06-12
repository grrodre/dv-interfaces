# Driver detection

When a plant device connects to the VPN and only the IP address is known, `detect_interface` probes the host across a set of ports and returns ranked driver candidates. Each driver owns its probe registers and default slave ID. The operator can confirm the suggestion or override it.

---

## detect_interface()

```python
from dv_interfaces import detect_interface, get_interface

candidates = detect_interface('10.8.0.42')

if candidates:
    best = candidates[0]
    print(best.driver)      # 'solarlog'
    print(best.port)        # 502
    print(best.slave_id)    # 1
    print(best.confidence)  # 2

    with get_interface(best.driver, '10.8.0.42', port=best.port) as iface:
        result = iface.read_dataset_result()
```

**Signature:**

```python
detect_interface(
    host: str,
    ports: tuple[int, ...] = (502, 5020),
    timeout: float = 2.0,
) -> list[DetectionCandidate]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | — | Device hostname or IP |
| `ports` | `(502, 5020)` | TCP ports to probe, tried in order |
| `timeout` | `2.0` | Per-connection timeout in seconds |

Returns an empty list if the host is unreachable on all ports or no registered driver responded.

---

## DetectionCandidate

Each result is a `DetectionCandidate` named tuple:

| Field | Type | Description |
|-------|------|-------------|
| `driver` | `str` | Driver name (`'solarlog'`, `'sma'`, etc.) |
| `port` | `int` | Port on which the device responded |
| `slave_id` | `int` | Modbus slave ID that responded |
| `confidence` | `int` | Number of characteristic registers that responded (0–2) |

Results are sorted by `confidence` descending — `candidates[0]` is the best match.

---

## Confidence scoring

Confidence is the count of characteristic registers that returned a valid (non-error) response. Each driver probes up to 2 registers known to be present on its device type.

| Score | Meaning |
|-------|---------|
| `2` | Both characteristic registers responded — high confidence |
| `1` | One register responded — partial match, confirm manually |
| `0` | No characteristic registers responded — excluded from results |

Because each driver probes its own register map and default Modbus slave ID (SolarLog=1, SMA=2, Smartdog=2, Meteocontrol=10), false positives across driver types are rare even at confidence 1.

---

## Handling multiple candidates

On networks where multiple devices are reachable from the same IP (behind a proxy or VPN concentrator), multiple candidates can be returned:

```python
candidates = detect_interface('10.8.0.42')

for c in candidates:
    print(f'{c.driver:15s}  port={c.port}  slave_id={c.slave_id}  confidence={c.confidence}')
```

Pick `candidates[0]` for unattended flows, or present all candidates to an operator for confirmation.

---

## Timeout tuning

On slow or high-latency links, increase the timeout:

```python
candidates = detect_interface('10.8.0.42', timeout=5.0)
```

On a fast LAN where you know the port, scan only that port to speed things up:

```python
candidates = detect_interface('192.168.1.100', ports=(502,), timeout=1.0)
```
