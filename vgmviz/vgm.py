from typing import Any, List, Callable, Type, TypeVar, Generic, Dict, ClassVar, Optional

from dataclasses import dataclass, field, fields, Field

from vgmviz import ym2612
from vgmviz.pointer import Pointer, Writer

assert ym2612

T = TypeVar('T', bound='Event')


class VgmNotImplemented(NotImplementedError):
    pass


class LinearEventList(List[T]):
    """ Consists of events and wait-events. """
    pass


@dataclass
class VgmFile:
    nbytes: int
    version: int
    data_addr: int
    events: LinearEventList = field(default_factory=LinearEventList)


ENDIAN = 'little'

def parse_vgm(path: str) -> LinearEventList:
    with open(path, 'rb') as f:
        ptr = Pointer(f.read(), 0, ENDIAN)

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

        if command in cmd2event:
            ev.append(cmd2event[command].decode(ptr, command))
        else:
            raise VgmNotImplemented(f"Unhandled VGM command {command:#2x}")


# Event base classes, for decoder

Command = int   # int8
cmd2event: Dict[Command, Type['Event']] = {}


def register_cmd2event(*commands: int) -> Callable:
    """
    Decoding lookup: cmd2event[commands] = event.
    Encoding lookup: event.base_command = commands[0].
    """

    if len(commands) == 0:
        raise TypeError('must supply commands to register_cmd2event')

    def _register_event(event_cls: Type[Event]) -> Type[Event]:
        if not issubclass(event_cls, Event):
            raise TypeError(f'{event_cls} must be Event')

        event_cls.base_command = commands[0]
        event_cls.is_multiple_commands = (len(commands) > 1)

        for command in commands:
            cmd2event[command] = event_cls

        return dataclass(event_cls)
    return _register_event


# @dataclass
class Event:
    base_command: ClassVar[Command]

    # A property which is defined in subclasses where base_command==True.
    command: ClassVar[property]

    # Some wait events are represented by multiple commands with 4 leading bits.
    # The 4 trailing bits serve as a duration parameter.
    is_multiple_commands: ClassVar[bool]

    """
    Supporting parametric events is hard.
    
    - decode() is passed a `ptr` pointing AFTER command ID.
    It is also passed `command_offset`
    (used to initialize event fields, *not* saved permanently).
        - A field can be declared `x: int = meta(parameterize=lambda x: x + 1)`
        to initialize `x = command_offset + 1`.
    - decode() does not read command ID from `ptr`.

    - encode() checks: If `is_multiple_commands` is true,
    it reads the `command` property, which calculates command from event fields.
    - encode() writes command ID to `wrt`.
    
    - TODO: encode() ignores fields `x` targeted by `meta(length=x)`
    and recomputes them when writing.
        - Only useful for binary blob editing.
        I don't need it in the foreseeable future.
    
    - TODO: actually define `command` on parametric commands.
        - I do not expect to encode() them.
    
    decode is a classmethod but works well as an independent function.
    encode is a instance method.
    """

    @classmethod
    def decode(cls, ptr: Pointer, command: Command) -> 'Event':
        command_offset = command - cls.base_command
        kwargs = {}

        for f in fields(cls):  # type: Field
            try:
                meta = get_meta(f)
            except KeyError:
                raise TypeError(f'broken type {cls}: field {f.name} missing metadata')
            ptr_args = []

            if meta.parameterize:
                if not cls.is_multiple_commands:
                    raise ValueError(
                        f'non-parametric {cls} cannot have parametric field {f.name}')
                kwargs[f.name] = meta.parameterize(command_offset)

            elif meta.method:
                # Contrived example: ptr.bytes_(length, address)
                if meta.length:  # length
                    length_val = kwargs[meta.length]
                    ptr_args.append(length_val)
                if meta.arg:  # optional: address
                    ptr_args.append(meta.arg)

                kwargs[f.name] = getattr(ptr, meta.method)(*ptr_args)
            else:
                raise ValueError(
                    f'cannot decode event {cls}: field {f.name} has empty metadata')

        return cls(**kwargs)

    # NOT classmethod
    def encode(self, wrt: Writer) -> None:
        f: Field

        if self.is_multiple_commands:
            command = self.command
        else:
            command = self.base_command

        # Write command ID.
        wrt.u8(command)

        for f in fields(self):
            meta = get_meta(f)

            value = getattr(self, f.name)
            write_args = [value]

            # Do not write fields which were read from the command ID.
            if meta.parameterize:
                continue

            # Write fields which were read from command parameters.
            getattr(wrt, meta.method)(*write_args)


@dataclass
class FieldMeta:
    # Either: call ptr.method to read/write field
    method: str = None  # Method called to read/write
    arg: Optional = None  # Reading the field needs parameters (eg. magic numbers)
    length: Optional = None  # Reading the field depends on another field

    # Or: determine field from `command - base_command`
    parameterize: Callable[[int], int] = None

    def __post_init__(self):
        if not (self.method or self.parameterize):
            raise ValueError(
                'Invalid metadata, must supply one of [method, parameterize]')

        if self.method and self.parameterize:
            raise ValueError(
                'Invalid metadata, cannot supply multiple of [method, parameterize]')


def meta(*args, **kwargs) -> Field:
    return field(metadata={
        'struct_field':
            FieldMeta(*args, **kwargs)
    })


def get_meta(f: Field) -> 'FieldMeta':
    return f.metadata['struct_field']


# Event implementations

class IWait(Event):
    delay: int


class PureWait(IWait):
    pass


# PCM
@register_cmd2event(0x67)
class DataBlock(Event):
    magic: bytes = meta('hexmagic', '66')
    typ: int = meta('u8')
    nbytes: int = meta('u32')
    file: bytes = meta('bytes_', length='nbytes')


@register_cmd2event(0xE0)
class PCMSeek(Event):
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
class Write8as8(Event):
    reg: int = meta('u8')
    value: int = meta('u8')


@register_cmd2event(0x52)
class YM2612Port0(Write8as8):
    pass


@register_cmd2event(0x53)
class YM2612Port1(Write8as8):
    pass


@register_cmd2event(0x50)
class PSGWrite(Event):
    value: int = meta('u8')


# **** Add timestamps to LinearEventList ****

@dataclass
class TimedEvent(Generic[T]):
    time: int
    event: T


TimedEventList = List[TimedEvent[T]]


def time_event_list(events: LinearEventList[T]) -> TimedEventList[T]:
    time = 0
    time_events: TimedEventList[T] = []

    for event in events:
        if not isinstance(event, PureWait):
            time_events.append(TimedEvent(time, event))
        if isinstance(event, IWait):
            time += event.delay

    return time_events


# def wait_event_list(time_events: TimedEventList[T]) -> LinearEventList[T]:
#     """ Converts a timed event list to a regular event list.
#     Only Wait16Bit will be used. All PCMWriteWait events will have duration 0. """
#     prev_time = 0
#     events: LinearEventList[T] = []
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


# TODO truncate_ev_time, transposes the event just before, duplicates the final event.

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
