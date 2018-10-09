from typing import Union, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vgmviz.vgm import YM2612Port0, YM2612Port1


# Parameters
DetHarm = 0x30  # 4-bit detune (sign-mag), 4-bit harmonic#
Ampl = 0x40  # 7-bit oscillator amplitude, in units of -0.75dB
TrebAttack = 0x50  # 2-bit treble speed-boost... 5-bit attack rate
AMDecay1 = 0x60  # 1-bit AM enable... 5-bit decay1 rate
Decay2 = 0x70  # ... 5-bit decay2 rate
KneeRelease = 0x80  # 4-bit knee amplitude (-3dB), 4-bit release rate (,*2+1)

""" YM2612 register address:
Bit field: pppp oo cc
Note that operators are larger than channels.
"""


def ym2612_pack(param, chan, op):
    assert param % 0x10 == 0
    assert 0 <= chan < 3
    assert 0 <= op < 4
    return param + op * 4 + chan


def ym2612_unpack(register):
    param = register & 0xF0
    chan = register & 0x03
    op = (register // 4) & 0x03
    return param, chan, op


class _Wildcard:
    def __eq__(self, other):
        return True


_wildcard = _Wildcard()

_Event = Union['YM2612Port0', 'YM2612Port1']


def ym2612_filter(param=_wildcard, chan=_wildcard, op=_wildcard) -> \
        Callable[[_Event], bool]:
    query = (param, chan, op)

    def cond(e: _Event):
        return ym2612_unpack(e.reg) == query

    return cond
