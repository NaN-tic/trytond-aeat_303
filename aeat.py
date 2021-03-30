# -*- coding: utf-8 -*-
from decimal import Decimal
import datetime
import calendar
import unicodedata
import sys

from retrofix import aeat303
from retrofix.record import Record, write as retrofix_write
from trytond.model import Workflow, ModelSQL, ModelView, fields, Unique
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond import backend
from sql import Literal


__all__ = ['Report', 'TemplateTaxCodeMapping', 'TemplateTaxCodeRelation',
    'TaxCodeMapping', 'TaxCodeRelation', 'CreateChart',
    'UpdateChart']

_STATES = {
    'readonly': Eval('state') == 'done',
    }

_DEPENDS = ['state']

_Z = Decimal("0.0")


def remove_accents(unicode_string):
    str_ = str if sys.version_info < (3, 0) else bytes
    unicode_ = str if sys.version_info < (3, 0) else str
    if isinstance(unicode_string, str_):
        unicode_string_bak = unicode_string
        try:
            unicode_string = unicode_string_bak.decode('iso-8859-1')
        except UnicodeDecodeError:
            try:
                unicode_string = unicode_string_bak.decode('utf-8')
            except UnicodeDecodeError:
                return unicode_string_bak

    if not isinstance(unicode_string, unicode_):
        return unicode_string

    unicode_string_nfd = ''.join(
        (c for c in unicodedata.normalize('NFD', unicode_string)
            if (unicodedata.category(c) != 'Mn'
                or c in ('\\u0327', '\\u0303'))  # Avoids normalize ç and ñ
            ))
    # It converts nfd to nfc to allow unicode.decode()
    return unicodedata.normalize('NFC', unicode_string_nfd)


class TemplateTaxCodeRelation(ModelSQL):
    '''
    AEAT 303 TaxCode Mapping Codes Relation
    '''
    __name__ = 'aeat.303.mapping-account.tax.code.template'

    mapping = fields.Many2One('aeat.303.template.mapping', 'Mapping',
        required=True, select=True)
    code = fields.Many2One('account.tax.code.template', 'Tax Code Template',
        required=True, select=True)


class TemplateTaxCodeMapping(ModelSQL):
    '''
    AEAT 303 TemplateTaxCode Mapping
    '''
    __name__ = 'aeat.303.template.mapping'

    aeat303_field = fields.Many2One('ir.model.field', 'Field',
        domain=[('module', '=', 'aeat_303')], required=True)
    type_ = fields.Selection([('code', 'Code'), ('numeric', 'Numeric')],
        'Type', required=True)
    code = fields.Many2Many('aeat.303.mapping-account.tax.code.template',
        'mapping', 'code', 'Tax Code Template', states={
            'invisible': Eval('type_') != 'code',
        }, depends=['type_'])
    number = fields.Numeric('Number',
        states={
            'required': Eval('type_') == 'numeric',
            'invisible': Eval('type_') != 'numeric',
            },
        depends=['type_'])

    @classmethod
    def __setup__(cls):
        super(TemplateTaxCodeMapping, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('aeat303_field_uniq', Unique(t, t.aeat303_field),
                'Field must be unique.')
            ]

    @staticmethod
    def default_type_():
        return 'code'

    def _get_mapping_value(self, mapping=None):
        pool = Pool()
        TaxCode = pool.get('account.tax.code')

        res = {}
        if not mapping or mapping.type_ != self.type_:
            res['type_'] = self.type_
        if not mapping or mapping.aeat303_field != self.aeat303_field:
            res['aeat303_field'] = self.aeat303_field.id
        if not mapping or mapping.number != self.number:
            res['number'] = self.number
        res['code'] = []
        old_ids = set()
        new_ids = set()
        if mapping and len(mapping.code) > 0:
            old_ids = set([c.id for c in mapping.code])
        if len(self.code) > 0:
            new_ids = set([c.id for c in TaxCode.search([
                            ('template', 'in', [c.id for c in self.code])
                            ])])
        if not mapping or mapping.template != self:
            res['template'] = self.id
        if old_ids or new_ids:
            key = 'code'
            res[key] = []
            to_remove = old_ids - new_ids
            if to_remove:
                res[key].append(['remove', list(to_remove)])
            to_add = new_ids - old_ids
            if to_add:
                res[key].append(['add', list(to_add)])
            if not res[key]:
                del res[key]
        if not mapping and self.type_ == 'code' and not res['code']:
            return  # There is nothing to create as there is no mapping
        return res


