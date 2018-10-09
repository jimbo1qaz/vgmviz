from binascii import unhexlify
from typing import ByteString, Optional

from util import coalesce


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
        self.endian = endian
        self.seek(addr)

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

    # Integer getters

    def _IntegerGetter(bits, signed):
        nbytes = bits // 8

        def get_integer(self: 'Pointer', addr: int = None) -> int:
            data = self.bytes(nbytes, addr)
            return int.from_bytes(data, self.endian, signed=signed)

        return get_integer

    # The VGM file format assumes unsigned ints.
    u8 = _IntegerGetter(8, signed=False)
    u16 = _IntegerGetter(16, signed=False)
    u24 = _IntegerGetter(24, signed=False)
    u32 = _IntegerGetter(32, signed=False)

    s8 = _IntegerGetter(8, signed=True)
    s16 = _IntegerGetter(16, signed=True)
    s24 = _IntegerGetter(24, signed=True)
    s32 = _IntegerGetter(32, signed=True)

    del _IntegerGetter

        return getter
