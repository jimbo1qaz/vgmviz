from typing import Any, List, Callable, Type, TypeVar, Tuple

import dataclasses
from dataclasses import dataclass

from vgmviz.datastruct import DataStruct, EventStruct, cmd2event, register_cmd2event, \
    meta
from vgmviz.pointer import Pointer, Writer


T = TypeVar('T', bound='Event')


class VgmNotImplemented(NotImplementedError):
    pass


LinearEventList = List[EventStruct]  # Consists of events and wait-events.


ENDIAN = 'little'


# Parse VGM

def parse_vgm(path: str) -> Tuple['VgmHeader', LinearEventList]:
    with open(path, 'rb') as f:
        ptr = Pointer(f.read(), 0, ENDIAN)

    header = VgmHeader.decode(ptr)
    events = parse_body(ptr, header)
    return header, events


@dataclass
class VgmHeader(DataStruct):
    nbytes: int = meta('offset', addr=0x04)
    version: int = meta('u32', addr=0x08)
    nsamp: int = meta('u32', addr=0x18)

    ym2612_clock: int = meta('u32', addr=0x2C)

    # default arguments
    data_addr: int = meta('offset', addr=0x34)

    # magic values become default arguments
    magic: bytes = meta('magic', arg=b'Vgm ', addr=0x00)

    @classmethod
    def decode(cls, ptr: Pointer) -> 'VgmHeader':
        # do I also have to call super().decode in superclass? Maybe.
        obj: VgmHeader = super().decode(ptr)

        if obj.version < 0x150:
            obj.data_addr = 0x40

        return obj


def parse_body(ptr: Pointer, header: VgmHeader) -> LinearEventList:
    events: LinearEventList = []

    ptr.seek(header.data_addr)
    while True:
        assert ptr.addr < header.nbytes
        command = ptr.u8()

        if command == 0x66:
            # assertion fails
            # assert ptr.addr == header.nbytes, \
            #     f"ptr.addr={ptr.addr} doesn't match header.nbytes={header.nbytes}"
            break

        if command in cmd2event:
            events.append(cmd2event[command].decode(ptr, command))
        else:
            raise VgmNotImplemented(f"Unhandled VGM command {command:#2x}")

    return events


# Write VGM

VGM_VERSION = 0x150
YM2612_CLOCK = 7600489  # PAL clock rate


def write_vgm(
        path: str,
        events: LinearEventList,
        orig_header: VgmHeader = None,
        ym2612_clock: int = None
) -> None:
    with open(path, 'wb') as f:
        wrt = Writer(f, ENDIAN)

        data_addr = 0x40

        # Write body
        wrt.seek(data_addr)

        nsamp = 0
        for event in events:
            event.encode(wrt)
            if isinstance(event, IWait):
                nsamp += event.delay

        # Write header
        nbytes = wrt.addr
        header = VgmHeader(
            nbytes=nbytes,
            version=VGM_VERSION,
            nsamp=nsamp,
            ym2612_clock=YM2612_CLOCK,
            data_addr=data_addr,
        )

        if orig_header:
            header = dataclasses.replace(
                header,
                ym2612_clock=orig_header.ym2612_clock,
            )

        if ym2612_clock:
            header.ym2612_clock = ym2612_clock

        header.encode(wrt)


# Event implementations

class IWait(EventStruct):
    delay: int


class PureWait(IWait):
    pass


# PCM
@register_cmd2event(0x67)
class DataBlock(EventStruct):
    magic: bytes = meta('hexmagic', '66')
    typ: int = meta('u8')
    nbytes: int = meta('u32')
    file: bytes = meta('bytes_', length='nbytes')


@register_cmd2event(0xE0)
class PCMSeek(EventStruct):
    address: int = meta('u32')


@register_cmd2event(*range(0x80, 0x90))
class PCMWriteWait(IWait):
    """0x8n:
    YM2612 port 0 address 2A write from the file bank, then wait n samples;
    n can range from 0 to 15. Note that the wait is n, NOT n+1.
    """
    delay: int = meta(parameterize=lambda x: x)


# Wait
@register_cmd2event(*range(0x70, 0x80))
class Wait4Bit(PureWait):
    """0x7n:
    wait n+1 samples, n can range from 0 to 15.
    """
    delay: int = meta(parameterize=lambda x: x + 1)


@register_cmd2event(0x61)
class Wait16Bit(PureWait):
    delay: int = meta('u16')


# YM2612 FM
@dataclass
class Write8as8(EventStruct):
    reg: int = meta('u8')
    value: int = meta('u8')


@register_cmd2event(0x52)
class YM2612Port0(Write8as8):
    pass


@register_cmd2event(0x53)
class YM2612Port1(Write8as8):
    pass


@register_cmd2event(0x50)
class PSGWrite(EventStruct):
    value: int = meta('u8')


# **** Add timestamps to LinearEventList ****

@dataclass
class TimedEvent:
    time: int
    event: EventStruct


TimedEventList = List[TimedEvent]


def time_event_list(events: LinearEventList) -> TimedEventList:
    time = 0
    time_events: TimedEventList = []

    for event in events:
        if not isinstance(event, PureWait):
            time_events.append(TimedEvent(time, event))
        if isinstance(event, IWait):
            time += event.delay

    return time_events


# def wait_event_list(time_events: TimedEventList) -> LinearEventList:
#     """ Converts a timed event list to a regular event list.
#     Only Wait16Bit will be used. All PCMWriteWait events will have duration 0. """
#     prev_time = 0
#     events: LinearEventList = []
#
#     for time, event in time_events:
#         if not isinstance(event, PureWait):
#             if time > prev_time:
#                 events.append(Wait16Bit)
#             events.append(event)
#
#             if isinstance(event, IWait):
#                 event = copy.copy(event)
#                 event.delay = 0
#
#             prev_time = time


def keep_type(time_events: TimedEventList, classes: List[type]) -> TimedEventList:
    if not classes:
        raise ValueError('empty classes')
    return [
        t_e for t_e in time_events if type(t_e.event) in classes
    ]


_Condition = Callable[[T], bool]


def filter_ev_type(
        time_events: TimedEventList,
        cls: Type[T],
        cond: _Condition = lambda e: True
) -> TimedEventList:

    # noinspection PyTypeHints
    return [
        t_e for t_e in time_events if isinstance(t_e.event, cls) and cond(t_e.event)
    ]


def filter_ev(time_events: TimedEventList, cond: _Condition) -> TimedEventList:
    return [t_e for t_e in time_events if cond(t_e.event)]


def filter_ev_time(time_events: TimedEventList, begin=float('-inf'), end=float('inf')) \
        -> TimedEventList:
    return [t_e for t_e in time_events if begin <= t_e.time < end]


def map_ev(
        time_events: TimedEventList,
        func: Callable[[Any], Any]
) -> TimedEventList:
    return [
        TimedEvent(t_e.time, func(t_e.event))
        for t_e in time_events
    ]

    pass


def main():
    bell = 'file/bell.vgm'

    # [event]
    events = parse_vgm(bell)

    # [time, event]
    time_events = time_event_list(events)
    time_events = keep_type(time_events, [YM2612Port0, YM2612Port1])
    print(len(time_events))
    print(time_events[-20:])


if __name__ == '__main__':
    main()
