from typing import Union, Callable

from vgmviz import vgm

# Parameters

DetHarm = 0x30  # 4-bit detune (sign-mag), 4-bit harmonic#
Ampl = 0x40  # 7-bit oscillator amplitude, in units of -0.75dB
TrebAttack = 0x50  # 2-bit treble speed-boost... 5-bit attack rate
AMDecay1 = 0x60  # 1-bit AM enable... 5-bit decay1 rate
Decay2 = 0x70  # ... 5-bit decay2 rate
KneeRelease = 0x80  # 4-bit knee amplitude (-3dB), 4-bit release rate (,*2+1)

""" YM2612 register address:
Bit field: 4param, 2op, 2chan
Note that the order "feels" reversed (compare to channel, operator, param).

- Each YM2612 port has 3 channels only.
- There are 2 YM2612 ports. Port0 accesses 0..2 and Port1 accesses 3..5.
"""


def reg_pack(chan, op, param):
    assert 0 <= chan < 3
    assert 0 <= op < 4
    assert param % 0x10 == 0
    return param + (4 * op) + chan


def reg_unpack(register):
    chan = register & 0x03
    op = (register // 4) & 0x03
    param = register & 0xF0
    return chan, op, param  # TODO add dataclass for chan,op,param


class _Wildcard:
    def __eq__(self, other):
        return True


_wildcard = _Wildcard()

_Event = Union['vgm.YM2612Port0', 'vgm.YM2612Port1']


def reg_filter(chan=_wildcard, op=_wildcard, param=_wildcard) -> \
        Callable[[_Event], bool]:
    """ Passed into filter_ev. """
    query = (chan, op, param)

    def cond(e: _Event):
        return reg_unpack(e.reg) == query

    return cond


def ev_unpack(e: _Event):
    chan, op, param = reg_unpack(e.reg)

    # YM2612 Port 1 accesses channels 3..5.
    if isinstance(e, vgm.YM2612Port1):
        chan += 3

    return (chan, op, param), e.value
