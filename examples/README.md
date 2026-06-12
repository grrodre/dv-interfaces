# Examples

Standalone runnable scripts. Each script is self-contained and shows one real-world use case.

| Script | Description |
|--------|-------------|
| `poll_forever.py` | Continuous polling loop — reads every 60 s and prints a live summary line |
| `detect_and_read.py` | Auto-detect the driver for an unknown IP, then read a dataset |
| `batch_readings.py` | Collect N readings and print a summary table |

## Running

```bash
uv run examples/poll_forever.py solarlog 192.168.1.100
uv run examples/poll_forever.py solarlog 192.168.1.100:5020

uv run examples/detect_and_read.py 10.8.0.42           # probes 502 and 5020 automatically
uv run examples/detect_and_read.py 10.8.0.42:5020      # probes only port 5020
uv run examples/detect_and_read.py 10.8.0.42 --timeout 5.0

uv run examples/batch_readings.py solarlog 192.168.1.100 --count 10 --interval 5
uv run examples/batch_readings.py solarlog 192.168.1.100:5020
```

