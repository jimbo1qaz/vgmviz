from binascii import unhexlify
from typing import ByteString, Optional

from util import coalesce


def byte_aligned(bits):
    assert bits % 8 == 0


# def wrap(val, bits):
#     val %= 2 ** bits
#
#     wraparound = 2 ** (bits - 1)
#     if val >= wraparound:
#         val -= wraparound * 2
#
#     return val


# def bytes2int(in_bytes, endian, signed):
#     return int.from_bytes(in_bytes, 'little' if endian else 'big', signed=signed)


# def int2bytes(value: int, bits, endian=False):
#     byte_aligned(bits)
#     return value.to_bytes(bits // 8, 'little' if endian else 'big')


class MagicError(ValueError):
    pass


Endian = str


class Pointer:
    data: bytes
    addr: int

    def __init__(self,
                 data: bytes,
                 addr: int,
                 endian: Endian):

        if not isinstance(data, ByteString):
            raise TypeError('Pointer() requires bytes or bytearray (buffer API)')

        self.data = data
        self.seek(addr)

        # self.bytes() raises OverlapError
        self.u8 = self._getter_factory(8, endian, signed=False)
        self.u16 = self._getter_factory(16, endian, signed=False)
        self.u24 = self._getter_factory(24, endian, signed=False)
        self.u32 = self._getter_factory(32, endian, signed=False)

        self.s8 = self._getter_factory(8, endian, signed=True)
        self.s16 = self._getter_factory(16, endian, signed=True)
        self.s24 = self._getter_factory(24, endian, signed=True)
        self.s32 = self._getter_factory(32, endian, signed=True)

    @classmethod
    def create(cls, data: bytes, endian: Endian):
        return cls(data,
                   addr=0,
                   endian=endian)

    def seek(self, addr: int):
        nbytes = len(self.data)

        # Seeking to EOF is allowed. Reading from EOF is not.
        if not (isinstance(addr, int) and 0 <= addr <= nbytes):
            raise ValueError('Invalid address {} / {}'.format(addr, nbytes))

        self.addr = addr
        return addr

    def seek_rel(self, offset):
        return self.seek(self.addr + offset)

    # **** READ ****

    def bytes(self, length: int, addr: int = None) -> bytes:
        if addr is not None:
            self.addr = addr
        begin = self.addr
        end = begin + length

        # Error checking
        if length <= 0:
            raise ValueError('bytes() call, length %s (<= 0)' % length)
        if end > len(self.data):
            raise ValueError('end of file')

        # Read data and increment pointer
        self.addr = end
        return self.data[begin:end]

    def vlq(self):
        out = 0

        while 1:
            # Assemble a multi-byte int.
            byte = self.u8()
            sub = byte & 0x7f

            out <<= 7
            out |= sub

            if byte & 0x80 == 0:
                break

        return out

    def magic(self, magic, addr: int = None):
        """ Assert the existence of magic constants. """
        pos = self.addr

        read = self.bytes(len(magic), addr)
        if read != magic:
            raise MagicError(f'Invalid magic at {pos}: read={read} expected={magic}')

        return read

    def hexmagic(self, hexmagic):
        return self.magic(unhexlify(hexmagic))

    def _getter_factory(self, bits, endian, signed):
        nbytes = bits // 8

        def getter(addr: int = None):
            data = self.bytes(nbytes, addr)
            return int.from_bytes(data, endian, signed=signed)

        return getter
