from vgmviz.ym2612 import ym2612_pack, ym2612_unpack


def test_reg_pack2unpack():
    for param in range(0x30, 0x80+1, 0x10):
        for chan in range(3):
            for op in range(4):
                pco_in = param, chan, op

                reg = ym2612_pack(param, chan, op)
                assert isinstance(reg, int), f'ym2612_pack returned {reg} not int'

                pco_out = ym2612_unpack(reg)
                assert pco_out == pco_in, f'Input {pco_in} != {pco_out}'


# TODO def test_reg_filter():
