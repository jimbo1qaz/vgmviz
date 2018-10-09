import pytest
from utils.pointer import Pointer


# def test_wrap():
#     assert wrap(0, 8) == 0
#     assert wrap(1, 8) == 1
#     assert wrap(128, 8) == -128
#     assert wrap(129, 8) == -127
#
#     assert wrap(0, 16) == 0
#     assert wrap(1, 16) == 1
#     assert wrap(0x8000, 16) == -0x8000
#     assert wrap(0x8001, 16) == -0x7fff


@pytest.fixture
def ptr():
    data = bytes.fromhex('0001 7e7f 8081 feff')
    # visited = [Visit.NONE] * len(data)  # zzzz: bad API

    return Pointer.create(data, 'big')


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
