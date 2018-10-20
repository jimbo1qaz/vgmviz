from vgmviz.ym2612 import reg_pack, reg_unpack, Register


def test_reg_pack2unpack():
    for param in range(0x30, 0x80+1, 0x10):
        for chan in range(3):
            for op in range(4):
                unpack = Register(chan, op, param)

                reg = reg_pack(unpack)
                assert isinstance(reg, int), f'reg_pack returned {reg} not int'

                unpack_out = reg_unpack(reg)
                assert unpack_out == unpack, f'Input {unpack} != {unpack_out}'


# TODO def test_reg_filter():
