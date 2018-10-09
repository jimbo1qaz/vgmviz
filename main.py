from utils.keyword_dataclasses import dataclass, field
from utils.pointer import Pointer


class VgmNotImplemented(NotImplementedError):
    pass


class LinearEventList(list):
    """ Consists of events and wait-events. """
    pass


@dataclass
class VgmFile:
    version: int = None
    nbytes: int = None
    data_addr: int = None
    events: LinearEventList = field(default_factory=LinearEventList)


def parse_vgm(path: str):
    with open(path, 'rb') as f:
        ptr = Pointer(f.read(), 0, 'little')

    data = VgmFile()

    parse_header(ptr, data)
    parse_body(ptr, data)

    return data


def parse_header(ptr: Pointer, data: VgmFile):
    ptr.magic(b'Vgm ', 0x00)
    data.nbytes = ptr.offset(0x04)
    data.version = ptr.u32(0x08)

    data.data_addr = 0x40
    if data.version >= 0x150:
        data.data_addr = ptr.offset(0x34)


def parse_body(ptr: Pointer, data: VgmFile):
    ev = data.events

    ptr.seek(data.data_addr)
    while ptr.addr < data.nbytes:
        command = ptr.u8()

        if command == 0x67:
            ev.append(DataBlock(ptr))
        elif command == 0x52:
            ev.append(YM2612Port0(ptr))
        elif command == 0x53:
            ev.append(YM2612Port1(ptr))
        elif command == 0x50:
            ev.append(PSGWrite(ptr))
        else:
            raise VgmNotImplemented(f"Unhandled VGM command {command:#2x}")


@dataclass
class DataBlock:
    typ: int
    nbytes: int
    data: bytes

    def __init__(self, ptr: Pointer):
        ptr.hexmagic('66')
        self.typ = ptr.u8()
        self.nbytes = ptr.u32()
        self.data = ptr.bytes(self.nbytes)
        print(self.nbytes)


@dataclass
class Write8as8:
    reg: int
    value: int

    def __init__(self, ptr: Pointer):
        self.reg = ptr.u8()
        self.value = ptr.u8()


class YM2612Port0(Write8as8):
    pass


class YM2612Port1(Write8as8):
    pass


@dataclass
class PSGWrite:
    value: int

    def __init__(self, ptr: Pointer):
        self.value = ptr.u8()


bell = 'data/bell.vgm'
parse_vgm(bell)
