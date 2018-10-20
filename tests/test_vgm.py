import pytest

from vgmviz.vgm import PCMWriteWait, Wait4Bit


def test_PCMWriteWait():
    assert PCMWriteWait.decode(None, 0x80).delay == 0
    assert PCMWriteWait.decode(None, 0x8f).delay == 15
    # I "trust" register_cmd2event() to not register PCMWriteWait for invalid commands.


def test_Wait():
    assert Wait4Bit.decode(None, 0x70).delay == 1
    assert Wait4Bit.decode(None, 0x7f).delay == 16
    # I "trust" register_cmd2event() to not register Wait4Bit for invalid commands.
