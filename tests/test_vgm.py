import pytest

from main import PCMWriteWait, Wait4Bit


def test_PCMWriteWait():
    assert PCMWriteWait(0x80).delay == 0
    assert PCMWriteWait(0x8f).delay == 15
    with pytest.raises(AssertionError):
        PCMWriteWait(0x7f)
    with pytest.raises(AssertionError):
        PCMWriteWait(0x90)


def test_Wait():
    assert Wait4Bit(0x70).delay == 1
    assert Wait4Bit(0x7f).delay == 16
    with pytest.raises(AssertionError):
        Wait4Bit(0x6f)
    with pytest.raises(AssertionError):
        Wait4Bit(0x80)
