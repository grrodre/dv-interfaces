"""Tests for the pymodbus-backed conversion surface used by drivers."""

import math
import struct
from unittest.mock import MagicMock, patch


def _make_registers(value, fmt: str, wordorder: str = '>') -> list[int]:
    raw = struct.pack(f'>{fmt}', value)
    registers = [struct.unpack('>H', raw[i : i + 2])[0] for i in range(0, len(raw), 2)]
    return list(reversed(registers)) if wordorder == '<' else registers


def _solarlog():
    from dv_interfaces.drivers.solarlog import Solarlog

    with patch('dv_interfaces.modbus.ModbusTcpClient'):
        iface = Solarlog('127.0.0.1')
    iface._client = MagicMock()
    iface._client.is_socket_open.return_value = True
    return iface


def _sma():
    from dv_interfaces.drivers.sma import Sma

    with patch('dv_interfaces.modbus.ModbusTcpClient'):
        iface = Sma('127.0.0.1')
    iface._client = MagicMock()
    iface._client.is_socket_open.return_value = True
    return iface


def test_scalar_decoders_cover_driver_datatypes():
    iface = _sma()

    assert iface._decode_uint16([65535]) == 65535
    assert iface._decode_uint32(_make_registers(0xFFFF_FFFF, 'I')) == 0xFFFF_FFFF
    assert iface._decode_int32(_make_registers(-1500, 'i')) == -1500
    assert (
        iface._decode_uint64(_make_registers(0xFFFF_FFFF_FFFF_FFFF, 'Q'))
        == 0xFFFF_FFFF_FFFF_FFFF
    )
    assert math.isclose(iface._decode_float32(_make_registers(1234.5, 'f')), 1234.5)
    assert math.isnan(iface._decode_float32(_make_registers(float('nan'), 'f')))


def test_little_word_order_decode_and_write():
    iface = _solarlog()
    value = 0x1234_5678

    assert iface._decode_uint32(_make_registers(value, 'I', wordorder='<')) == value

    response = MagicMock()
    response.isError.return_value = False
    iface._client.write_registers.return_value = response
    iface._write_uint32(10404, value)

    assert iface._client.write_registers.call_args.args == (10404, [0x5678, 0x1234])


def test_solarlog_batch_decode_uses_explicit_slices():
    registers = [
        0x0000,  # 10900: status
        0x0064,  # 10901: limitation_nb_percent = 100
        *_make_registers(0.0, 'f', wordorder='<'),
        *_make_registers(0, 'I', wordorder='<'),
        *_make_registers(0, 'I', wordorder='<'),
        *_make_registers(0, 'I', wordorder='<'),
        *_make_registers(224346, 'i', wordorder='<'),
    ]
    iface = _solarlog()

    assert iface._decode_uint16(registers[0:1]) == 0
    assert iface._decode_uint16(registers[1:2]) == 100
    assert iface._decode_float32(registers[2:4]) == 0.0
    assert iface._decode_uint32(registers[4:6]) == 0
    assert iface._decode_uint32(registers[6:8]) == 0
    assert iface._decode_uint32(registers[8:10]) == 0
    assert iface._decode_int32(registers[10:12]) == 224346
