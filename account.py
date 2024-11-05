# -*- coding: utf-8 -*-
from trytond.pool import Pool, PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['aeat.303.report']

    def get_allow_draft(self, name):
        pool = Pool()
        Report = pool.get('aeat.303.report')

        result = super().get_allow_draft(name)
        if self.origin and isinstance(self.origin, Report):
            return True
        return result
