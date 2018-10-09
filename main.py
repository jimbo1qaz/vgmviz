from utils.keyword_dataclasses import dataclass
from utils.pointer import Pointer

bell = 'data/bell.vgm'


@dataclass
class VgmData:
    version: int = None
    data_addr: int = None


class VgmParser:
    """Parser for VGM file format. Builds a list of events."""
    def __init__(self, path: str):
        self.path = path
        with open(path, 'rb') as f:
            self.ptr = Pointer(f.read(), 0, 'little')

        self.data = VgmData()

        self.parse_header()
        self.parse_body()

    def parse_header(self):
        ptr = self.ptr
        data = self.data

        ptr.magic(b'Vgm ', 0)
        data.version = ptr.u32(0x08)

        data.data_addr = 0x40
        if data.version >= 0x150:
            data.data_addr = ptr.offset(0x34)

    def parse_body(self):
        ptr = self.ptr
        data = self.data

        ptr.seek(data.data_addr)




parse_vgm(bell)
