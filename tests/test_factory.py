"""Tests for get_interface() and list_interfaces() factory functions."""

import pytest

import dv_interfaces
from dv_interfaces import get_interface, list_interfaces
from dv_interfaces.drivers.meteocontrol import Meteocontrol
from dv_interfaces.drivers.sma import Sma
from dv_interfaces.drivers.smartdog import Smartdog
from dv_interfaces.drivers.solarlog import Solarlog
from dv_interfaces.modbus import DVInterfaceModbusBase, DVModbusConfiguration


def test_list_interfaces_returns_all_drivers():
    names = {entry['name'] for entry in list_interfaces()}
    assert names == {'solarlog', 'sma', 'meteocontrol', 'smartdog'}


def test_list_interfaces_has_description():
    for entry in list_interfaces():
        assert 'name' in entry
        assert 'description' in entry
        assert entry['description']


@pytest.mark.parametrize(
    'name,cls',
    [
        ('solarlog', Solarlog),
        ('sma', Sma),
        ('meteocontrol', Meteocontrol),
        ('smartdog', Smartdog),
    ],
)
def test_get_interface_returns_correct_type(name, cls):
    iface = get_interface(name, '127.0.0.1')
    assert isinstance(iface, cls)


def test_get_interface_unknown_raises():
    with pytest.raises(ValueError, match='Unknown interface'):
        get_interface('unknown_driver', '127.0.0.1')


def test_get_interface_modbus_config_dict_passed():
    iface = get_interface('solarlog', '127.0.0.1', modbus_config={'slave_id': 5})
    assert isinstance(iface, DVInterfaceModbusBase)
    assert iface.modbus_config.slave_id == 5


def test_get_interface_modbus_config_model_passed():
    cfg = DVModbusConfiguration(slave_id=5, timeout=10.0)
    iface = get_interface('solarlog', '127.0.0.1', modbus_config=cfg)
    assert isinstance(iface, DVInterfaceModbusBase)
    assert iface.modbus_config == cfg


def test_get_interface_model_without_slave_id_uses_driver_default():
    cfg = DVModbusConfiguration(timeout=10.0)
    iface = get_interface('sma', '127.0.0.1', modbus_config=cfg)
    assert isinstance(iface, DVInterfaceModbusBase)
    assert iface.modbus_config.slave_id == 2
    assert iface.modbus_config.timeout == 10.0


def test_get_interface_invalid_modbus_config_raises():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        get_interface('solarlog', '127.0.0.1', modbus_config={'slave_id': 999})


def test_version_available():
    assert dv_interfaces.__version__
