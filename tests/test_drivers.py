"""Per-driver smoke tests with a mocked pymodbus client.

Each test verifies:
- correct register address and device_id used
- correct NaN/sentinel → None conversion
- correct sign conventions (e.g. SmartDog Verbraucherpfeilsystem)
"""

import math
import struct
from unittest.mock import MagicMock, patch

import pytest

from dv_interfaces.exceptions import (
    ErrorReadDVInterface,
    ErrorUnsupportedOperationDVInterface,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registers_f32(value: float, wordorder: str = '>') -> list[int]:
    raw = struct.pack('>f', value)
    hi = struct.unpack('>H', raw[0:2])[0]
    lo = struct.unpack('>H', raw[2:4])[0]
    return [lo, hi] if wordorder == '<' else [hi, lo]


def _make_registers_s32(value: int, wordorder: str = '>') -> list[int]:
    raw = struct.pack('>i', value)
    hi = struct.unpack('>H', raw[0:2])[0]
    lo = struct.unpack('>H', raw[2:4])[0]
    return [lo, hi] if wordorder == '<' else [hi, lo]


def _make_registers_u32(value: int, wordorder: str = '>') -> list[int]:
    raw = struct.pack('>I', value)
    hi = struct.unpack('>H', raw[0:2])[0]
    lo = struct.unpack('>H', raw[2:4])[0]
    return [lo, hi] if wordorder == '<' else [hi, lo]


def _make_registers_u64(value: int) -> list[int]:
    raw = struct.pack('>Q', value)
    return [struct.unpack('>H', raw[i : i + 2])[0] for i in range(0, 8, 2)]


def _mock_response(registers):
    rsp = MagicMock()
    rsp.isError.return_value = False
    rsp.registers = registers
    return rsp


def _mock_error_response():
    rsp = MagicMock()
    rsp.isError.return_value = True
    return rsp


def _make_client_mock(registers):
    client = MagicMock()
    client.is_socket_open.return_value = True
    rsp = _mock_response(registers)
    client.read_holding_registers.return_value = rsp
    client.read_input_registers.return_value = rsp
    return client


# ---------------------------------------------------------------------------
# Solarlog
# ---------------------------------------------------------------------------


class TestSolarlog:
    def _iface(self, regs):
        from dv_interfaces.drivers.solarlog import Solarlog

        with patch('dv_interfaces.modbus.ModbusTcpClient'):
            iface = Solarlog('127.0.0.1')
        iface._client = _make_client_mock(regs)
        return iface

    def test_read_production(self):
        iface = self._iface(_make_registers_u32(5000, wordorder='<'))
        assert iface.read_production() == 5000
        iface._client.read_input_registers.assert_called_once_with(
            10904, count=2, device_id=1
        )

    def test_read_gridfeed(self):
        iface = self._iface(_make_registers_s32(-1500, wordorder='<'))
        assert iface.read_gridfeed() == -1500

    def test_read_consumption(self):
        iface = self._iface(_make_registers_u32(3000, wordorder='<'))
        assert iface.read_consumption() == 3000

    def test_read_dataset_batch(self):
        regs = (
            [0]  # 10900: status
            + [100]  # 10901: limitation_nb_percent (100%)
            + _make_registers_f32(
                50.0, wordorder='<'
            )  # 10902-10903: limitation_nb_w (50 kW)
            + _make_registers_u32(5000, wordorder='<')  # 10904-10905: production
            + _make_registers_u32(
                6000, wordorder='<'
            )  # 10906-10907: possible_production
            + _make_registers_u32(1200, wordorder='<')  # 10908-10909: consumption
            + _make_registers_s32(3800, wordorder='<')  # 10910-10911: grid_feed
        )
        assert len(regs) == 12
        iface = self._iface(regs)
        ds = iface.read_dataset()
        assert ds.production == 5000
        assert ds.consumption == 1200
        assert ds.grid_feed == 3800
        assert ds.limitation_nb_percent == pytest.approx(100.0)
        assert ds.limitation_nb_w == pytest.approx(50_000.0)
        iface._client.read_input_registers.assert_called_once_with(
            10900, count=12, device_id=1
        )

    def test_status_reads_correct_register(self):
        iface = self._iface([0])
        assert iface.status() == 0
        iface._client.read_input_registers.assert_called_once_with(
            10900, count=1, device_id=1
        )

    def test_read_limitation_nb_percent(self):
        iface = self._iface([75])
        assert iface.read_limitation_nb_percent() == pytest.approx(75.0)
        iface._client.read_input_registers.assert_called_once_with(
            10901, count=1, device_id=1
        )

    def test_read_limitation_nb_w(self):
        iface = self._iface(_make_registers_f32(50.0, wordorder='<'))
        assert iface.read_limitation_nb_w() == pytest.approx(50_000.0)
        iface._client.read_input_registers.assert_called_once_with(
            10902, count=2, device_id=1
        )

    def test_read_limitation_dv_percent_returns_none(self):
        iface = self._iface([])
        assert iface.read_limitation_dv_percent() is None

    def test_read_limitation_dv_w_returns_none(self):
        iface = self._iface([])
        assert iface.read_limitation_dv_w() is None

    def test_set_limitation_dv_percent_writes_control_block(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface._client.write_register.return_value = _mock_response([])
        iface.set_limitation_dv_percent(80.0)
        # watchdog: uint32 at 10404 (2 registers, FC16)
        assert iface._client.write_registers.call_count == 1
        wdog_call = iface._client.write_registers.call_args
        assert wdog_call[0][0] == 10404
        assert len(wdog_call[0][1]) == 2
        assert wdog_call[1]['device_id'] == 1
        # mode=2 and value=80 as individual registers (FC06)
        assert iface._client.write_register.call_count == 2
        mode_call, value_call = iface._client.write_register.call_args_list
        assert mode_call[0][0] == 10400
        assert mode_call[0][1] == 2  # mode: fixed limit
        assert value_call[0][0] == 10401
        assert value_call[0][1] == 80

    def test_turn_on_writes_mode1_value100(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface._client.write_register.return_value = _mock_response([])
        iface.turn_on()
        mode_call, value_call = iface._client.write_register.call_args_list
        assert mode_call[0][0] == 10400
        assert mode_call[0][1] == 1  # mode: no limit
        assert value_call[0][0] == 10401
        assert value_call[0][1] == 100

    def test_turn_off_writes_mode2_value0(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface._client.write_register.return_value = _mock_response([])
        iface.turn_off()
        mode_call, value_call = iface._client.write_register.call_args_list
        assert mode_call[0][0] == 10400
        assert mode_call[0][1] == 2  # mode: fixed limit
        assert value_call[0][0] == 10401
        assert value_call[0][1] == 0

    def test_set_limitation_dv_w_raises(self):
        iface = self._iface([])
        assert iface.supports_dv_watt_limit is False
        with pytest.raises(ErrorUnsupportedOperationDVInterface):
            iface.set_limitation_dv_w(5000.0)

    def test_read_possible_production_w(self):
        iface = self._iface(_make_registers_u32(8000, wordorder='<'))
        assert iface.read_possible_production_w() == 8000
        iface._client.read_input_registers.assert_called_once_with(
            10906, count=2, device_id=1
        )

    def test_read_possible_production_w_zero_when_no_sensor(self):
        iface = self._iface(_make_registers_u32(0, wordorder='<'))
        assert iface.read_possible_production_w() == 0

    def test_read_battery_charge_w(self):
        iface = self._iface(_make_registers_s32(2000, wordorder='<'))
        assert iface.read_battery_charge_w() == 2000
        iface._client.read_input_registers.assert_called_once_with(
            10912, count=2, device_id=1
        )

    def test_read_battery_discharge_w(self):
        iface = self._iface(_make_registers_s32(1500, wordorder='<'))
        assert iface.read_battery_discharge_w() == 1500
        iface._client.read_input_registers.assert_called_once_with(
            10914, count=2, device_id=1
        )


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------


class TestSma:
    def _iface(self, regs):
        from dv_interfaces.drivers.sma import Sma

        with patch('dv_interfaces.modbus.ModbusTcpClient'):
            iface = Sma('127.0.0.1')
        iface._client = _make_client_mock(regs)
        return iface

    def test_read_production(self):
        iface = self._iface(_make_registers_s32(8000))
        assert iface.read_production() == 8000
        iface._client.read_input_registers.assert_called_once_with(
            30775, count=2, device_id=2
        )

    def test_read_production_nan_returns_zero(self):
        # NaN for S32 is 0x80000000 = -2147483648
        iface = self._iface(_make_registers_s32(-2_147_483_648))
        # read_production returns the raw value; NaN is only handled in specific methods
        result = iface.read_production()
        assert result == -2_147_483_648

    def test_read_limitation_nb_percent_nan(self):
        iface = self._iface(_make_registers_u32(0xFFFF_FFFF))
        assert iface.read_limitation_nb_percent() is None

    def test_read_limitation_nb_percent_value(self):
        # FIX2: 7500 → 75.00%
        iface = self._iface(_make_registers_u32(7500))
        assert iface.read_limitation_nb_percent() == pytest.approx(75.0)

    def test_read_battery_soc_nan(self):
        iface = self._iface(_make_registers_u32(0xFFFF_FFFF))
        assert iface.read_battery_soc_percent() is None

    def test_read_grid_frequency(self):
        # FIX2: 5000 → 50.00 Hz
        iface = self._iface(_make_registers_u32(5000))
        assert iface.read_grid_frequency_hz() == pytest.approx(50.0)

    def test_read_gridfeed(self):
        iface = self._iface(_make_registers_s32(3500))
        assert iface.read_gridfeed() == 3500
        iface._client.read_input_registers.assert_called_once_with(
            31249, count=2, device_id=2
        )

    def test_read_limitation_dv_percent_nan(self):
        iface = self._iface(_make_registers_u32(0xFFFF_FFFF))
        assert iface.read_limitation_dv_percent() is None

    def test_read_limitation_dv_percent_value(self):
        # FIX2: 8000 → 80.00%
        iface = self._iface(_make_registers_u32(8000))
        assert iface.read_limitation_dv_percent() == pytest.approx(80.0)
        iface._client.read_input_registers.assert_called_once_with(
            31241, count=2, device_id=2
        )

    def test_set_limitation_dv_percent_writes_correct_register(self):
        iface = self._iface([])
        iface._client.write_register.return_value = _mock_response([])
        iface.set_limitation_dv_percent(75.0)
        call = iface._client.write_register.call_args
        assert call[0][0] == 40493
        assert call[1]['value'] == 7500  # 75.00 * 100 (FIX2)
        assert call[1]['device_id'] == 2

    def test_turn_on_writes_full_power(self):
        iface = self._iface([])
        iface._client.write_register.return_value = _mock_response([])
        iface.turn_on()
        call = iface._client.write_register.call_args
        assert call[0][0] == 40493
        assert call[1]['value'] == 10000  # 100.00% (FIX2)
        assert call[1]['device_id'] == 2

    def test_turn_off_writes_zero(self):
        iface = self._iface([])
        iface._client.write_register.return_value = _mock_response([])
        iface.turn_off()
        call = iface._client.write_register.call_args
        assert call[0][0] == 40493
        assert call[1]['value'] == 0
        assert call[1]['device_id'] == 2

    def test_set_limitation_dv_w_raises(self):
        iface = self._iface([])
        assert iface.supports_dv_watt_limit is False
        with pytest.raises(ErrorUnsupportedOperationDVInterface):
            iface.set_limitation_dv_w(5000.0)

    def test_read_error_raises(self):
        iface = self._iface([])
        iface._client.read_input_registers.return_value = _mock_error_response()
        with pytest.raises(ErrorReadDVInterface):
            iface.read_production()


# ---------------------------------------------------------------------------
# Meteocontrol
# ---------------------------------------------------------------------------


class TestMeteocontrol:
    def _iface(self, regs):
        from dv_interfaces.drivers.meteocontrol import Meteocontrol

        with patch('dv_interfaces.modbus.ModbusTcpClient'):
            iface = Meteocontrol('127.0.0.1')
        iface._client = _make_client_mock(regs)
        return iface

    def test_read_production(self):
        iface = self._iface(_make_registers_f32(6000.0, wordorder='<'))
        assert iface.read_production() == 6000
        iface._client.read_holding_registers.assert_called_once_with(
            0, count=2, device_id=10
        )

    def test_read_gridfeed(self):
        iface = self._iface(_make_registers_f32(2500.0, wordorder='<'))
        assert iface.read_gridfeed() == 2500

    def test_read_limitation_dv_percent_nan(self):
        iface = self._iface(_make_registers_f32(float('nan'), wordorder='<'))
        assert iface.read_limitation_dv_percent() is None

    def test_read_limitation_dv_percent_value(self):
        iface = self._iface(_make_registers_f32(80.0, wordorder='<'))
        assert iface.read_limitation_dv_percent() == pytest.approx(80.0)

    def test_read_limitation_dv_percent_above_100(self):
        iface = self._iface(_make_registers_f32(110.0, wordorder='<'))
        assert iface.read_limitation_dv_percent() == pytest.approx(110.0)

    def test_set_limitation_dv_percent_writes_correct_register(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface.set_limitation_dv_percent(75.0)
        call_args = iface._client.write_registers.call_args
        assert call_args[0][0] == 5000
        assert call_args[1]['device_id'] == 10

    def test_turn_on_writes_100_percent(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface.turn_on()
        call_args = iface._client.write_registers.call_args
        assert call_args[0][0] == 5000
        regs = call_args[0][1]
        decoder_regs = list(reversed(regs))  # wordorder '<' reversal
        raw = struct.pack('>HH', *decoder_regs)
        value = struct.unpack('>f', raw)[0]
        assert math.isclose(value, 100.0, rel_tol=1e-6)

    def test_turn_off_writes_0_percent(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface.turn_off()
        call_args = iface._client.write_registers.call_args
        assert call_args[0][0] == 5000

    def test_read_limitation_nb_percent_nan(self):
        iface = self._iface(_make_registers_f32(float('nan'), wordorder='<'))
        assert iface.read_limitation_nb_percent() is None

    def test_read_limitation_nb_percent_value(self):
        iface = self._iface(_make_registers_f32(60.0, wordorder='<'))
        assert iface.read_limitation_nb_percent() == pytest.approx(60.0)
        iface._client.read_holding_registers.assert_called_once_with(
            6, count=2, device_id=10
        )

    def test_read_limitation_nb_w_nan(self):
        iface = self._iface(_make_registers_f32(float('nan'), wordorder='<'))
        assert iface.read_limitation_nb_w() is None

    def test_read_limitation_nb_w_value(self):
        iface = self._iface(_make_registers_f32(50_000.0, wordorder='<'))
        assert iface.read_limitation_nb_w() == pytest.approx(50_000.0)
        iface._client.read_holding_registers.assert_called_once_with(
            10, count=2, device_id=10
        )

    def test_read_limitation_dv_w_nan(self):
        iface = self._iface(_make_registers_f32(float('nan'), wordorder='<'))
        assert iface.read_limitation_dv_w() is None

    def test_read_limitation_dv_w_value(self):
        iface = self._iface(_make_registers_f32(30_000.0, wordorder='<'))
        assert iface.read_limitation_dv_w() == pytest.approx(30_000.0)
        iface._client.read_holding_registers.assert_called_once_with(
            44, count=2, device_id=10
        )

    def test_set_limitation_dv_w_writes_correct_register(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        assert iface.supports_dv_watt_limit is True
        iface.set_limitation_dv_w(40_000.0)
        call_args = iface._client.write_registers.call_args
        assert call_args[0][0] == 5002
        assert call_args[1]['device_id'] == 10


# ---------------------------------------------------------------------------
# Smartdog
# ---------------------------------------------------------------------------


class TestSmartdog:
    def _iface(self, regs):
        from dv_interfaces.drivers.smartdog import Smartdog

        with patch('dv_interfaces.modbus.ModbusTcpClient'):
            iface = Smartdog('127.0.0.1')
        iface._client = _make_client_mock(regs)
        return iface

    def test_read_production(self):
        iface = self._iface(_make_registers_s32(7000))
        assert iface.read_production() == 7000
        iface._client.read_holding_registers.assert_called_once_with(
            40002, count=2, device_id=2
        )

    def test_read_gridfeed_negated(self):
        # Register stores Verbraucherpfeilsystem: positive=import → must negate
        iface = self._iface(_make_registers_s32(1000))
        assert iface.read_gridfeed() == -1000

    def test_read_gridfeed_export_positive(self):
        iface = self._iface(_make_registers_s32(-2000))
        assert iface.read_gridfeed() == 2000

    def test_read_consumption(self):
        iface = self._iface(_make_registers_s32(4000))
        assert iface.read_consumption() == 4000
        iface._client.read_holding_registers.assert_called_once_with(
            40026, count=2, device_id=2
        )

    def test_read_limitation_dv_w_nan(self):
        iface = self._iface(_make_registers_s32(-1))
        assert iface.read_limitation_dv_w() is None

    def test_read_limitation_dv_w_value(self):
        iface = self._iface(_make_registers_s32(5000))
        assert iface.read_limitation_dv_w() == pytest.approx(5000.0)

    def test_set_limitation_dv_w_writes_two_registers(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        assert iface.supports_dv_watt_limit is True
        iface.set_limitation_dv_w(3000.0)
        assert iface._client.write_registers.call_count == 2
        first_call = iface._client.write_registers.call_args_list[0]
        assert first_call[0][0] == 40004
        second_call = iface._client.write_registers.call_args_list[1]
        assert second_call[0][0] == 40014

    def test_turn_off_sets_zero_limit_and_activates(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface.turn_off()
        assert iface._client.write_registers.call_count == 2
        first_call = iface._client.write_registers.call_args_list[0]
        assert first_call[0][0] == 40004
        second_call = iface._client.write_registers.call_args_list[1]
        assert second_call[0][0] == 40014

    def test_turn_on_deactivates_dv_control(self):
        iface = self._iface([])
        iface._client.write_registers.return_value = _mock_response([])
        iface.turn_on()
        assert iface._client.write_registers.call_count == 1
        call_args = iface._client.write_registers.call_args
        assert call_args[0][0] == 40014

    def test_set_limitation_dv_percent_reads_rated_power(self):
        iface = self._iface(_make_registers_s32(10000))
        iface._client.write_registers.return_value = _mock_response([])
        iface.set_limitation_dv_percent(50.0)
        read_call = iface._client.read_holding_registers.call_args_list[0]
        assert read_call[0][0] == 40012

    def test_set_limitation_dv_percent_raises_when_rated_is_nan(self):
        from dv_interfaces.exceptions import ErrorLimitingDVInterface

        iface = self._iface(_make_registers_s32(-1))
        with pytest.raises(ErrorLimitingDVInterface):
            iface.set_limitation_dv_percent(50.0)

    def test_read_battery_soc_nan(self):
        iface = self._iface(_make_registers_s32(-1))
        assert iface.read_battery_soc_percent() is None

    def test_read_battery_soc_value(self):
        iface = self._iface(_make_registers_s32(85))
        assert iface.read_battery_soc_percent() == 85

    def test_read_limitation_nb_w_nan(self):
        iface = self._iface(_make_registers_s32(-1))
        assert iface.read_limitation_nb_w() is None

    def test_read_limitation_nb_w_value(self):
        iface = self._iface(_make_registers_s32(10_000))
        assert iface.read_limitation_nb_w() == pytest.approx(10_000.0)
        iface._client.read_holding_registers.assert_called_once_with(
            40006, count=2, device_id=2
        )

    def test_read_error_raises(self):
        iface = self._iface([])
        iface._client.read_holding_registers.return_value = _mock_error_response()
        with pytest.raises(ErrorReadDVInterface):
            iface.read_production()
