"""Tests for dv_interfaces.utils: stream."""

from itertools import islice
from unittest.mock import MagicMock, patch

from dv_interfaces.base_interface import DVDataset, DVReadResult
from dv_interfaces.modbus import DVModbusConfiguration
from dv_interfaces.utils import stream


def _dataset(**kwargs):
    defaults = dict(production=5000, consumption=1200, grid_feed=3800)
    return DVDataset(**{**defaults, **kwargs})


def _result(**kwargs) -> DVReadResult:
    return DVReadResult(
        interface='solarlog',
        host='192.168.1.1',
        elapsed_s=0.1,
        dataset=_dataset(),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------


class TestStream:
    def _mock_iface(self, results):
        iface = MagicMock()
        iface.read_dataset_result.side_effect = results
        return iface

    def test_yields_results(self):
        r = _result()
        iface = self._mock_iface([r, r, r])
        items = list(islice(stream(iface), 3))
        assert len(items) == 3
        assert all(isinstance(i, DVReadResult) for i in items)

    def test_yields_exception_on_error(self):
        exc = RuntimeError('read failed')
        iface = self._mock_iface([exc])
        items = list(islice(stream(iface), 1))
        assert len(items) == 1
        assert isinstance(items[0], Exception)
        assert str(items[0]) == 'read failed'

    def test_continues_after_error(self):
        r = _result()
        exc = RuntimeError('oops')
        iface = self._mock_iface([exc, r, r])
        items = list(islice(stream(iface), 3))
        assert isinstance(items[0], Exception)
        assert isinstance(items[1], DVReadResult)
        assert isinstance(items[2], DVReadResult)

    def test_no_sleep_when_interval_zero(self):
        r = _result()
        iface = self._mock_iface([r])
        with patch('dv_interfaces.utils.time') as mock_time:
            list(islice(stream(iface, interval_s=0.0), 1))
            mock_time.sleep.assert_not_called()

    def test_sleeps_between_reads(self):
        r = _result()
        iface = self._mock_iface([r, r, r])
        with patch('dv_interfaces.utils.time') as mock_time:
            list(islice(stream(iface, interval_s=5.0), 3))
            # sleep runs after each yield; with 3 reads islice cuts off before the 3rd sleep
            assert mock_time.sleep.call_count == 2
            mock_time.sleep.assert_called_with(5.0)


# ---------------------------------------------------------------------------
# DVModbusConfiguration.from_env()
# ---------------------------------------------------------------------------


class TestDVModbusConfigurationFromEnv:
    def test_defaults_when_no_env(self, monkeypatch):
        for var in ('DV_SLAVE_ID', 'DV_TIMEOUT', 'DV_MAX_RETRIES', 'DV_RETRY_DELAY'):
            monkeypatch.delenv(var, raising=False)
        cfg = DVModbusConfiguration.from_env()
        assert cfg.slave_id == 1
        assert cfg.timeout == 5.0
        assert cfg.max_retries == 0
        assert cfg.retry_delay == 0.2

    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv('DV_SLAVE_ID', '5')
        monkeypatch.setenv('DV_TIMEOUT', '15.0')
        monkeypatch.setenv('DV_MAX_RETRIES', '3')
        monkeypatch.setenv('DV_RETRY_DELAY', '1.0')
        cfg = DVModbusConfiguration.from_env()
        assert cfg.slave_id == 5
        assert cfg.timeout == 15.0
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 1.0

    def test_custom_prefix(self, monkeypatch):
        monkeypatch.setenv('MY_SLAVE_ID', '10')
        monkeypatch.delenv('DV_SLAVE_ID', raising=False)
        cfg = DVModbusConfiguration.from_env(prefix='MY')
        assert cfg.slave_id == 10
