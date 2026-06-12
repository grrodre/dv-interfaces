"""CLI entry point: connect to a device and read one dataset."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='dv-read',
        description='Connect to a device and read one dataset.',
    )
    parser.add_argument(
        'driver',
        help='Driver name (solarlog, sma, meteocontrol, smartdog)',
    )
    parser.add_argument(
        'host',
        help='Device IP address or hostname, optionally with port (host:port)',
    )
    parser.add_argument(
        '--slave-id',
        type=int,
        help='Modbus slave ID (overrides driver default)',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=5.0,
        help='Connection timeout in seconds (default: 5.0)',
    )
    args = parser.parse_args()

    if ':' in args.host:
        host, port_str = args.host.rsplit(':', 1)
        port = int(port_str)
    else:
        host = args.host
        port = 502

    modbus_config: dict = {'timeout': args.timeout}
    if args.slave_id is not None:
        modbus_config['slave_id'] = args.slave_id

    from dv_interfaces import get_interface

    try:
        with get_interface(
            args.driver, host, port=port, modbus_config=modbus_config
        ) as iface:
            result = iface.read_dataset_result()
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    ds = result.dataset
    nb = (
        f'{ds.limitation_nb_percent:.1f}%'
        if ds.limitation_nb_percent is not None
        else 'None'
    )
    dv = (
        f'{ds.limitation_dv_percent:.1f}%'
        if ds.limitation_dv_percent is not None
        else 'None'
    )
    print(
        f'prod={ds.production}W  cons={ds.consumption}W  grid={ds.grid_feed:+d}W  nb={nb}  dv={dv}'
    )
    print(
        f'interface={result.interface}  host={result.host}  elapsed={result.elapsed_s:.3f}s'
    )
