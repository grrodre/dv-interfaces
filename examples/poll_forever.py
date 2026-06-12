"""Continuous polling loop — reads every 60 s and prints a one-line summary.

Usage:
    python examples/poll_forever.py solarlog 192.168.1.100
    python examples/poll_forever.py solarlog 192.168.1.100:5020
    python examples/poll_forever.py solarlog 192.168.1.100 --interval 30
"""

import argparse
import logging

from dv_interfaces import get_interface, stream

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


def parse_host_port(arg: str, default_port: int = 502) -> tuple[str, int]:
    if ':' in arg:
        host, port_str = arg.rsplit(':', 1)
        return host, int(port_str)
    return arg, default_port


def main() -> None:
    parser = argparse.ArgumentParser(description='Poll a plant continuously')
    parser.add_argument(
        'driver', help='Driver name (solarlog, sma, meteocontrol, smartdog)'
    )
    parser.add_argument(
        'host', help='Device IP address or hostname, optionally with port (host:port)'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=60.0,
        help='Seconds between reads (default 60)',
    )
    args = parser.parse_args()

    host, port = parse_host_port(args.host)
    logger.info('Connecting to %s at %s:%d', args.driver, host, port)

    with get_interface(args.driver, host, port=port) as iface:
        for result in stream(iface, interval_s=args.interval):
            if isinstance(result, Exception):
                logger.error('Read failed: %s', result)
                continue

            ds = result.dataset
            nb = f'{ds.limitation_nb_percent:.1f}%' if ds.limitation_nb_percent is not None else 'None'
            dv = f'{ds.limitation_dv_percent:.1f}%' if ds.limitation_dv_percent is not None else 'None'
            logger.info(
                '[%s  %.3fs]  prod=%dW  cons=%dW  grid=%+dW  nb=%s  dv=%s',
                result.read_at.strftime('%H:%M:%S'),
                result.elapsed_s,
                ds.production,
                ds.consumption,
                ds.grid_feed,
                nb,
                dv,
            )


if __name__ == '__main__':
    main()
