import bisect
import math
from typing import Union, Callable, List, TypeVar, Dict, Optional

from dataclasses import dataclass, replace

from vgmviz import vgm

T = TypeVar('T')


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


@dataclass(frozen=True, order=True)
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

_PackedRegEvent = Union['vgm.YM2612Port0', 'vgm.YM2612Port1']
_Event = Union[_PackedRegEvent, UnpackedEvent]


def ev_unpack(e: _PackedRegEvent) -> UnpackedEvent:
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
# Note: UNUSED

def reg_filter(chan=_wildcard, op=_wildcard, param=_wildcard) -> \
        Callable[[_PackedRegEvent], bool]:
    """ Passed into filter_ev. """

    # noinspection PyTypeChecker
    query = Register(chan, op, param)   # type: ignore

    def cond(e: _PackedRegEvent):
        return reg_unpack(e.reg) == query

    return cond


# Note: mypy doesn't support cross-module generics in a function body.
# vgm.TimedEventList[UnpackedEvent] fails.
TimedEventList = List['vgm.TimedEvent[T]']


def bound_ev_time(
        time_events: 'vgm.TimedEventList[UnpackedEvent]',
        begin=0,
        end=math.inf
) -> 'TimedEventList[UnpackedEvent]':
    """
    Filter by time (seconds).
    For each register ID, prepend the "previous state" at t=begin,
    and append the "ending state" at t=end.
    """

    regs = sorted(set(t_e.event.unpack for t_e in time_events))
    assert len(regs) < 0x100, '256+ registers, did you fail to deduplicate?'

    # O(n) :(
    times = [t_e.time for t_e in time_events]

    i0 = bisect.bisect_left(times, begin)
    i1 = bisect.bisect_left(times, end)

    # Find the "previous state" before t=begin.
    before = time_events[:i0]
    old_reg2event = {}

    for reg in regs:
        old_reg2event[reg] = \
            next((t_e.event for t_e in reversed(before) if t_e.event.unpack == reg),
                 None)

    # Find the "final state" at t=end.
    during = time_events[i0:i1]
    new_reg2event = {}

    for reg in regs:
        new_reg2event[reg] = \
            next((t_e.event for t_e in reversed(during) if t_e.event.unpack == reg),
                 old_reg2event[reg])

    # Prepend old state, append new state.
    if end == math.inf:
        end = times[-1]

    def retime_events(time, reg2event):
        return [vgm.TimedEvent(time, event)
                for event in reg2event.values()
                if event is not None]

    out: TimedEventList[UnpackedEvent] = []
    out += retime_events(begin, old_reg2event)
    out += during
    out += retime_events(end, new_reg2event)
    return out




