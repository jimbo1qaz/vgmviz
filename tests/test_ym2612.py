from vgmviz.ym2612 import reg_pack, reg_unpack


def test_reg_pack2unpack():
    for param in range(0x30, 0x80+1, 0x10):
        for chan in range(3):
            for op in range(4):
                tup_in = chan, op, param

                reg = reg_pack(*tup_in)
                assert isinstance(reg, int), f'reg_pack returned {reg} not int'

                tup_out = reg_unpack(reg)
                assert tup_out == tup_in, f'Input {tup_in} != {tup_out}'


# TODO def test_reg_filter():
