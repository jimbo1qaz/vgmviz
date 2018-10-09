from typing import Any, List

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
    while True:
        assert ptr.addr < data.nbytes
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


# PCM
class DataBlock:
    def __init__(self, ptr: Pointer):
        ptr.hexmagic('66')
        self.typ = ptr.u8()
        self.nbytes = ptr.u32()
        self.data = ptr.bytes(self.nbytes)


class PCMSeek:
    def __init__(self, ptr: Pointer):
        self.address = ptr.u32()


class PCMWriteWait(IWait):
    """0x8n:
    YM2612 port 0 address 2A write from the data bank, then wait
    n samples; n can range from 0 to 15. Note that the wait is n,
    NOT n+1. (Note: Written to first chip instance only.)
    """
    def __init__(self, command: int):
        assert 0x80 <= command < 0x90, 'PCMWriteWait command out of range'
        self.delay = command - 0x80


# Wait
class Wait4Bit(IWait):
    """0x7n       : wait n+1 samples, n can range from 0 to 15."""
    def __init__(self, command: int):
        assert 0x70 <= command < 0x80, 'Wait command out of range'
        self.delay = command - 0x70 + 1


class Wait16Bit(IWait):
    def __init__(self, ptr: Pointer):
        self.delay = ptr.u16()


# YM2612 FM
class Write8as8:
    def __init__(self, ptr: Pointer):
        self.reg = ptr.u8()
        self.value = ptr.u8()


class YM2612Port0(Write8as8):
    pass


class YM2612Port1(Write8as8):
    pass


class PSGWrite:
    def __init__(self, ptr: Pointer):
        self.value = ptr.u8()


bell = 'data/bell.vgm'
if __name__ == '__main__':
    parse_vgm(bell)
