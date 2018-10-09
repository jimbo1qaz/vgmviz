# import kaitaistruct as ks
#
# ks.KaitaiStruct
import numpy as np

from pointer import Pointer

bell = 'data/bell.vgm'


def parse_vgm(path):
    # data: np.ndarray = np.fromfile(path, np.uint8)
    # magic: np.ndarray = data[0:4]
    # assert magic.tobytes() == b'Vgm '
    with open(path, 'rb') as f:
        ptr = Pointer(f.read(), 0, 'little')

    ptr.magic(b'Vgm ', 0)
    version = ptr.u32(0x08)

    # ym2612_clock =
    # if version >= 0x0110:

    data_addr = 0x40
    if version >= 0x150:
        data_addr = ptr.offset(0x34)

    # Parse VGM data section




parse_vgm(bell)
