from typing import NamedTuple


class _DriverEntry(NamedTuple):
    module: str
    class_name: str
    description: str


_REGISTRY: dict[str, _DriverEntry] = {
    'solarlog': _DriverEntry('dv_interfaces.drivers.solarlog', 'Solarlog', 'SolarLog'),
    'sma': _DriverEntry('dv_interfaces.drivers.sma', 'Sma', 'SMA cluster'),
    'meteocontrol': _DriverEntry(
        'dv_interfaces.drivers.meteocontrol', 'Meteocontrol', "Meteocontrol blue'Log XC"
    ),
    'smartdog': _DriverEntry(
        'dv_interfaces.drivers.smartdog', 'Smartdog', 'ecodata SmartDog'
    ),
}
