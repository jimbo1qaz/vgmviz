from vgmviz.ym2612 import ym2612_pack, ym2612_unpack


def test_reg_pack2unpack():
    for param in range(0x30, 0x80+1, 0x10):
        for chan in range(3):
            for op in range(4):
                tup_in = chan, op, param

                reg = ym2612_pack(*tup_in)
                assert isinstance(reg, int), f'ym2612_pack returned {reg} not int'

                tup_out = ym2612_unpack(reg)
                assert tup_out == tup_in, f'Input {tup_in} != {tup_out}'


# TODO def test_ym2612_filter():
