from typing import Union, Callable

from dataclasses import dataclass, replace

from vgmviz import vgm

# Based off documentation at https://www.smspower.org/maxim/Documents/YM2612

# Parameters (4op per channel)

DetHarm = 0x30  # 4-bit detune (sign-mag), 4-bit harmonic multiple
Ampl = 0x40  # 7-bit oscillator amplitude, in units of -0.75dB
TrebAttack = 0x50  # 2-bit treble speed-boost... 5-bit attack rate
AMDecay1 = 0x60  # 1-bit AM enable... 5-bit decay1 rate
Decay2 = 0x70  # ... 5-bit decay2 rate
KneeRelease = 0x80  # 4-bit knee amplitude (-3dB), 4-bit release rate (,*2+1)
SSGEnvelope = 0x90  # SSG envelope (unknown)

# Parameters (1 per channel)
BEGIN_1OP = 0xB0
FeedbackAlgo = 0xB0  # ... 3-bit op0 feedback, 3-bit algorithm

""" YM2612 register address:
Bit field: 4param, 2op, 2chan
Note that the order "feels" reversed (compare to channel, operator, param).

- Each YM2612 port has 3 channels only.
- There are 2 YM2612 ports. Port0 accesses 0..2 and Port1 accesses 3..5.
"""


class _Wildcard:
    def __eq__(self, other):
        return True


_wildcard = _Wildcard()


@dataclass
class Register:
    chan: int
    op: int
    param: int


@dataclass
class UnpackedEvent:
    unpack: Register
    value: int


# Pack and unpack registers

def reg_pack(reg: Register) -> int:
    assert 0 <= reg.chan < 3

    if reg.param >= BEGIN_1OP:
        assert reg.op == 0
        assert reg.param % 0x4 == 0
    else:
        assert 0 <= reg.op < 4
        assert reg.param % 0x10 == 0

    return reg.param + (4 * reg.op) + reg.chan


def reg_unpack(register: int) -> Register:
    if register > BEGIN_1OP:
        param = register & (~0x03)
        op = 0
    else:
        param = register & 0xF0
        op = (register // 4) & 0x03
    chan = register & 0x03

    return Register(chan, op, param)


# Map register type

_SinglePortEvent = Union['vgm.YM2612Port0', 'vgm.YM2612Port1']
_Event = Union[_SinglePortEvent, UnpackedEvent]


def ev_unpack(e: _SinglePortEvent) -> UnpackedEvent:
    """ Input: YM2612PortX with numeric register field
    Output: UnpackedEvent holding unpack=Register object

    Port0 maps to channels 0..2, Port1 maps to channels 3..5.

    Function is passed into map_ev. """

    unpack = reg_unpack(e.reg)

    # YM2612 Port 1 accesses channels 3..5.
    if isinstance(e, vgm.YM2612Port1):
        unpack = replace(unpack, chan = unpack.chan + 3)

    return UnpackedEvent(unpack, e.value)


# Filter by register type

def reg_filter(chan=_wildcard, op=_wildcard, param=_wildcard) -> \
        Callable[[_Event], bool]:
    """ Passed into filter_ev. """

    # noinspection PyTypeChecker
    query = Register(chan, op, param)   # type: ignore

    def cond(e: _Event):
        return reg_unpack(e.reg) == query

    return cond
