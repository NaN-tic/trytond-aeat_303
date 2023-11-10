# -*- coding: utf-8 -*-
from trytond.pool import PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['aeat.303.report']
