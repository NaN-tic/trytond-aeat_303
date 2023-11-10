# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.company.model import CompanyValueMixin


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    aeat303_move_account = fields.MultiValue(fields.Many2One(
            'account.account', "Account for Move",
            domain=[
                ('closed', '=', False),
                ('party_required', '=', False),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ('type', '!=', None),
                ('type.expense', '=', False),
                ('type.revenue', '=', False),
                ('type.debt', '=', False),
                ],
            states={
                'required': Bool(Eval('aeat303_post_and_close')),
                },
            help='Account used for the counterpart in the creation of the '
            'account move when generate the 303 model.'))
    aeat303_move_journal = fields.MultiValue(fields.Many2One(
            'account.journal', "Journal for Move",
            states={
                'required': Bool(Eval('aeat303_post_and_close')),
                },
            help='Journal used for the counterpart in the creation of the '
            'account move when generate the 303 model.'))
    aeat303_post_and_close = fields.MultiValue(
        fields.Boolean("Post and Close",
        help='If checked the account move will be posted and the corresponding'
        ' period or periods will be closed.'))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'aeat303_move_account', 'aeat303_move_journal',
                'aeat303_post_and_close'}:
            return pool.get('account.configuration.aeat303')
        return super().multivalue_model(field)

    @classmethod
    def default_aeat303_post_and_close(cls, **pattern):
        return cls.multivalue_model(
            'aeat303_post_and_close').default_aeat303_post_and_close()


class ConfigurationAEAT303(ModelSQL, CompanyValueMixin):
    "AEAT 303 Account Configuration"
    __name__ = 'account.configuration.aeat303'
    aeat303_move_account = fields.Many2One(
        'account.account', "Account for Move",
        domain=[
            ('party_required', '=', False),
            ('company', '=', Eval('company', -1)),
            ('type', '!=', None),
            ('type.expense', '=', False),
            ('type.revenue', '=', False),
            ('type.debt', '=', False),
            ],
        states={
            'required': Bool(Eval('aeat303_post_and_close')),
            },
        help='Account used for the counterpart in the creation of the account'
        ' move when generate the 303 model.')
    aeat303_move_journal = fields.Many2One(
            'account.journal', "Journal for Move",
            states={
                'required': Bool(Eval('aeat303_post_and_close')),
                },
            context={
                'company': Eval('company', -1),
                },
            help='Journal used for the counterpart in the creation of the '
            'account move when generate the 303 model.')
    aeat303_post_and_close = fields.Boolean("Post and Close",
        help='If checked the account move will be posted and the corresponding'
        ' period or periods will be closed.')

    @staticmethod
    def default_aeat303_post_and_close():
        return False
