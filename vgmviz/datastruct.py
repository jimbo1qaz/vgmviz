from typing import ClassVar, Dict, Type, Callable, Optional, Any, List, Union

from dataclasses import fields, Field, dataclass, field

from vgmviz.pointer import Pointer, Writer


_Args = List[Any]
_Kwargs = Dict[str, Any]


#### DataStruct field definnitions

_METADATA_KEY = 'struct_field'


def meta(*args, **kwargs) -> Field:
    metadata = FieldMeta(*args, **kwargs)

    field_kwargs = {}
    if metadata.method == 'magic':
        field_kwargs['default'] = metadata.arg

    return field(metadata={_METADATA_KEY: metadata}, **field_kwargs)


# Unused
# def bare_field(*args, **kwargs) -> Field:
#     return field(*args, **kwargs, metadata={_METADATA_KEY: None})


def _get_meta(f: Field) -> 'Optional[FieldMeta]':
    return f.metadata[_METADATA_KEY]


@dataclass
class FieldMeta:
    # Either: call ptr.method to read/write field
    method: Optional[str] = None  # Method called to read/write
    arg: Optional = None  # Reading the field needs parameters (eg. magic numbers)
    length: Optional[str] = None  # Reading the field depends on another field
    addr: Optional[int] = None  # Read *and* write the field at a fixed address

    # Or: determine field from `command - base_command`
    parameterize: Callable[[int], int] = None

    def __post_init__(self):
        if not (self.method or self.parameterize):
            raise ValueError(
                'Invalid metadata, must supply one of [method, parameterize]')

        if self.method and self.parameterize:
            raise ValueError(
                'Invalid metadata, cannot supply multiple of [method, parameterize]')


#### DataStruct (for VGM headers)

# noinspection PyDataclass
class DataStruct:
    """ Dataclass representing a struct. """
    @classmethod
    def decode(cls, ptr: Pointer) -> 'DataStruct':
        kwargs: _Kwargs = {}

        for f in fields(cls):  # type: Field
            _struct_read(cls, ptr, f, kwargs, 0)

        # noinspection PyArgumentList
        return cls(**kwargs)

    def encode(self, wrt: Writer) -> None:
        f: Field
        for f in fields(self):
            value = getattr(self, f.name)
            _struct_write(self, wrt, value, f)


#### EventStruct (special-case supporting command ID)

Command = int   # int8
cmd2event: Dict[Command, Type['EventStruct']] = {}


def register_cmd2event(*commands: int) -> Callable:
    """
    Decoding lookup: cmd2event[commands] = event.
    Encoding lookup: event.base_command = commands[0].
    """

    if len(commands) == 0:
        raise TypeError('must supply commands to register_cmd2event')

    def _register_event(event_cls: Type[EventStruct]) -> Type[EventStruct]:
        if not issubclass(event_cls, EventStruct):
            raise TypeError(f'{event_cls} must be Event')

        event_cls.base_command = commands[0]
        event_cls.is_multiple_commands = (len(commands) > 1)

        for command in commands:
            cmd2event[command] = event_cls

        return dataclass(event_cls)
    return _register_event


# noinspection PyDataclass
class EventStruct:
    """ Event composed of command + data.

    Supporting parametric events is hard.

    - decode() is passed a `ptr` pointing AFTER command ID.
    It is also passed `command_offset`
    (used to initialize event fields, *not* saved permanently).
        - A field can be declared `x: int = meta(parameterize=lambda x: x + 1)`
        to initialize `x = command_offset + 1`.
    - decode() does not read command ID from `ptr`.

    - encode() checks: If `is_multiple_commands` is true,
    it reads `command()`, which calculates command from event fields.
    - encode() writes command ID to `wrt`, skipping all parameterized fields.

    - TODO: encode() ignores fields `x` targeted by `meta(length=x)`
    and recomputes them when writing.
        - Only useful for binary blob editing.
        I don't need it in the foreseeable future.

    - TODO: actually define `command()` on parametric commands.
        - I do not expect to encode() them.
    """

    base_command: ClassVar[Command]
    command: ClassVar[Callable[[], int]]
    is_multiple_commands: ClassVar[bool]

    @classmethod
    def decode(cls, ptr: Pointer, command: Command) -> 'EventStruct':
        command_offset = command - cls.base_command
        kwargs = {}

        for f in fields(cls):  # type: Field
            _struct_read(cls, ptr, f, kwargs, command_offset)

        # noinspection PyArgumentList
        return cls(**kwargs)

    # NOT classmethod
    def encode(self, wrt: Writer) -> None:
        if self.is_multiple_commands:
            command = self.command()
        else:
            command = self.base_command

        # Write command ID.
        wrt.u8(command)

        f: Field
        for f in fields(self):
            value = getattr(self, f.name)
            _struct_write(self, wrt, value, f)


#### Struct field operations

_AnyStruct = Union[DataStruct, EventStruct]


def _struct_read(
        cls: Type[_AnyStruct],
        ptr: Pointer,
        f: Field,
        kwargs: _Kwargs,
        command_offset: Optional[int]
) -> None:
    try:
        metadata = _get_meta(f)
    except KeyError:
        raise ValueError(f'broken type {cls}: field {f.name} missing metadata')

    # bare_field() (unused and commented-out) produces metadata=None.
    if metadata is None:
        return

    if metadata.parameterize:
        if not getattr(cls, 'is_multiple_commands', None):
            raise ValueError(
                f'non-parametric {cls} cannot have parametric field {f.name}')
        kwargs[f.name] = metadata.parameterize(command_offset)

    elif metadata.method:
        ptr_args = []
        ptr_kwargs = {}

        if metadata.length:  # Data length equals another field
            length_val = kwargs[metadata.length]
            ptr_args.append(length_val)
        if metadata.arg:  # Magic numbers
            ptr_args.append(metadata.arg)
        if metadata.addr is not None:
            ptr_kwargs['addr'] = metadata.addr

        kwargs[f.name] = getattr(ptr, metadata.method)(*ptr_args, **ptr_kwargs)

    else:
        raise ValueError(
            f'cannot decode event {cls}: field {f.name} has empty metadata')


def _struct_write(obj: _AnyStruct, wrt: Writer, value: Any, f: Field) -> None:
    try:
        cls = type(obj)
        try:
            metadata = _get_meta(f)
        except KeyError:
            raise TypeError(f'broken type {cls}: field {f.name} missing metadata')

        write_args = [value]
        write_kwargs = {}

        # Parametric fields are encoded via obj.command(), and do not need to be written.
        if metadata.parameterize:
            # assert not metadata.method
            if not getattr(cls, 'is_multiple_commands', None):
                raise ValueError(
                    f'non-parametric {cls} cannot have parametric field {f.name}')
            return

        elif metadata.method:
            # Destination address
            if metadata.addr is not None:
                write_kwargs['addr'] = metadata.addr

            # Write fields which were read from command parameters.
            getattr(wrt, metadata.method)(*write_args, **write_kwargs)

        else:
            raise ValueError(
                f'cannot decode event {cls}: field {f.name} has empty metadata')
    except Exception as e:
        import sys
        raise type(e)(f'class={cls}, field={f.name}')
