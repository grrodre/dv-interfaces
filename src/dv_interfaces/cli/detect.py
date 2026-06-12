"""CLI entry point: probe a host and identify the connected Modbus device."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='dv-detect',
        description='Probe a host and identify the Modbus device type.',
    )
    parser.add_argument(
        'host',
        help='Device IP address or hostname, optionally with port (host:port)',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=2.0,
        help='Per-connection timeout in seconds (default: 2.0)',
    )
    args = parser.parse_args()

    if ':' in args.host:
        host, port_str = args.host.rsplit(':', 1)
        ports: tuple[int, ...] = (int(port_str),)
    else:
        host = args.host
        ports = (502, 5020)

    from dv_interfaces import detect_interface

    print(f'Probing {args.host} ...')
    try:
        candidates = detect_interface(host, ports=ports, timeout=args.timeout)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if not candidates:
        print('No device identified.')
        sys.exit(1)

    print(f'\n{"Driver":<16} {"Port":<6} {"Slave ID":<10} Confidence')
    print(f'{"-" * 16} {"-" * 6} {"-" * 10} {"-" * 10}')
    for c in candidates:
        print(f'{c.driver:<16} {c.port:<6} {c.slave_id:<10} {c.confidence}')
