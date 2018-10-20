import io

import pytest
from vgmviz.pointer import Pointer, Writer


@pytest.fixture
def ptr():
    data = bytes.fromhex('0001 7e7f 8081 feff')
    # visited = [Visit.NONE] * len(data)  # zzzz: bad API

    return Pointer.create(data, 'big')


@pytest.fixture
def wrt():
    return Writer(io.BytesIO(), 'big')


def test_unsigned(ptr):
    assert ptr.addr == 0

    assert ptr.u8() == 0x00
    assert ptr.u24() == 0x017e7f
    assert ptr.u32() == 0x8081feff

    assert ptr.addr == 8


def test_signed(ptr):
    assert ptr.s32() == 0x00017e7f
    assert ptr.s24() == 0x8081fe - 0x1000000
    assert ptr.s8() == 0xff - 0x100


def test_offset(ptr):
    # Pointer.offset() is a signed int32, for VGM file format.

    assert ptr.offset() == 0x00017e7f
    assert ptr.offset() + 2**32 == 0x8081feff + 0x04

    assert ptr.offset(0) == 0x00017e7f


def test_error(ptr):
    # Mark everything as visited, to trigger OverlapError.
    for i in range(8):
        ptr.u8()

    with pytest.raises(ValueError):
        ptr.u8()


def test_eof(ptr):
    ptr.seek(3)
    assert ptr.addr == 3

    ptr.seek_rel(2)
    assert ptr.addr == 5

    # EOF
    with pytest.raises(ValueError):
        ptr.s32()

    ptr.s8()
    with pytest.raises(ValueError):
        ptr.s24()

    ptr.s8()
    with pytest.raises(ValueError):
        ptr.s16()

    ptr.s8()
    with pytest.raises(ValueError):
        ptr.s8()


# Writer tests

def test_write_offset(wrt):
    # Pointer.offset() is a signed int32, for VGM file format.

    def buf():
        return bytes(wrt.file.getbuffer())

    wrt.offset(0)
    assert buf() == b'\x00\x00\x00\x00'

    wrt.offset(0)
    assert buf()[4:] == b'\xFF\xFF\xFF\xFC'

    # wrt.file.seek(0)
    # wrt.file.truncate(0)
    #

    wrt.offset(0x100, addr=0)
    assert b'\x00\x00\x01\x00' == buf()[:4]

    wrt.offset(0x180, addr=0x100)
    assert b'\x00\x00\x00\x80' == buf()[0x100:]