class UpdateChart(metaclass=PoolMeta):
    __name__ = 'account.update_chart'

    def transition_update(self):
        pool = Pool()
        MappingTemplate = pool.get('aeat.303.template.mapping')
        Mapping = pool.get('aeat.303.mapping')
        ret = super(UpdateChart, self).transition_update()
        # Update current values
        ids = []
        company = self.start.account.company.id
        for mapping in Mapping.search([
                    ('company', 'in', [company, None]),
                    ]):
            if not mapping.template:
                continue
            vals = mapping.template._get_mapping_value(mapping=mapping)
            if vals:
                Mapping.write([mapping], vals)
            ids.append(mapping.template.id)

        # Create new one's
        to_create = []
        for template in MappingTemplate.search([('id', 'not in', ids)]):
            vals = template._get_mapping_value()
            if vals:
                vals['company'] = company
                to_create.append(vals)
        if to_create:
            Mapping.create(to_create)
        return ret


class CreateChart(metaclass=PoolMeta):
    __name__ = 'account.create_chart'

    def transition_create_account(self):
        pool = Pool()
        MappingTemplate = pool.get('aeat.303.template.mapping')
        Mapping = pool.get('aeat.303.mapping')

        company = self.account.company.id

        ret = super(CreateChart, self).transition_create_account()
        to_create = []
        for template in MappingTemplate.search([]):
            vals = template._get_mapping_value()
            if vals:
                vals['company'] = company
                to_create.append(vals)

        Mapping.create(to_create)
        return ret


class TaxCodeRelation(ModelSQL):
    '''
    AEAT 303 TaxCode Mapping Codes Relation
    '''
    __name__ = 'aeat.303.mapping-account.tax.code'

    mapping = fields.Many2One('aeat.303.mapping', 'Mapping', required=True,
        select=True)
    code = fields.Many2One('account.tax.code', 'Tax Code', required=True,
        select=True)


class TaxCodeMapping(ModelSQL, ModelView):
    '''
    AEAT 303 TaxCode Mapping
    '''
    __name__ = 'aeat.303.mapping'

    company = fields.Many2One('company.company', 'Company',
        ondelete="RESTRICT")
    aeat303_field = fields.Many2One('ir.model.field', 'Field',
        domain=[('module', '=', 'aeat_303')], required=True)
    type_ = fields.Selection([('code', 'Code'), ('numeric', 'Numeric')],
        'Type', required=True)
    code = fields.Many2Many('aeat.303.mapping-account.tax.code', 'mapping',
        'code', 'Tax Code', states={
            'required': Eval('type_') == 'code',
            'invisible': Eval('type_') != 'code',
        }, depends=['type_'])
    number = fields.Numeric('Number',
        states={
            'required': Eval('type_') == 'numeric',
            'invisible': Eval('type_') != 'numeric',
            },
        depends=['type_'])
    template = fields.Many2One('aeat.303.template.mapping', 'Template')

    @classmethod
    def __setup__(cls):
        super(TaxCodeMapping, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('aeat303_field_uniq', Unique(t, t.company, t.aeat303_field),
                'Field must be unique.')
            ]

    @staticmethod
    def default_type_():
        return 'code'

    @staticmethod
    def default_company():
        return Transaction().context.get('company') or None


