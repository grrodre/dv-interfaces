"""Collect N readings and print a summary table.

Usage:
    python examples/batch_readings.py solarlog 192.168.1.100
    python examples/batch_readings.py solarlog 192.168.1.100:5020
    python examples/batch_readings.py solarlog 192.168.1.100 --count 50 --interval 5
"""

import argparse
from itertools import islice

from dv_interfaces import get_interface, stream


def parse_host_port(arg: str, default_port: int = 502) -> tuple[str, int]:
    if ':' in arg:
        host, port_str = arg.rsplit(':', 1)
        return host, int(port_str)
    return arg, default_port


def main() -> None:
    parser = argparse.ArgumentParser(description='Collect readings and print a table')
    parser.add_argument('driver', help='Driver name (solarlog, sma, meteocontrol, smartdog)')
    parser.add_argument('host', help='Device IP or hostname, optionally with port (host:port)')
    parser.add_argument('--count', type=int, default=20, help='Number of readings to collect')
    parser.add_argument('--interval', type=float, default=10.0, help='Seconds between reads')
    args = parser.parse_args()

    host, port = parse_host_port(args.host)
    print(f'Collecting {args.count} readings from {args.driver} at {host}:{port} …\n')

    header = f"{'read_at':<32}  {'production':>12}  {'consumption':>12}  {'grid_feed':>11}  {'elapsed_s':>9}"
    print(header)
    print('-' * len(header))

    rows = []
    with get_interface(args.driver, host, port=port) as iface:
        for result in islice(stream(iface, interval_s=args.interval), args.count):
            if isinstance(result, Exception):
                print(f'  error: {result}')
                continue
            ds = result.dataset
            print(
                f'{result.read_at.isoformat():<32}  '
                f'{ds.production:>11}W  '
                f'{ds.consumption:>11}W  '
                f'{ds.grid_feed:>+10}W  '
                f'{result.elapsed_s:>8.3f}s'
            )
            rows.append(result)

    if not rows:
        print('No successful reads.')
        return

    productions = [r.dataset.production for r in rows]
    grid_feeds = [r.dataset.grid_feed for r in rows]
    print(f'\nMean production : {sum(productions) / len(productions):.0f} W')
    print(f'Max grid feed   : {max(grid_feeds):+d} W')
    print(f'Min grid feed   : {min(grid_feeds):+d} W')


if __name__ == '__main__':
    main()
