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
        'account.account', "Prorrata Account",
        states={
            'required': Bool(Eval('aeat303_prorrata_percent')),
            }))
    aeat303_prorrata_fiscalyear = fields.MultiValue(fields.Many2One(
        'account.fiscalyear', "Prorrata Fiscal Year"))

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
                'aeat303_prorrata_percent', 'aeat303_prorrata_fiscalyear'}:
            return pool.get('account.configuration.aeat303')
        return super().multivalue_model(field)

    @classmethod
    def default_aeat303_post_and_close(cls, **pattern):
        return cls.multivalue_model(
            'aeat303_post_and_close').default_aeat303_post_and_close()

    @classmethod
    @ModelView.button
    def calculate_prorrata(cls, records):
        config = records[0]
        fiscalyear = config.aeat303_prorrata_fiscalyear
        prorrata = config._calculate_prorrata(fiscalyear=fiscalyear)
        config.aeat303_prorrata_percent = prorrata
        config.save()

    def _calculate_prorrata(self, fiscalyear=None):
        pool = Pool()
        Mapping = pool.get('aeat.303.prorrata.mapping')
        TaxCode = pool.get('account.tax.code')
        FiscalYear = pool.get('account.fiscalyear')

        # Won't be really necessary, but with this control ensure that the
        # account is set and that allow th create the account move correctly.
        if not self.aeat303_prorrata_account:
            raise UserError(gettext('aeat_303.msg_prorrata_account_required'))

        company = Transaction().context.get('company')

        if not fiscalyear:
            fiscalyear = FiscalYear.find(company, test_state=False)
        if not self.aeat303_prorrata_fiscalyear:
            self.aeat303_prorrata_fiscalyear = fiscalyear
            self.save()
        periods = [p.id for p in fiscalyear.periods]

        mapping = {}
        for map in Mapping.search([('company', '=', company)]):
            for code in map.code_by_companies:
                mapping[code.id] = map.prorrata_field.name

        deductible_import = 0
        total_import = 0
        with Transaction().set_context(periods=periods):
            for tax,field in zip(TaxCode.browse(mapping.keys()),
                                 mapping.values()):
                total_import += tax.amount
                #Field refered in the prorrata total amount mapping
                if field == 'prorrata_total_amount':
                    continue
                deductible_import += tax.amount
        prorrata = (ceil((deductible_import/total_import) * 100)
                    if total_import else 0)

        return prorrata


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
        'account.account', "Prorrata Account",
                states={
            'required': Bool(Eval('aeat303_prorrata_percent')),
            })
    aeat303_prorrata_fiscalyear = fields.Many2One(
        'account.fiscalyear', "Prorrata Fiscal Year")

    @staticmethod
    def default_aeat303_post_and_close():
        return False