class Report(Workflow, ModelSQL, ModelView):
    '''
    AEAT 303 Report
    '''
    __name__ = 'aeat.303.report'

    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    fiscalyear_code = fields.Integer('Fiscal Year Code', required=True)
    monthly_return_subscription = fields.Boolean('Montly Return Subscription')
    period = fields.Selection([
            ('1T', 'First quarter'),
            ('2T', 'Second quarter'),
            ('3T', 'Third quarter'),
            ('4T', 'Fourth quarter'),
            ('01', 'January'),
            ('02', 'February'),
            ('03', 'March'),
            ('04', 'April'),
            ('05', 'May'),
            ('06', 'June'),
            ('07', 'July'),
            ('08', 'August'),
            ('09', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
            ], 'Period', required=True, sort=False, states=_STATES,
        depends=_DEPENDS)
    type = fields.Selection([
            ('C', 'Application for compensation'),
            ('D', 'Return'),
            ('G', 'Current account tax - Revenue'),
            ('I', 'Income'),
            ('N', 'No activity / Zero result'),
            ('V', 'Current account tax - Returns'),
            ('U', 'Direct incomes in account'),
            ], 'Declaration Type', required=True, sort=False, states=_STATES,
        depends=_DEPENDS)
    regime_type = fields.Selection([
            #('1', 'Tribute exclusively on simplificated regime'),
            #('2', 'Tribute on both simplified and general regime'),
            ('3', 'Tribute exclusively on general regime'),
            ], 'Tribute type', required=True, sort=False, states=_STATES,
        depends=_DEPENDS)
    joint_liquidation = fields.Boolean('Is joint liquidation')
    recc = fields.Boolean('Special Cash Criteria')
    recc_receiver = fields.Boolean('Special Cash Criteria Receiver')
    special_prorate = fields.Boolean('Special prorate')
    special_prorate_revocation = fields.Boolean('Special prorate revocation')
    accrued_vat_base_1 = fields.Numeric('Accrued Vat Base 1', digits=(16, 2))
    accrued_vat_percent_1 = fields.Numeric('Accrued Vat Percent 1',
        digits=(16, 2))
    accrued_vat_tax_1 = fields.Numeric('Accrued Vat Tax 1', digits=(16, 2))
    accrued_vat_base_2 = fields.Numeric('Accrued Vat Base 2', digits=(16, 2))
    accrued_vat_percent_2 = fields.Numeric('Accrued Vat Percent 2',
        digits=(16, 2))
    accrued_vat_tax_2 = fields.Numeric('Accrued Vat Tax 2', digits=(16, 2))
    accrued_vat_base_3 = fields.Numeric('Accrued Vat Base 3', digits=(16, 2))
    accrued_vat_percent_3 = fields.Numeric('Accrued Vat Percent 3',
        digits=(16, 2))
    accrued_vat_tax_3 = fields.Numeric('Accrued Vat Tax 3', digits=(16, 2))
    accrued_vat_base_modification = fields.Numeric('Accrued Vat Base '
        'Modification', digits=(16, 2))
    accrued_vat_tax_modification = fields.Numeric('Accrued Vat Tax '
        'Modification', digits=(16, 2))
    accrued_re_base_1 = fields.Numeric('Accrued Re Base 1', digits=(16, 2))
    accrued_re_percent_1 = fields.Numeric('Accrued Re Percent 1',
        digits=(16, 2))
    accrued_re_tax_1 = fields.Numeric('Accrued Re Tax 1', digits=(16, 2))
    accrued_re_base_2 = fields.Numeric('Accrued Re Base 2', digits=(16, 2))
    accrued_re_percent_2 = fields.Numeric('Accrued Re Percent 2',
        digits=(16, 2))
    accrued_re_tax_2 = fields.Numeric('Accrued Re Tax 2', digits=(16, 2))
    accrued_re_base_3 = fields.Numeric('Accrued Re Base 3', digits=(16, 2))
    accrued_re_percent_3 = fields.Numeric('Accrued Re Percent 3',
        digits=(16, 2))
    accrued_re_tax_3 = fields.Numeric('Accrued Re Tax 3', digits=(16, 2))
    accrued_re_base_modification = fields.Numeric('Accrued Re Base '
        'Modification', digits=(16, 2))
    accrued_re_tax_modification = fields.Numeric('Accrued Re Tax '
        'Modification', digits=(16, 2))
    intracommunity_adquisitions_base = fields.Numeric(
        'Intracommunity Adquisitions Base', digits=(16, 2))
    intracommunity_adquisitions_tax = fields.Numeric(
        'Intracommunity Adquisitions Tax', digits=(16, 2))
    other_passive_subject_base = fields.Numeric(
        'Other Passive Subject Adquisitions Base', digits=(16, 2))
    other_passive_subject_tax = fields.Numeric(
        'Other Passive Subject Adquisitions Tax', digits=(16, 2))
    accrued_total_tax = fields.Function(fields.Numeric('Accrued Total Tax',
            digits=(16, 2)), 'get_accrued_total_tax')
    deductible_current_domestic_operations_base = fields.Numeric(
        'Deductible Current Domestic Operations Base', digits=(16, 2))
    deductible_current_domestic_operations_tax = fields.Numeric(
        'Deductible Current Domestic Operations Tax', digits=(16, 2))
    deductible_investment_domestic_operations_base = fields.Numeric(
        'Deductible Investment Domestic Operations Base', digits=(16, 2))
    deductible_investment_domestic_operations_tax = fields.Numeric(
        'Deductible Investment Domestic Operations Tax', digits=(16, 2))
    deductible_current_import_operations_base = fields.Numeric(
        'Deductible Current Import Operations Base', digits=(16, 2))
    deductible_current_import_operations_tax = fields.Numeric(
        'Deductible Current Import Operations Tax', digits=(16, 2))
    deductible_investment_import_operations_base = fields.Numeric(
        'Deductible Investment Import Operations Base', digits=(16, 2))
    deductible_investment_import_operations_tax = fields.Numeric(
        'Deductible Investment Import Operations Tax', digits=(16, 2))
    deductible_current_intracommunity_operations_base = fields.Numeric(
        'Deductible Current Intracommunity Operations Base', digits=(16, 2))
    deductible_current_intracommunity_operations_tax = fields.Numeric(
        'Deductible Current Intracommunity Operations Tax', digits=(16, 2))
    deductible_investment_intracommunity_operations_base = fields.Numeric(
        'Deductible Investment Intracommunity Operations Base', digits=(16, 2))
    deductible_investment_intracommunity_operations_tax = fields.Numeric(
        'Deductible Investment Intracommunity Operations Tax', digits=(16, 2))
    deductible_regularization_base = fields.Numeric(
        'Deductible Regularization Base', digits=(16, 2))
    deductible_regularization_tax = fields.Numeric(
        'Deductible Regularization Tax', digits=(16, 2))
    deductible_compensations = fields.Numeric('Deductible Compensations',
        digits=(16, 2))
    deductible_investment_regularization = fields.Numeric(
        'Deductible Investment Regularization', digits=(16, 2))
    deductible_pro_rata_regularization = fields.Numeric(
        'Deductible Pro Rata Regularization', digits=(16, 2))
    deductible_total = fields.Function(fields.Numeric('Deductible Total',
            digits=(16, 2)), 'get_deductible_total')
    result_tax_regularitzation = fields.Numeric(
        'Tax Regularization art. 80.cinco.50a LIVA', digits=(16, 2),
        help="Only fill if you have done the 952 model. To Fill with the tax "
        "to recover.")
    general_regime_result = fields.Function(fields.Numeric(
            'General Regime Result',
            digits=(16, 2)), 'get_general_regime_result')
    state_administration_percent = fields.Numeric(
        'State Administration Percent', digits=(16, 2))
    state_administration_amount = fields.Function(
        fields.Numeric('State Administration Amount', digits=(16, 2)),
        'get_state_administration_amount')
    previous_report = fields.Many2One('aeat.303.report', 'Previous Report',
        states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    previous_period_pending_amount_to_compensate = fields.Numeric(
        'Previous Period Pending Amount To Compensate', digits=(16, 2),
        states={
            'readonly': Bool(Eval('previous_report')),
            }, depends=['previous_report'])
    previous_period_amount_to_compensate = fields.Numeric(
        'Previous Period Amount To Compensate', digits=(16, 2))
    result_previous_period_amount_to_compensate = fields.Function(
        fields.Numeric('Result Previous Period Amount To Compensate',
            digits=(16, 2)), 'get_result_previous_period_amount_to_compensate')
    intracommunity_deliveries = fields.Numeric(
        'Intracommunity Deliveries', digits=(16, 2))
    exports = fields.Numeric('Exports', digits=(16, 2))
    not_subject_or_reverse_charge = fields.Numeric(
        'Not Subject Or Reverse Charge', digits=(16, 2))
    sum_results = fields.Function(fields.Numeric(
            'Sum of Results', digits=(16, 2)), 'get_sum_results')
    aduana_tax_pending = fields.Numeric(
        'Aduana Tax Pending', digits=(16, 2),
        help="Import VAT paid by Aduana pending entry")
    joint_taxation_state_provincial_councils = fields.Numeric(
        'Joint Taxation State Provincial Councils', digits=(16, 2))
    result = fields.Function(fields.Numeric('Result', digits=(16, 2)),
        'get_result')
    to_deduce = fields.Numeric('To Deduce', digits=(16, 2))
    liquidation_result = fields.Function(fields.Numeric('Liquidation Result',
        digits=(16, 2)), 'get_liquidation_result')
    amount_to_compensate = fields.Numeric('Amount To Compensate',
        digits=(16, 2))
    recc_deliveries_base = fields.Numeric(
        'Special Cash Criteria Deliveries Base', digits=(16, 2))
    recc_deliveries_tax = fields.Numeric(
        'Special Cash Criteria Deliveries Tax', digits=(16, 2))
    recc_adquisitions_base = fields.Numeric(
        'Special Cash Criteria Asquistions Base', digits=(16, 2))
    recc_adquisitions_tax = fields.Numeric(
        'Special Cash Criteria Adquistions Tax', digits=(16, 2))
    info_territory_alava = fields.Numeric(
        'Taxation Information by Territory: Alava', digits=(16, 2))
    info_territory_guipuzcoa = fields.Numeric(
        'Taxation Information by Territory: Guipuzcoa', digits=(16, 2))
    info_territory_vizcaya = fields.Numeric(
        'Taxation Information by Territory: Vizcaya', digits=(16, 2))
    info_territory_navarra = fields.Numeric(
        'Taxation Information by Territory: Navarra', digits=(16, 2))
    special_info_exempt_op_2bdeduced = fields.Numeric(
        'Exports and Other Exempt Oprations to be Deduce', digits=(16, 2))
    special_info_farming_cattleraising_fishing = fields.Numeric(
        'Especial Regime of Farming, Cattle rasing and Fishing',
        digits=(16, 2))
    special_info_passive_subject_re = fields.Numeric(
        'Passive Subject on Equivalence Regime', digits=(16, 2))
    special_info_art_antiques_collectibles = fields.Numeric(
        'Special Regime Operations on Art, Antiques and Collectibles',
        digits=(16, 2))
    special_info_travel_agency = fields.Numeric(
        'Special Regime Operations on Travel Agency', digits=(16, 2))
    special_info_delivery_investment_domestic_operations = fields.Numeric(
        'Delivery of Investment Domestic Operations', digits=(16, 2))
    information_taxation_reason_territory = fields.Numeric(
        'Information on taxation by reason of territorya: Commo territory',
        digits=(3, 2))
    without_activity = fields.Boolean('Without Activity')
    company_party = fields.Function(fields.Many2One('party.party',
            'Company Party'),
        'on_change_with_company_party')
    bank_account = fields.Many2One('bank.account', 'Bank Account',
        domain=[
            ('owners', '=', Eval('company_party')),
        ], states={
            'required': Eval('type') == 'U',
            },
        depends=['company_party', 'type'])
    exonerated_mod390 = fields.Selection([
            ('0', ''),
            ('1', 'Yes'),
            ('2', 'No'),
            ], 'Exonerated Model 390', help="Exclusively to fill in the last "
            "period exonerated from the Annual Declaration-VAT summary. "
            "(Exempt from presenting the model 390 and with volume of "
            "operations zero).")
    annual_operation_volume = fields.Selection([
            ('0', ''),
            ('1', 'Yes'),
            ('2', 'No'),
            ], 'Exist operations annual volume (art. 121 LIVA)', states={
                'readonly': Eval('exonerated_mod390') != '1',
                'required': Eval('exonerated_mod390') == '1',
                }, help="Exclusively to fill in the last "
            "period exonerated from the Annual Declaration-VAT summary. "
            "(Exempt from presenting the model 390 and with volume of "
            "operations zero).")
    passive_subject_foral_administration = fields.Selection([
            ('1', 'Yes'),
            ('2', 'No'),
            ], 'Passive Subject on a Foral Administration', help="Passive "
            "Subject that tribute exclusively on a Foral Administration with "
            "an import TAX paid by Aduana pending entry.")
    taken_vat_book_to_aeat = fields.Selection([
            ('1', 'Yes'),
            ('2', 'No'),
            ], 'Taken the VAT Registration Book to AEAT', help="Have you "
            "voluntarily taken the VAT Registration Books through the AEAT's "
            "Electronic Office during the fiscal year?")
    company_vat = fields.Char('VAT')
    company_name = fields.Char('Company Name')
    complementary_declaration = fields.Boolean(
        'Complementary Declaration')
    previous_declaration_receipt = fields.Char(
        'Previous Declaration Receipt', size=13,
        states={
            'required': Bool(Eval('complementary_declaration')),
            },
        depends=['complementary_declaration'])
    auto_bankruptcy_declaration = fields.Selection([
            (' ', 'No'),
            ('1', 'Before Bankruptcy Proceeding'),
            ('2', 'After Bankruptcy Proceeding'),
            ], 'Auto Bankruptcy Declaration', required=True)
    auto_bankruptcy_date = fields.Date('Auto Bankruptcy Date')
    calculation_date = fields.DateTime('Calculation Date', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled')
            ], 'State', readonly=True)
    file_ = fields.Binary('File', filename='filename', states={
            'invisible': Eval('state') != 'done',
            }, readonly=True)
    filename = fields.Function(fields.Char("File Name"),
        'get_filename')

    @classmethod
    def __setup__(cls):
        super(Report, cls).__setup__()
        cls._order = [
            ('fiscalyear_code', 'DESC'),
            ('period', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['calculated',
                            'cancelled']),
                    },
                'calculate': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'process': {
                    'invisible': ~Eval('state').in_(['calculated']),
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['cancelled']),
                    },
                })
        cls._transitions |= set((
                ('draft', 'calculated'),
                ('draft', 'cancelled'),
                ('calculated', 'draft'),
                ('calculated', 'done'),
                ('calculated', 'cancelled'),
                ('done', 'cancelled'),
                ('cancelled', 'draft'),
                ))

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Module = pool.get('ir.module')
        cursor = Transaction().connection.cursor()
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)
        model_table = cls.__table__()
        module_table = Module.__table__()
        sql_table = ModelData.__table__()
        # Meld aeat_303_es into aeat_303
        cursor.execute(*module_table.update(
                columns=[module_table.state],
                values=[Literal('uninstalled')],
                where=module_table.name == Literal('aeat_303_es')
                ))
        cursor.execute(*sql_table.update(
                columns=[sql_table.module],
                values=[module_name],
                where=sql_table.module == Literal('aeat_303_es')))

        regime_type = table.column_exist('regime_type')
        complementary_declaration = table.column_exist(
            'complementary_declaration')
        joint_presentation_allowed = table.column_exist(
            'joint_presentation_allowed')

        super(Report, cls).__register__(module_name)

        # Migration to model 303 of 2015
        if not regime_type and table.column_exist('simplificated_regime'):
            # Don't use UPDATE FROM because SQLite nor MySQL support it.
            cursor.execute(*model_table.update(
                    columns=[model_table.regime_type],
                    values=['1'],
                    where=model_table.simplificated_regime == True))
            cursor.execute(*model_table.update(
                    columns=[model_table.regime_type],
                    values=['3'],
                    where=model_table.simplificated_regime == False))

            cursor.execute(*model_table.update(
                    columns=[model_table.type],
                    values=['U'],
                    where=model_table.simplificated_regime == False))

            table.not_null_action('simplificated_regime', action='remove')

        if not complementary_declaration and table.column_exist(
                'complementary_declaration'):
            # Don't use UPDATE FROM because SQLite nor MySQL support it.
            cursor.execute(*model_table.update(
                    columns=[model_table.complementary_declaration],
                    values=[True],
                    where=model_table.complementary_autoliquidation == 'X'))
            cursor.execute(*model_table.update(
                    columns=[model_table.complementary_declaration],
                    values=[False],
                    where=model_table.complementary_autoliquidation == ' '))

        if joint_presentation_allowed:
            table.not_null_action('joint_presentation_allowed',
                action='remove')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_complementary_declaration():
        return False

    @staticmethod
    def default_state_administration_percent():
        return 100

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_auto_bankruptcy_declaration():
        return ' '

    @staticmethod
    def default_deductible_compensations():
        return 0

    @staticmethod
    def default_deductible_investment_regularization():
        return 0

    @staticmethod
    def default_deductible_pro_rata_regularization():
        return 0

    @staticmethod
    def default_amount_to_compensate():
        return 0

    @staticmethod
    def default_joint_taxation_state_provincial_councils():
        return 0

    @staticmethod
    def default_previous_period_pending_amount_to_compensate():
        return 0

    @staticmethod
    def default_previous_period_amount_to_compensate():
        return 0

    @staticmethod
    def default_to_deduce():
        return 0

    @classmethod
    def default_company_party(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            return Company(company_id).party.id

    @classmethod
    def default_company_name(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            return Company(company_id).party.name.upper()

    @classmethod
    def default_company_vat(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            company = Company(company_id)
            vat_code = company.party.tax_identifier and \
                company.party.tax_identifier.code or None
            if vat_code and vat_code.startswith('ES'):
                return vat_code[2:]
            return vat_code

    @staticmethod
    def default_result_tax_regularitzation():
        return 0

    @staticmethod
    def default_aduana_tax_pending():
        return 0

    @staticmethod
    def default_exonerated_mod390():
        return '0'

    @staticmethod
    def default_annual_operation_volume():
        return '0'

    @staticmethod
    def default_passive_subject_foral_administration():
        return '2'

    @staticmethod
    def default_taken_vat_book_to_aeat():
        return '2'

    @staticmethod
    def default_info_territory_alava():
        return 0

    @staticmethod
    def default_info_territory_guipuzcoa():
        return 0

    @staticmethod
    def default_info_territory_vizcaya():
        return 0

    @staticmethod
    def default_info_territory_navarra():
        return 0

    @staticmethod
    def default_special_info_exempt_op_2bdeduced():
        return 0

    @staticmethod
    def default_special_info_farming_cattleraising_fishing():
        return 0

    @staticmethod
    def default_special_info_passive_subject_re():
        return 0

    @staticmethod
    def default_special_info_art_antiques_collectibles():
        return 0

    @staticmethod
    def default_special_info_travel_agency():
        return 0

    @staticmethod
    def default_special_info_delivery_investment_domestic_operations():
        return 0

    @staticmethod
    def default_information_taxation_reason_territory():
        return 0

    @staticmethod
    def default_accrued_vat_base_modification():
        return 0

    @staticmethod
    def default_accrued_vat_tax_modification():
        return 0

    @staticmethod
    def default_deductible_regularization_base():
        return 0

    @staticmethod
    def default_deductible_regularization_tax():
        return 0

    @staticmethod
    def default_regime_type():
        return '3'

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        if self.company:
            return self.company.party.id

    @fields.depends('company')
    def on_change_with_company_name(self, name=None):
        if self.company:
            return self.company.party.name.upper()

    @fields.depends('company')
    def on_change_with_company_vat(self, name=None):
        if self.company:
            tax_identifier = self.company.party.tax_identifier
            if tax_identifier and tax_identifier.code.startswith('ES'):
                return tax_identifier.code[2:]

    @fields.depends('fiscalyear')
    def on_change_with_fiscalyear_code(self):
        code = None
        if self.fiscalyear:
            code = self.fiscalyear.start_date.year
        return code

    @fields.depends('state_administration_amount',
        'aduana_tax_pending', 'previous_period_pending_amount_to_compensate')
    def set_previous_period_amount_to_compensate(self):
        result = ((self.state_administration_amount or _Z) +
            (self.aduana_tax_pending or _Z))
        if (result > 0 and (self.previous_period_pending_amount_to_compensate or
                    self.previous_period_pending_amount_to_compensate != _Z)):
            self.previous_period_amount_to_compensate = min(result,
                self.previous_period_pending_amount_to_compensate or _Z)

    @fields.depends(methods=['set_previous_period_amount_to_compensate'])
    def on_change_state_administration_amount(self):
        self.set_previous_period_amount_to_compensate()

    @fields.depends(methods=['set_previous_period_amount_to_compensate'])
    def on_change_aduana_tax_pending(self):
        self.set_previous_period_amount_to_compensate()

    @fields.depends(methods=['set_previous_period_amount_to_compensate'])
    def on_change_previous_period_pending_amount_to_compensate(self):
        self.set_previous_period_amount_to_compensate()

    @fields.depends('previous_report',
        methods=['set_previous_period_amount_to_compensate'])
    def on_change_previous_report(self):
        self.previous_period_pending_amount_to_compensate = (
            self.previous_report.result_previous_period_amount_to_compensate
            if self.previous_report else _Z)
        self.on_change_previous_period_pending_amount_to_compensate()

    def get_currency(self, name):
        return self.company.currency.id

    def get_general_regime_result(self, name):
        return (self.accrued_total_tax or _Z) - (self.deductible_total or _Z)

    def get_accrued_total_tax(self, name):
        return ((self.accrued_vat_tax_1 or _Z) +
            (self.accrued_vat_tax_2 or _Z) +
            (self.accrued_vat_tax_3 or _Z) +
            (self.intracommunity_adquisitions_tax or _Z) +
            (self.other_passive_subject_tax or _Z) +
            (self.accrued_vat_tax_modification or _Z) +
            (self.accrued_re_tax_1 or _Z) +
            (self.accrued_re_tax_2 or _Z) +
            (self.accrued_re_tax_3 or _Z) +
            (self.accrued_re_tax_modification or _Z)
                )

    def get_deductible_total(self, name):
        return ((self.deductible_current_domestic_operations_tax or _Z) +
            (self.deductible_investment_domestic_operations_tax or _Z) +
            (self.deductible_current_import_operations_tax or _Z) +
            (self.deductible_investment_import_operations_tax or _Z) +
            (self.deductible_current_intracommunity_operations_tax or _Z) +
            (self.deductible_investment_intracommunity_operations_tax or _Z) +
            (self.deductible_regularization_tax or _Z) +
            (self.deductible_compensations or _Z) +
            (self.deductible_investment_regularization or _Z) +
            (self.deductible_pro_rata_regularization or _Z)
                )

    def get_sum_results(self, name):
        # Here have to sum the box 46 + 58 + 76. The 58 is only for There
        #  Regime Simplified. By the moment this type are not supported so
        #  only sum 46 + 76.
        return ((self.general_regime_result or _Z) +
            (self.result_tax_regularitzation or _Z))

    def get_state_administration_amount(self, name):
        return (self.general_regime_result
            * (self.state_administration_percent or _Z)
            / Decimal('100.0'))

    def get_result_previous_period_amount_to_compensate(self, name):
        return ((self.previous_period_pending_amount_to_compensate or _Z)
            - (self.previous_period_amount_to_compensate or _Z))

    def get_result(self, name):
        return ((self.state_administration_amount or _Z)
            + (self.aduana_tax_pending or _Z)
            - (self.previous_period_amount_to_compensate or _Z)
            + (self.joint_taxation_state_provincial_councils or _Z))

    def get_liquidation_result(self, name):
        return self.result - self.to_deduce

    def get_filename(self, name):
        return 'aeat303-%s-%s.txt' % (
            self.fiscalyear_code, self.period)

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()
            report.check_compensate()

    def check_euro(self):
        if self.currency.code != 'EUR':
            raise UserError(gettext('aeat_303.msg_invalid_currency',
                name=self.rec_name,
                ))

    def check_compensate(self):
        result = ((self.state_administration_amount or _Z)
                + (self.aduana_tax_pending or _Z))
        if ((result <= _Z and self.previous_period_amount_to_compensate != _Z)
                or (result > _Z and (self.previous_period_amount_to_compensate
                    or _Z) > result)):
            raise UserError(gettext('aeat_303.msg_invalid_compensate'))

    @classmethod
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
        pool = Pool()
        Mapping = pool.get('aeat.303.mapping')
        Period = pool.get('account.period')
        TaxCode = pool.get('account.tax.code')

        mapping = {}
        fixed = {}
        for mapp in Mapping.search([('type_', '=', 'code')]):
            for code in mapp.code:
                mapping[code.id] = mapp.aeat303_field.name
        for mapp in Mapping.search([('type_', '=', 'numeric')]):
            fixed[mapp.aeat303_field.name] = mapp.number

        if len(fixed) == 0:
            raise UserError(gettext('aeat_303.no_config'))

        for report in reports:
            fiscalyear = report.fiscalyear
            period = report.period
            if 'T' in period:
                period = period[0]
                start_month = (int(period) - 1) * 3 + 1
                end_month = start_month + 2
            else:
                start_month = int(period)
                end_month = start_month

            year = fiscalyear.start_date.year
            lday = calendar.monthrange(year, end_month)[1]
            periods = [p.id for p in Period.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ('start_date', '>=', datetime.date(year, start_month, 1)),
                    ('end_date', '<=', datetime.date(year, end_month, lday))
                    ])]

            for field, value in fixed.items():
                setattr(report, field, value)
            for field in mapping.values():
                setattr(report, field, Decimal('0.0'))
            with Transaction().set_context(periods=periods):
                for tax in TaxCode.browse(mapping.keys()):
                    value = getattr(report, mapping[tax.id])
                    setattr(report, mapping[tax.id], value + tax.amount)
            report.save()

        cls.write(reports, {
                'calculation_date': datetime.datetime.now(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, reports):
        for report in reports:
            report.create_file()

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, reports):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, reports):
        pass

    def create_file(self):
        header = Record(aeat303.HEADER_RECORD)
        footer = Record(aeat303.FOOTER_RECORD)
        record = Record(aeat303.RECORD)
        general_record = Record(aeat303.GENERAL_RECORD)
        additional_record = Record(aeat303.ADDITIONAL_RECORD)
        columns = [x for x in self.__class__._fields if x not in
            ('report', 'bank_account')]
        for column in columns:
            value = getattr(self, column, None)
            if not value:
                continue
            if column == 'fiscalyear':
                value = str(self.fiscalyear_code)
            if column in header._fields:
                setattr(header, column, value)
            if column in record._fields:
                setattr(record, column, value)
            if column in general_record._fields:
                setattr(general_record, column, value)
            #If period is diffenret of 12/4T the fourth page will be without
            #   content.
            if self.period in ('12', '4T'):
                if column in additional_record._fields:
                    setattr(additional_record, column, value)
            if column in footer._fields:
                setattr(footer, column, value)
        record.bankruptcy = bool(self.auto_bankruptcy_declaration != ' ')
        if self.bank_account:
            for number in self.bank_account.numbers:
                if number.type == 'iban':
                    general_record.bank_account = number.number_compact
                    general_record.swift_bank = (
                        self.bank_account.bank and self.bank_account.bank.bic
                        or '')
                    break
        records = [header, record, general_record]
        if self.period in ('12', '4T'):
            records.append(additional_record)
        records.append(footer)
        data = retrofix_write(records, separator='')
        data = remove_accents(data).upper()
        if isinstance(data, str):
            data = data.encode('iso-8859-1')
        self.file_ = self.__class__.file_.cast(data)
        self.save()
