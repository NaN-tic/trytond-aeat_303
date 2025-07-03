# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelSQL, fields, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.company.model import CompanyValueMixin
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext
from math import ceil
from datetime import datetime, date

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
    aeat303_prorrata_percent = fields.MultiValue(fields.Integer(
        "Prorrata Percent"))
    aeat303_prorrata_account = fields.MultiValue(fields.Many2One(
        'account.account', "Prorrata Account"))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'calculate_prorrata': {}
            })

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'aeat303_move_account', 'aeat303_move_journal',
                'aeat303_post_and_close','aeat303_prorrata_account',
                'aeat303_prorrata_percent'}:
            return pool.get('account.configuration.aeat303')
        return super().multivalue_model(field)

    @classmethod
    def default_aeat303_post_and_close(cls, **pattern):
        return cls.multivalue_model(
            'aeat303_post_and_close').default_aeat303_post_and_close()

    @classmethod
    @ModelView.button
    def calculate_prorrata(cls, records):
        pool = Pool()
        Mapping = pool.get('aeat.303.prorrata.mapping')
        TaxCode = pool.get('account.tax.code')
        Period = pool.get('account.period')

        config = records[0]
        if not config.aeat303_prorrata_account:
            raise UserError(gettext('aeat_303.msg_prorrata_account_required'))

        company =  Transaction().context.get('company')
        year = datetime.now().year
        periods = [p.id for p in Period.search([
                ('start_date', '>=', date(year, 1, 1)),
                ('end_date', '<=', date(year, 9, 30)),
                ('company', '=', company),
                ])]

        mapping = {}
        for map in Mapping.search([('company', '=', company)]):
            for code in map.code_by_companies:
                mapping[code.id] = map.prorrata_field.name

        deductible_import = 0
        total_import = 0
        with Transaction().set_context(periods=periods):
            for tax,field in zip(TaxCode.browse(mapping.keys()), mapping.values()):
                total_import += tax.amount
                #Field refered in the prorrata total amount mapping
                if field == 'prorrata_total_amount':
                    continue
                deductible_import += tax.amount
        prorrata = ceil((deductible_import/total_import) * 100) if total_import else 0

        config.aeat303_prorrata_percent = prorrata
        config.save()


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
    aeat303_prorrata_percent = fields.Integer(
        "Prorrata Percent")
    aeat303_prorrata_account = fields.Many2One(
        'account.account', "Prorrata Account")

    @staticmethod
    def default_aeat303_post_and_close():
        return False
