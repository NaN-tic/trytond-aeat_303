# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    deferred_dua_tax = fields.Boolean('Deferred DUA Tax')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        old_column = table.column_exist('redeme')
        new_column = table.column_exist('deferred_dua_tax')
        super().__register__(module_name)

        if old_column and not new_column:
            cursor.execute(*sql_table.update(
                    columns=[sql_table.deferred_dua_tax],
                    values=[sql_table.redeme]))
