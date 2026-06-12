"""Hardware integration tests that require real devices on the network.

Set one or more host variables, then run:
    DV_TEST_SOLARLOG_HOST=192.168.1.100 uv run pytest -m hardware -v

Supported variables:
    DV_TEST_SOLARLOG_HOST
    DV_TEST_SMA_HOST
    DV_TEST_METEOCONTROL_HOST
    DV_TEST_SMARTDOG_HOST

Optional per-driver variables:
    DV_TEST_<DRIVER>_PORT
    DV_TEST_<DRIVER>_SLAVE_ID
    DV_TEST_<DRIVER>_TIMEOUT
    DV_TEST_<DRIVER>_MAX_RETRIES
    DV_TEST_<DRIVER>_RETRY_DELAY
"""

import os
from dataclasses import dataclass

import pytest

from dv_interfaces import DVModbusConfiguration, get_interface
from dv_interfaces.detection import detect_interface

pytestmark = pytest.mark.hardware


@dataclass(frozen=True)
class HardwareTarget:
    driver: str
    env_var: str

    @property
    def env_prefix(self) -> str:
        return f'DV_TEST_{self.driver.upper()}'


TARGETS = (
    HardwareTarget('solarlog', 'DV_TEST_SOLARLOG_HOST'),
    HardwareTarget('sma', 'DV_TEST_SMA_HOST'),
    HardwareTarget('meteocontrol', 'DV_TEST_METEOCONTROL_HOST'),
    HardwareTarget('smartdog', 'DV_TEST_SMARTDOG_HOST'),
)


def _host(env_var: str) -> str:
    host = os.environ.get(env_var)
    if not host:
        pytest.skip(f'{env_var} not set')
    return host


def _port(target: HardwareTarget) -> int:
    return int(os.environ.get(f'{target.env_prefix}_PORT', '502'))


def _modbus_config(target: HardwareTarget) -> DVModbusConfiguration:
    return DVModbusConfiguration.from_env(prefix=target.env_prefix)


def _interface(target: HardwareTarget, host: str):
    return get_interface(
        target.driver,
        host,
        port=_port(target),
        modbus_config=_modbus_config(target),
    )


@pytest.fixture(params=TARGETS, ids=lambda target: target.driver)
def hardware_target(request) -> tuple[HardwareTarget, str]:
    target = request.param
    return target, _host(target.env_var)


def test_ping(hardware_target):
    target, host = hardware_target
    assert _interface(target, host).ping() is True


def test_read_dataset_result_contract(hardware_target):
    target, host = hardware_target

    with _interface(target, host) as iface:
        result = iface.read_dataset_result()

    assert result.interface == target.driver
    assert result.host == host
    assert result.elapsed_s >= 0
    assert result.dataset.production >= 0
    assert result.dataset.consumption >= 0
    assert isinstance(result.dataset.grid_feed, int)

    flat = result.to_dict()
    assert 'production' in flat
    assert 'grid_feed' in flat
    assert 'read_at' in flat


def test_detection_finds_expected_driver(hardware_target):
    target, host = hardware_target

    candidates = detect_interface(host, ports=(_port(target),))

    assert candidates
    assert candidates[0].driver == target.driver


def test_capability_flags_match_watt_limit_support(hardware_target):
    target, host = hardware_target

    with _interface(target, host) as iface:
        assert iface.supports_dv_percent_limit is True
        assert iface.supports_dv_watt_limit is (
            target.driver in {'meteocontrol', 'smartdog'}
        )


def test_solarlog_extended_reads():
    target = TARGETS[0]
    with _interface(target, _host(target.env_var)) as iface:
        assert isinstance(iface.status(), int)
        assert isinstance(iface.read_possible_production_w(), int)
        assert isinstance(iface.read_battery_charge_w(), int)
        assert isinstance(iface.read_battery_discharge_w(), int)


def test_sma_extended_reads():
    target = TARGETS[1]
    with _interface(target, _host(target.env_var)) as iface:
        freq = iface.read_grid_frequency_hz()
        soc = iface.read_battery_soc_percent()

    assert freq is None or 45.0 <= freq <= 65.0
    assert soc is None or 0 <= soc <= 100


def test_smartdog_extended_reads():
    target = TARGETS[3]
    with _interface(target, _host(target.env_var)) as iface:
        dv_w = iface.read_limitation_dv_w()
        soc = iface.read_battery_soc_percent()

    assert dv_w is None or isinstance(dv_w, float)
    assert soc is None or 0 <= soc <= 100
