from typing import Any, List, Callable, Type, TypeVar

from dataclasses import dataclass, field

from vgmviz import ym2612
from vgmviz.pointer import Pointer

assert ym2612


class VgmNotImplemented(NotImplementedError):
    pass


class LinearEventList(list):
    """ Consists of events and wait-events. """
    pass


@dataclass
class VgmFile:
    nbytes: int
    version: int
    data_addr: int
    events: LinearEventList = field(default_factory=LinearEventList)


def parse_vgm(path: str) -> LinearEventList:
    with open(path, 'rb') as f:
        ptr = Pointer(f.read(), 0, 'little')

    file = parse_header(ptr)
    parse_body(ptr, file)

    return file.events


def parse_header(ptr: Pointer) -> VgmFile:
    ptr.magic(b'Vgm ', 0x00)
    nbytes = ptr.offset(0x04)
    version = ptr.u32(0x08)

    data_addr = 0x40
    if version >= 0x150:
        data_addr = ptr.offset(0x34)

    return VgmFile(
        nbytes=nbytes,
        version=version,
        data_addr=data_addr
    )


def parse_body(ptr: Pointer, file: VgmFile):
    ev = file.events

    ptr.seek(file.data_addr)
    while True:
        assert ptr.addr < file.nbytes
        command = ptr.u8()

        # PCM
        if command == 0x66:
            break
        elif command == 0x67:
            ev.append(DataBlock(ptr))
        elif command == 0xe0:
            ev.append(PCMSeek(ptr))
        elif 0x80 <= command < 0x90:
            ev.append(PCMWriteWait(command))
        # Wait
        elif 0x70 <= command < 0x80:
            ev.append(Wait4Bit(command))
        elif command == 0x61:
            ev.append(Wait16Bit(ptr))
        # YM2612 FM
        elif command == 0x52:
            ev.append(YM2612Port0(ptr))
        elif command == 0x53:
            ev.append(YM2612Port1(ptr))
        elif command == 0x50:
            ev.append(PSGWrite(ptr))

        else:
            raise VgmNotImplemented(f"Unhandled VGM command {command:#2x}")


class IWait:
    delay: int


class PureWait(IWait):
    pass


# PCM
class DataBlock:
    def __init__(self, ptr: Pointer) -> None:
        ptr.hexmagic('66')
        self.typ = ptr.u8()
        self.nbytes = ptr.u32()
        self.file = ptr.bytes_(self.nbytes)


class PCMSeek:
    def __init__(self, ptr: Pointer) -> None:
        self.address = ptr.u32()


class PCMWriteWait(IWait):
    """0x8n:
    YM2612 port 0 address 2A write from the data bank, then wait
    n samples; n can range from 0 to 15. Note that the wait is n,
    NOT n+1. (Note: Written to first chip instance only.)
    """
    def __init__(self, command: int) -> None:
        assert 0x80 <= command < 0x90, 'PCMWriteWait command out of range'
        self.delay = command - 0x80


# Wait
class Wait4Bit(PureWait):
    """0x7n       : wait n+1 samples, n can range from 0 to 15."""
    def __init__(self, command: int) -> None:
        assert 0x70 <= command < 0x80, 'Wait command out of range'
        self.delay = command - 0x70 + 1


class Wait16Bit(PureWait):
    def __init__(self, ptr: Pointer) -> None:
        self.delay = ptr.u16()


# YM2612 FM
class Write8as8:
    def __init__(self, ptr: Pointer) -> None:
        self.reg = ptr.u8()
        self.value = ptr.u8()


class YM2612Port0(Write8as8):
    pass


class YM2612Port1(Write8as8):
    pass


class PSGWrite:
    def __init__(self, ptr: Pointer) -> None:
        self.value = ptr.u8()


# **** Add timestamps to LinearEventList ****

@dataclass
class TimedEvent:
    time: int
    event: Any


class TimedEventList(List[TimedEvent]):
    pass


def time_event_list(events: LinearEventList) -> TimedEventList:
    time = 0
    time_events = TimedEventList()

    for event in events:
        if not isinstance(event, PureWait):
            time_events.append(TimedEvent(time, event))
        if isinstance(event, IWait):
            time += event.delay

    return time_events


T = TypeVar('T')


def keep_type(time_events: TimedEventList, classes: List[type]) -> TimedEventList:
    if not classes:
        raise ValueError('empty classes')
    return TimedEventList(
        t_e for t_e in time_events if type(t_e.event) in classes
    )


def filter_ev(
        time_events: TimedEventList,
        cls: Type[T],
        cond: Callable[[T], bool] = lambda e: True
) -> TimedEventList:
    return TimedEventList(
        t_e for t_e in time_events if isinstance(t_e.event, cls) and cond(t_e.event)
    )


def main():
    bell = 'data/bell.vgm'

    # [event]
    events = parse_vgm(bell)

    # [time, event]
    time_events = time_event_list(events)
    time_events = keep_type(time_events, [YM2612Port0, YM2612Port1])
    print(len(time_events))
    print(time_events[-20:])


if __name__ == '__main__':
    main()
