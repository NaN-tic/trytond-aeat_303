# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Origin(metaclass=PoolMeta):
    __name__ = 'account.statement.origin'

    def _search_move_line_reconciliation_domain(self, exclude_ids=None,
            second_currency=None):
        domain = super()._search_move_line_reconciliation_domain(exclude_ids,
            second_currency)
        for dom in domain:
            if dom[0] == 'OR' and dom[1][0] == 'move_origin':
                dom.append(('move_origin', 'like', 'aeat.303.report,%'))
        return domain
