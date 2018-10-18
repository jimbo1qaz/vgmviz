import io
from binascii import unhexlify
from typing import ByteString, AnyStr, IO

from vgmviz.util import coalesce


class MagicError(ValueError):
    pass


Endian = str


class Pointer:
    data: bytes
    addr: int

    def __init__(self,
                 data: bytes,
                 addr: int,
                 endian: Endian) -> None:

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

    def bytes_(self, length: int, addr: int = None) -> bytes:
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

    def magic(self, magic, addr: int = None) -> bytes:
        """ Assert the existence of magic constants. """
        pos = self.addr

        read = self.bytes_(len(magic), addr)
        if read != magic:
            raise MagicError(f'Invalid magic at {pos}: read={read} expected={magic}')

        return read

    def hexmagic(self, hexmagic: AnyStr) -> bytes:
        return self.magic(unhexlify(hexmagic))

    # Integer getters

    def _IntegerGetter(bits, signed):
        nbytes = bits // 8

        def get_integer(self: 'Pointer', addr: int = None) -> int:
            data = self.bytes_(nbytes, addr)
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

    # 32-bit pointer offsets.
    PTR_GETTER = s32

    def offset(self, addr: int = None) -> int:
        """
        VGM pointers are encoded as offsets relative to the location of the pointer.
        I'll use signed address-offsets, since I'm more worried about negative offsets
        than >2GB VGM files.
        """
        addr = coalesce(addr, self.addr)

        offset = self.PTR_GETTER(addr)
        return addr + offset


class Writer:
    file: io.BytesIO

    @property
    def addr(self):
        return self.file.tell()

    def __init__(self,
                 file: IO[bytes],
                 endian: Endian) -> None:

        self.file = file
        self.endian = endian

        def _IntegerSetter(bits, signed):
            nbytes = bits // 8

            def set_integer(value: int, addr: int = None) -> None:
                data = value.to_bytes(nbytes, self.endian, signed=signed)
                self.bytes_(data, addr)

            return set_integer

        self.u8 = _IntegerSetter(8, signed=False)
        self.u16 = _IntegerSetter(16, signed=False)
        self.u24 = _IntegerSetter(24, signed=False)
        self.u32 = _IntegerSetter(32, signed=False)

        self.s8 = _IntegerSetter(8, signed=True)
        self.s16 = _IntegerSetter(16, signed=True)
        self.s24 = _IntegerSetter(24, signed=True)
        self.s32 = _IntegerSetter(32, signed=True)

        self.PTR_SETTER = self.s32

    @classmethod
    def create(cls, endian: Endian):
        return cls(file=io.BytesIO(),
                   endian=endian)

    def seek(self, addr: int):
        return self.file.seek(addr)

    def seek_rel(self, offset):
        return self.file.seek(offset, io.SEEK_CUR)

    # **** WRITE ****

    def bytes_(self, data: bytes, addr: int = None) -> None:
        if addr is not None:
            self.seek(addr)
        self.file.write(data)

    def hexmagic(self, hexmagic: AnyStr):
        self.bytes_(unhexlify(hexmagic))

    def offset(self, star: int, amp: int = None) -> None:
        amp = coalesce(amp, self.addr)

        offset = star - amp
        self.PTR_SETTER(offset, amp)
