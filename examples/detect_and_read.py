"""Auto-detect the driver for an unknown device, then read a dataset.

Useful when a new plant connects to the VPN and only the IP is known.
If a port is given (host:port), only that port is probed.
Without a port, both 502 and 5020 are tried automatically.

Usage:
    python examples/detect_and_read.py 192.168.1.100
    python examples/detect_and_read.py 192.168.1.100:5020
    python examples/detect_and_read.py 10.8.0.42 --timeout 5.0
"""

import argparse

from dv_interfaces import detect_interface, get_interface


def parse_host_port(arg: str) -> tuple[str, tuple[int, ...]]:
    """Return (host, ports) — ports is a single-element tuple if given, else the defaults."""
    if ':' in arg:
        host, port_str = arg.rsplit(':', 1)
        return host, (int(port_str),)
    return arg, (502, 5020)


def main() -> None:
    parser = argparse.ArgumentParser(description='Detect and read a solar plant device')
    parser.add_argument(
        'host', help='Device IP address or hostname, optionally with port (host:port)'
    )
    parser.add_argument(
        '--timeout', type=float, default=2.0, help='Per-port probe timeout in seconds'
    )
    args = parser.parse_args()

    host, ports = parse_host_port(args.host)
    ports_str = ', '.join(str(p) for p in ports)
    print(f'Probing {host} on port(s) {ports_str} …')

    candidates = detect_interface(host, ports=ports, timeout=args.timeout)

    if not candidates:
        print(f'No device found on port(s) {ports_str}.')
        return

    for i, c in enumerate(candidates):
        marker = '★' if i == 0 else ' '
        print(
            f'  {marker} {c.driver:15s}  port={c.port}  slave_id={c.slave_id}  confidence={c.confidence}/2'
        )

    best = candidates[0]
    print(f'\nUsing: {best.driver} on port {best.port}')

    with get_interface(best.driver, host, port=best.port) as iface:
        ds = iface.read_dataset()

    nb = f'{ds.limitation_nb_percent:.1f}%' if ds.limitation_nb_percent is not None else 'None'
    dv = f'{ds.limitation_dv_percent:.1f}%' if ds.limitation_dv_percent is not None else 'None'
    print(f'prod={ds.production}W  cons={ds.consumption}W  grid={ds.grid_feed:+d}W  nb={nb}  dv={dv}')


if __name__ == '__main__':
    main()
