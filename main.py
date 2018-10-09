# import kaitaistruct as ks
#
# ks.KaitaiStruct
import numpy as np

from pointer import Pointer

bell= 'data/bell.vgm'
# with open(, 'rb') as f:
#     data = f.read()
#


# class File:
#     def __init__(self, path, order='little'):
#         self.order = order
#         with open(path, 'rb') as f:
#             self.data = f.read()
#
#     def u32(self, offset):
#         _ = self.data[offset:offset+4]
#         return int.from_bytes(_, self.order, signed=False)
#
#     def s32(self, offset):
#         _ = self.data[offset:offset+4]
#         return int.from_bytes(_, self.order, signed=True)


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

    data_offset = 0x40
    if version >= 0x150:
        data_offset = 0x34
        data_offset += ptr.u32(data_offset)




parse_vgm(bell)
