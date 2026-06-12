"""Tests for driver detection without requiring real hardware."""

from unittest.mock import MagicMock, patch

import pytest
from pymodbus.exceptions import ModbusException

from dv_interfaces.detection import detect_interface


def test_unreachable_host_returns_empty():
    with patch('dv_interfaces.detection._tcp_reachable', return_value=False):
        result = detect_interface('10.0.0.1')
    assert result == []


def test_returns_candidate_when_probe_succeeds():
    with (
        patch('dv_interfaces.detection._tcp_reachable', return_value=True),
        patch('dv_interfaces.drivers.solarlog.Solarlog._probe', return_value=2),
        patch('dv_interfaces.drivers.sma.Sma._probe', return_value=0),
    ):
        result = detect_interface('10.0.0.1', ports=(502,))
    assert len(result) == 1
    assert result[0].driver == 'solarlog'
    assert result[0].port == 502
    assert result[0].confidence == 2


def test_sorted_by_confidence_descending():
    with (
        patch('dv_interfaces.detection._tcp_reachable', return_value=True),
        patch('dv_interfaces.drivers.solarlog.Solarlog._probe', return_value=1),
        patch('dv_interfaces.drivers.sma.Sma._probe', return_value=2),
    ):
        result = detect_interface('10.0.0.1', ports=(502,))
    assert len(result) == 2
    assert result[0].driver == 'sma'
    assert result[0].confidence == 2
    assert result[1].driver == 'solarlog'
    assert result[1].confidence == 1


def test_probes_all_given_ports():
    probed = []

    def _reachable(host, port, timeout):
        probed.append(port)
        return False

    with patch('dv_interfaces.detection._tcp_reachable', side_effect=_reachable):
        detect_interface('10.0.0.1', ports=(502, 5020))
    assert sorted(probed) == [502, 5020]


def test_zero_confidence_excluded():
    with (
        patch('dv_interfaces.detection._tcp_reachable', return_value=True),
        patch('dv_interfaces.drivers.solarlog.Solarlog._probe', return_value=0),
        patch('dv_interfaces.drivers.sma.Sma._probe', return_value=0),
        patch('dv_interfaces.drivers.meteocontrol.Meteocontrol._probe', return_value=0),
        patch('dv_interfaces.drivers.smartdog.Smartdog._probe', return_value=0),
    ):
        result = detect_interface('10.0.0.1', ports=(502,))
    assert result == []


def _probe_response(is_error: bool = False):
    response = MagicMock()
    response.isError.return_value = is_error
    return response


def test_shared_probe_scores_successful_registers():
    from dv_interfaces.drivers.sma import Sma

    client = MagicMock()
    client.connect.return_value = True
    client.read_input_registers.side_effect = [
        _probe_response(),
        _probe_response(is_error=True),
    ]

    with patch.object(Sma, '_make_probe_client', return_value=client):
        score = Sma._probe('10.0.0.1', 502, 2.0)

    assert score == 1
    assert client.read_input_registers.call_args_list[0].args == (30201,)
    assert client.read_input_registers.call_args_list[0].kwargs == {
        'count': 2,
        'device_id': 2,
    }
    assert client.read_input_registers.call_args_list[1].args == (30775,)
    client.close.assert_called_once_with()


def test_shared_probe_uses_override_slave_id():
    from dv_interfaces.drivers.solarlog import Solarlog

    client = MagicMock()
    client.connect.return_value = True
    client.read_input_registers.return_value = _probe_response()

    with patch.object(Solarlog, '_make_probe_client', return_value=client):
        score = Solarlog._probe('10.0.0.1', 502, 2.0, slave_id=7)

    assert score == 2
    assert client.read_input_registers.call_args_list[0].kwargs['device_id'] == 7
    assert client.read_input_registers.call_args_list[1].kwargs['device_id'] == 7


def test_shared_probe_returns_zero_when_connection_fails():
    from dv_interfaces.drivers.smartdog import Smartdog

    client = MagicMock()
    client.connect.return_value = False

    with patch.object(Smartdog, '_make_probe_client', return_value=client):
        score = Smartdog._probe('10.0.0.1', 502, 2.0)

    assert score == 0
    client.read_holding_registers.assert_not_called()
    client.close.assert_called_once_with()


@pytest.mark.parametrize(
    'exc', [OSError('network'), TimeoutError('timeout'), ModbusException('modbus')]
)
def test_shared_probe_returns_zero_for_expected_probe_failures(exc):
    from dv_interfaces.drivers.solarlog import Solarlog

    client = MagicMock()
    client.connect.return_value = True
    client.read_input_registers.side_effect = exc

    with patch.object(Solarlog, '_make_probe_client', return_value=client):
        score = Solarlog._probe('10.0.0.1', 502, 2.0)

    assert score == 0
    client.close.assert_called_once_with()


def test_shared_probe_does_not_hide_programming_errors():
    from dv_interfaces.drivers.solarlog import Solarlog

    client = MagicMock()
    client.connect.return_value = True
    client.read_input_registers.side_effect = TypeError('bad call')

    with (
        patch.object(Solarlog, '_make_probe_client', return_value=client),
        pytest.raises(TypeError, match='bad call'),
    ):
        Solarlog._probe('10.0.0.1', 502, 2.0)

    client.close.assert_called_once_with()
