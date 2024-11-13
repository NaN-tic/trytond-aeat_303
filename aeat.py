# -*- coding: utf-8 -*-
from decimal import Decimal
import datetime
import calendar
import unicodedata

from retrofix import aeat303
from retrofix.record import Record, write as retrofix_write
from trytond.model import Workflow, ModelSQL, ModelView, fields, Unique
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from sql import Literal
from sql.functions import Extract


_STATES = {
    'readonly': Eval('state') == 'done',
    }

_DEPENDS = ['state']

_STATES_390 = {
    'invisible': Eval('exonerated_mod390') != '1',
    }

_DEPENDS_390 = ['exonerated_mod390']

_Z = Decimal("0.0")


def remove_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text)
        if (unicodedata.category(c) != 'Mn'
                or c in ('\\u0327', '\\u0303'))  # Avoids normalize ç and ñ
        )
    # It converts nfd to nfc to allow unicode.decode()
    #return unicodedata.normalize('NFC', unicode_string_nfd)


class TemplateTaxCodeRelation(ModelSQL):
    '''
    AEAT 303 TaxCode Mapping Codes Relation
    '''
    __name__ = 'aeat.303.mapping-account.tax.code.template'

    mapping = fields.Many2One('aeat.303.template.mapping', 'Mapping',
        required=True)
    code = fields.Many2One('account.tax.code.template', 'Tax Code Template',
        required=True)


class TemplateTaxCodeMapping(ModelSQL):
    '''
    AEAT 303 TemplateTaxCode Mapping
    '''
    __name__ = 'aeat.303.template.mapping'

    aeat303_field = fields.Many2One('ir.model.field', 'Field',
        domain=[('module', '=', 'aeat_303')], required=True)
    type_ = fields.Selection([
            ('code', 'Code'),
            ('exonerated390', 'Exonerate 390'),
            ('numeric', 'Numeric')
            ], 'Type', required=True)
    code = fields.Many2Many('aeat.303.mapping-account.tax.code.template',
        'mapping', 'code', 'Tax Code Template', states={
            'invisible': Eval('type_') == 'numeric',
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

    mapping = fields.Many2One('aeat.303.mapping', 'Mapping', required=True)
    code = fields.Many2One('account.tax.code', 'Tax Code', required=True)


class TaxCodeMapping(ModelSQL, ModelView):
    '''
    AEAT 303 TaxCode Mapping
    '''
    __name__ = 'aeat.303.mapping'

    company = fields.Many2One('company.company', 'Company',
        ondelete="RESTRICT")
    aeat303_field = fields.Many2One('ir.model.field', 'Field',
        domain=[('module', '=', 'aeat_303')], required=True)
    type_ = fields.Selection([
            ('code', 'Code'),
            ('exonerated390', 'Exonerate 390'),
            ('numeric', 'Numeric')
            ], 'Type', required=True)
    code = fields.Many2Many('aeat.303.mapping-account.tax.code', 'mapping',
        'code', 'Tax Code', states={
            'required': Eval('type_') != 'numeric',
            'invisible': Eval('type_') == 'numeric',
        }, depends=['type_'])
    code_by_companies = fields.Function(
        fields.Many2Many('aeat.303.mapping-account.tax.code', 'mapping',
        'code', 'Tax Code', states={
            'required': Eval('type_') != 'numeric',
            'invisible': Eval('type_') == 'numeric',
        }, depends=['type_']), 'get_code_by_companies')
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

    @classmethod
    def get_code_by_companies(cls, records, name):
        user_company = Transaction().context.get('company')
        res = dict((x.id, None) for x in records)
        for record in records:
            code_ids = []
            for code in record.code:
                if not code.company or code.company.id == user_company:
                    code_ids.append(code.id)
            res[record.id] = code_ids
        return res


class Report(Workflow, ModelSQL, ModelView):
    '''
    AEAT 303 Report
    '''
    __name__ = 'aeat.303.report'

    # Header
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state').in_(['done', 'calculated']),
            }, depends=['state'])
    regime_type = fields.Selection([
            # ('1', 'Tribute exclusively on simplificated regime'),
            # ('2', 'Tribute on both simplified and general regime'),
            ('3', 'Tribute exclusively on general regime'),
            ], 'Tribute type', required=True, sort=False, states={
                'readonly': Eval('state').in_(['done', 'calculated']),
                }, depends=_DEPENDS)
    company_vat = fields.Char('VAT')
    company_name = fields.Char('Company Name')
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')

    # Page01
    type = fields.Selection([
            ('C', 'Application for compensation'),
            ('D', 'Return'),
            ('G', 'Current account tax - Revenue'),
            ('I', 'Income'),
            ('N', 'No activity / Zero result'),
            ('V', 'Current account tax - Returns'),
            ('U', 'Direct incomes in account'),
            ('X', 'Return by trasnfer to foreign account'),
            ], 'Declaration Type', required=True, sort=False, states=_STATES,
        depends=_DEPENDS)
    year = fields.Integer("Year", required=True,
        domain=[
            ('year', '>=', 1000),
            ('year', '<=', 9999)
            ],
        states={
            'readonly': Eval('state').in_(['done', 'calculated']),
            }, depends=_DEPENDS)
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
            ], 'Period', required=True, sort=False, states={
                'readonly': Eval('state').in_(['done', 'calculated']),
                }, depends=_DEPENDS)
    passive_subject_foral_administration = fields.Selection([
            ('1', 'Yes'),
            ('2', 'No'),
            ], 'Passive Subject on a Foral Administration', help="Passive "
        "Subject that tribute exclusively on a Foral Administration with "
        "an import TAX paid by Aduana pending entry.")
    monthly_return_subscription = fields.Boolean('Montly Return Subscription')
    joint_liquidation = fields.Boolean('Is joint liquidation')
    recc = fields.Boolean('Special Cash Criteria')
    recc_receiver = fields.Boolean('Special Cash Criteria Receiver')
    special_prorate = fields.Boolean('Special prorate')
    special_prorate_revocation = fields.Boolean('Special prorate revocation')
    auto_bankruptcy_date = fields.Date('Auto Bankruptcy Date')
    auto_bankruptcy_declaration = fields.Selection([
            (' ', 'No'),
            ('1', 'Before Bankruptcy Proceeding'),
            ('2', 'After Bankruptcy Proceeding'),
            ], 'Auto Bankruptcy Declaration', required=True)
    passive_subject_voluntarily_sii = fields.Selection([
            ('1', 'Yes'),
            ('2', 'No'),
            ], 'Passive Subject voluntarily opted for the SII')
    exonerated_mod390 = fields.Selection([
            ('0', ''),
            ('1', 'Yes'),
            ('2', 'No'),
            ], 'Exonerated Model 390', states={
                'readonly': ~Eval('period').in_(['12', '4T'])
            }, help="Exclusively to fill in the last period exonerated from "
            "the Annual Declaration-VAT summary. (Exempt from presenting the "
            "model 390 and with volume of operations zero).")
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
    accrued_vat_base_0 = fields.Numeric('Accrued Vat Base 0', digits=(15, 2))
    accrued_vat_percent_0 = fields.Numeric('Accrued Vat Percent 0',
        digits=(15, 2))
    accrued_vat_tax_0 = fields.Numeric('Accrued Vat Tax 0', digits=(15, 2))
    accrued_vat_base_1 = fields.Numeric('Accrued Vat Base 1', digits=(15, 2))
    accrued_vat_percent_1 = fields.Numeric('Accrued Vat Percent 1',
        digits=(15, 2))
    accrued_vat_tax_1 = fields.Numeric('Accrued Vat Tax 1', digits=(15, 2))
    accrued_vat_base_4 = fields.Numeric('Accrued Vat Base 4', digits=(15, 2))
    accrued_vat_percent_4 = fields.Numeric('Accrued Vat Percent 4',
        digits=(15, 2))
    accrued_vat_tax_4 = fields.Numeric('Accrued Vat Tax 4', digits=(15, 2))
    accrued_vat_base_2 = fields.Numeric('Accrued Vat Base 2', digits=(15, 2))
    accrued_vat_percent_2 = fields.Numeric('Accrued Vat Percent 2',
        digits=(15, 2))
    accrued_vat_tax_2 = fields.Numeric('Accrued Vat Tax 2', digits=(15, 2))
    accrued_vat_base_3 = fields.Numeric('Accrued Vat Base 3', digits=(15, 2))
    accrued_vat_percent_3 = fields.Numeric('Accrued Vat Percent 3',
        digits=(15, 2))
    accrued_vat_tax_3 = fields.Numeric('Accrued Vat Tax 3', digits=(15, 2))
    accrued_vat_base_5 = fields.Numeric('Accrued Vat Base 5', digits=(15, 2),
        states={'readonly': Bool(Eval('apply_old_tax'))}, depends=['apply_old_tax'])
    accrued_vat_percent_5 = fields.Numeric('Accrued Vat Percent 5',
        digits=(15, 2), states={'readonly': Bool(Eval('apply_old_tax'))},
        depends=['apply_old_tax'])
    accrued_vat_tax_5 = fields.Numeric('Accrued Vat Tax 5', digits=(15, 2),
        states={'readonly': Bool(Eval('apply_old_tax'))}, depends=['apply_old_tax'])
    intracommunity_adquisitions_base = fields.Numeric(
        'Intracommunity Adquisitions Base', digits=(15, 2))
    intracommunity_adquisitions_tax = fields.Numeric(
        'Intracommunity Adquisitions Tax', digits=(15, 2))
    other_passive_subject_base = fields.Numeric(
        'Other Passive Subject Adquisitions Base', digits=(15, 2))
    other_passive_subject_tax = fields.Numeric(
        'Other Passive Subject Adquisitions Tax', digits=(15, 2))
    accrued_vat_base_modification = fields.Numeric('Accrued Vat Base '
        'Modification', digits=(15, 2))
    accrued_vat_tax_modification = fields.Numeric('Accrued Vat Tax '
        'Modification', digits=(15, 2))
    accrued_re_base_4 = fields.Numeric('Accrued Re Base 4', digits=(15, 2))
    accrued_re_percent_4 = fields.Numeric('Accrued Re Percent 4',
        digits=(15, 2))
    accrued_re_tax_4 = fields.Numeric('Accrued Re Tax 4', digits=(15, 2))
    accrued_re_base_1 = fields.Numeric('Accrued Re Base 1', digits=(15, 2))
    accrued_re_percent_1 = fields.Numeric('Accrued Re Percent 1',
        digits=(15, 2))
    accrued_re_tax_1 = fields.Numeric('Accrued Re Tax 1', digits=(15, 2))
    accrued_re_base_2 = fields.Numeric('Accrued Re Base 2', digits=(15, 2))
    accrued_re_percent_2 = fields.Numeric('Accrued Re Percent 2',
        digits=(15, 2))
    accrued_re_tax_2 = fields.Numeric('Accrued Re Tax 2', digits=(15, 2))
    accrued_re_base_3 = fields.Numeric('Accrued Re Base 3', digits=(15, 2))
    accrued_re_percent_3 = fields.Numeric('Accrued Re Percent 3',
        digits=(15, 2))
    accrued_re_tax_3 = fields.Numeric('Accrued Re Tax 3', digits=(15, 2))
    accrued_re_tax_5 = fields.Numeric('Accrued Re Tax 5', digits=(15, 2),
        states={'readonly': Bool(Eval('apply_old_tax'))}, depends=['apply_old_tax'])
    accrued_re_base_5 = fields.Numeric('Accrued Re Base 5', digits=(15, 2),
        states={'readonly': Bool(Eval('apply_old_tax'))}, depends=['apply_old_tax'])
    accrued_re_percent_5 = fields.Numeric('Accrued Re Percent 5',
        digits=(15, 2), states={'readonly': Bool(Eval('apply_old_tax'))},
        depends=['apply_old_tax'])
    accrued_re_base_modification = fields.Numeric('Accrued Re Base '
        'Modification', digits=(15, 2))
    accrued_re_tax_modification = fields.Numeric('Accrued Re Tax '
        'Modification', digits=(15, 2))
    accrued_total_tax = fields.Function(fields.Numeric('Accrued Total Tax',
            digits=(15, 2)), 'get_accrued_total_tax')
    deductible_current_domestic_operations_base = fields.Numeric(
        'Deductible Current Domestic Operations Base', digits=(15, 2))
    deductible_current_domestic_operations_tax = fields.Numeric(
        'Deductible Current Domestic Operations Tax', digits=(15, 2))
    deductible_investment_domestic_operations_base = fields.Numeric(
        'Deductible Investment Domestic Operations Base', digits=(15, 2))
    deductible_investment_domestic_operations_tax = fields.Numeric(
        'Deductible Investment Domestic Operations Tax', digits=(15, 2))
    deductible_current_import_operations_base = fields.Numeric(
        'Deductible Current Import Operations Base', digits=(15, 2))
    deductible_current_import_operations_tax = fields.Numeric(
        'Deductible Current Import Operations Tax', digits=(15, 2))
    deductible_investment_import_operations_base = fields.Numeric(
        'Deductible Investment Import Operations Base', digits=(15, 2))
    deductible_investment_import_operations_tax = fields.Numeric(
        'Deductible Investment Import Operations Tax', digits=(15, 2))
    deductible_current_intracommunity_operations_base = fields.Numeric(
        'Deductible Current Intracommunity Operations Base', digits=(15, 2))
    deductible_current_intracommunity_operations_tax = fields.Numeric(
        'Deductible Current Intracommunity Operations Tax', digits=(15, 2))
    deductible_investment_intracommunity_operations_base = fields.Numeric(
        'Deductible Investment Intracommunity Operations Base', digits=(15, 2))
    deductible_investment_intracommunity_operations_tax = fields.Numeric(
        'Deductible Investment Intracommunity Operations Tax', digits=(15, 2))
    deductible_regularization_base = fields.Numeric(
        'Deductible Regularization Base', digits=(15, 2))
    deductible_regularization_tax = fields.Numeric(
        'Deductible Regularization Tax', digits=(15, 2))
    deductible_compensations = fields.Numeric('Deductible Compensations',
        digits=(15, 2))
    deductible_investment_regularization = fields.Numeric(
        'Deductible Investment Regularization', digits=(15, 2))
    deductible_pro_rata_regularization = fields.Numeric(
        'Deductible Pro Rata Regularization', digits=(15, 2))
    deductible_total = fields.Function(fields.Numeric('Deductible Total',
            digits=(15, 2)), 'get_deductible_total')
    general_regime_result = fields.Function(fields.Numeric(
            'General Regime Result',
            digits=(15, 2)), 'get_general_regime_result')

    # Page 03
    intracommunity_deliveries = fields.Numeric(
        'Intracommunity Deliveries', digits=(15, 2))
    exports = fields.Numeric('Exports', digits=(15, 2))
    not_subject_localitzation_rules = fields.Numeric("Not Subject To "
        "Localitzation Rules (Except For Those Included in Box 123)",
        digits=(15, 2))
    subject_operations_w_reverse_charge = fields.Numeric(
        "Subject Operations With Reverse Charge", digits=(15, 2))
    oss_not_subject_operations = fields.Numeric("OSS, Not Subject Operations",
        digits=(15, 2))
    oss_subject_operations = fields.Numeric("OSS, Subject Operations",
        digits=(15, 2))
    recc_deliveries_base = fields.Numeric(
        'Special Cash Criteria Deliveries Base', digits=(15, 2))
    recc_deliveries_tax = fields.Numeric(
        'Special Cash Criteria Deliveries Tax', digits=(15, 2))
    recc_adquisitions_base = fields.Numeric(
        'Special Cash Criteria Asquistions Base', digits=(15, 2))
    recc_adquisitions_tax = fields.Numeric(
        'Special Cash Criteria Adquistions Tax', digits=(15, 2))
    result_tax_regularitzation = fields.Numeric(
        'Tax Regularization art. 80.cinco.50a LIVA', digits=(15, 2),
        help="Only fill if you have done the 952 model. To Fill with the tax "
        "to recover.")
    sum_results = fields.Function(fields.Numeric(
            'Sum of Results', digits=(15, 2)), 'get_sum_results')
    state_administration_percent = fields.Numeric(
        'State Administration Percent', digits=(15, 2))
    state_administration_amount = fields.Function(
        fields.Numeric('State Administration Amount', digits=(15, 2)),
        'get_state_administration_amount')
    aduana_tax_pending = fields.Numeric(
        'Aduana Tax Pending', digits=(15, 2),
        help="Import VAT paid by Aduana pending entry")
    previous_report = fields.Many2One('aeat.303.report', 'Previous Report',
        states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    previous_period_pending_amount_to_compensate = fields.Numeric(
        'Previous Period Pending Amount To Compensate', digits=(15, 2),
        states={
            'readonly': Bool(Eval('previous_report')),
            }, depends=['previous_report'])
    previous_period_amount_to_compensate = fields.Numeric(
        'Previous Period Amount To Compensate', digits=(15, 2))
    result_previous_period_amount_to_compensate = fields.Function(
        fields.Numeric('Result Previous Period Amount To Compensate',
            digits=(15, 2)), 'get_result_previous_period_amount_to_compensate')
    joint_taxation_state_provincial_councils = fields.Numeric(
        'Joint Taxation State Provincial Councils', digits=(15, 2))
    result = fields.Function(fields.Numeric('Result', digits=(15, 2)),
        'get_result')
    before_result = fields.Numeric('Before Result', digits=(15, 2))
    to_deduce = fields.Numeric('To Deduce', digits=(15, 2))
    liquidation_result = fields.Function(fields.Numeric('Liquidation Result',
        digits=(15, 2)), 'get_liquidation_result')
    without_activity = fields.Boolean('Without Activity')
    complementary_declaration = fields.Boolean(
        'Complementary Declaration')
    complementary_declaration_modify_direct_debit = fields.Boolean(
        'Complementary Declaration Modify Direct Debit')
    complementary_declaration_other_adjustements = fields.Numeric(
        'Complementary Declaration Other Adjustements', digits=(15, 2))
    complementary_declaration_amount = fields.Numeric(
        'Complementary Declaration Amount', digits=(15, 2))
    complementary_declaration_rectification = fields.Boolean(
        'Complementary Declaration Rectification')
    complementary_declaration_administrative_discrepancy = fields.Boolean(
        'Complementary Declaration Administrative Discrepancy')
    previous_declaration_receipt = fields.Char(
        'Previous Declaration Receipt', size=13,
        states={
            'required': Bool(Eval('complementary_declaration')),
            },
        depends=['complementary_declaration'])

    # Page 04
    special_info_key_main = fields.Char('Main Activity Code',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_section_iae_main = fields.Char('Main IAE Code',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_key_others_1 = fields.Char('Activity Code (Other 1)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_section_iae_others_1 = fields.Char('IAE Code (Other 1)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_key_others_2 = fields.Char('Activity Code (Other 2)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_section_iae_others_2 = fields.Char('IAE Code (Other 2)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_key_others_3 = fields.Char('Activity Code (Other 3)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_section_iae_others_3 = fields.Char('IAE Code (Other 3)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_key_others_4 = fields.Char('Activity Code (Other 4)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_section_iae_others_4 = fields.Char('IAE Code (Other 4)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_key_others_5 = fields.Char('Activity Code (Other 5)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_section_iae_others_5 = fields.Char('IAE Code (Other 5)',
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_required_declare_third_party_operation = fields.Selection([
            (' ', 'No'),
            ('X', 'Yes'),
            ], 'Required declare Third Party Operations',
        help="Check if you have carried out transactions for which you are "
        "required to submit the annual declaration of transactions with "
        "third parties.", states=_STATES_390, depends=_DEPENDS_390)
    info_territory_alava = fields.Numeric(
        'Taxation Information by Territory: Alava', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    info_territory_guipuzcoa = fields.Numeric(
        'Taxation Information by Territory: Guipuzcoa', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    info_territory_vizcaya = fields.Numeric(
        'Taxation Information by Territory: Vizcaya', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    info_territory_navarra = fields.Numeric(
        'Taxation Information by Territory: Navarra', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    information_taxation_reason_territory = fields.Numeric(
        'Information on taxation by reason of territorya: Commo territory',
        digits=(3, 2), states=_STATES_390, depends=_DEPENDS_390)
    special_info_rg_operations = fields.Numeric(
        'Operations in General Regime', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_recc = fields.Numeric(
        'Operations Especial Regime Cash Criteria', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_intracommunity_deliveries_2bdeduced = fields.Numeric(
        'Intracommunity Delivery of Goods and Services', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_exempt_op_2bdeduced = fields.Numeric(
        'Exports and Other Exempt Oprations to be Deduce', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_exempt_op_wo_permission_2bdeduced = fields.Numeric(
        'Exempt Oprations without deduction right', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_w_passive_subject = fields.Numeric(
        'Not Subjected Operations', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    annual_subject_operations_w_reverse_charge = fields.Numeric(
        'Subjected Operations With Reverse Charge', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    annual_oss_not_subject_operations = fields.Numeric(
        'Not Subjected Operations Special Regime Unic Window', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    annual_oss_subject_operations = fields.Numeric(
        'Subjected Operations Special Regime Unic Window', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    annual_intragroup_transaction = fields.Numeric('Intragroup Transactions',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    special_info_operations_rs = fields.Numeric('Simplified Regime Operations',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    special_info_farming_cattleraising_fishing = fields.Numeric(
        'Especial Regime of Farming, Cattle rasing and Fishing',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    special_info_passive_subject_re = fields.Numeric(
        'Passive Subject on Equivalence Regime', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_art_antiques_collectibles = fields.Numeric(
        'Special Regime Operations on Art, Antiques and Collectibles',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    special_info_travel_agency = fields.Numeric(
        'Special Regime Operations on Travel Agency', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_financial_op_not_usual = fields.Numeric(
        'Operations Not Usual', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_delivery_investment_domestic_operations = fields.Numeric(
        'Delivery of Investment Domestic Operations', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    special_info_total = fields.Function(fields.Numeric(
            'Total Operations Volume', digits=(15, 2),
            states=_STATES_390, depends=_DEPENDS_390),
        'get_total_operations_volume')

    # Page 05
    additional_page_indicator = fields.Selection([
            (' ', 'No'),
            ('C', 'Yes'),
            ], 'Complementari Page Indicator',
        states=_STATES_390, depends=_DEPENDS_390)
    cnae1 = fields.Char('CNAE 1', states=_STATES_390, depends=_DEPENDS_390)
    operations_amount1 = fields.Numeric('Operations Amount 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    operations_amount_w_deduction1 = fields.Numeric(
        'Operations Amount With Deduction 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    prorrata_type1 = fields.Selection([
            ('G', 'G'),
            ('E', 'E'),
            (' ', 'None'),
            ], 'Prorrata Type 1', states=_STATES_390, depends=_DEPENDS_390)
    prorrata_percent1 = fields.Numeric(
        'Operations Amount With Deduction 1', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    cnae2 = fields.Char('CNAE 2', states=_STATES_390, depends=_DEPENDS_390)
    operations_amount2 = fields.Numeric('Operations Amount 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    operations_amount_w_deduction2 = fields.Numeric(
        'Operations Amount With Deduction 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    prorrata_type2 = fields.Selection([
            ('G', 'G'),
            ('E', 'E'),
            (' ', 'None'),
            ], 'Prorrata Type 2', states=_STATES_390, depends=_DEPENDS_390)
    prorrata_percent2 = fields.Numeric(
        'Operations Amount With Deduction 2', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    cnae3 = fields.Char('CNAE 3', states=_STATES_390, depends=_DEPENDS_390)
    operations_amount3 = fields.Numeric('Operations Amount 3', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    operations_amount_w_deduction3 = fields.Numeric(
        'Operations Amount With Deduction 3', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    prorrata_type3 = fields.Selection([
            ('G', 'G'),
            ('E', 'E'),
            (' ', 'None'),
            ], 'Prorrata Type 3', states=_STATES_390, depends=_DEPENDS_390)
    prorrata_percent3 = fields.Numeric(
        'Operations Amount With Deduction 3', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    cnae4 = fields.Char('CNAE 4', states=_STATES_390, depends=_DEPENDS_390)
    operations_amount4 = fields.Numeric('Operations Amount 4', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    operations_amount_w_deduction4 = fields.Numeric(
        'Operations Amount With Deduction 4', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    prorrata_type4 = fields.Selection([
            ('G', 'G'),
            ('E', 'E'),
            (' ', 'None'),
            ], 'Prorrata Type 4', states=_STATES_390, depends=_DEPENDS_390)
    prorrata_percent4 = fields.Numeric(
        'Operations Amount With Deduction 4', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    cnae5 = fields.Char('CNAE 5', states=_STATES_390, depends=_DEPENDS_390)
    operations_amount5 = fields.Numeric('Operations Amount 5', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    operations_amount_w_deduction5 = fields.Numeric(
        'Operations Amount With Deduction 5', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    prorrata_type5 = fields.Selection([
            ('G', 'G'),
            ('E', 'E'),
            (' ', 'None'),
            ], 'Prorrata Type 5', states=_STATES_390, depends=_DEPENDS_390)
    prorrata_percent5 = fields.Numeric(
        'Operations Amount With Deduction 5', digits=(3, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_domestic_operations_base1 = fields.Numeric(
        'Deductible Current Domestic Operations Base 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_domestic_operations_tax1 = fields.Numeric(
        'Deductible Current Domestic Operations Tax 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_domestic_operations_base1 = fields.Numeric(
        'Deductible Investment Domestic Operations Base 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_domestic_operations_tax1 = fields.Numeric(
        'Deductible Investment Domestic Operations Tax 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_import_operations_base1 = fields.Numeric(
        'Deductible Current Import Operations Base 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_import_operations_tax1 = fields.Numeric(
        'Deductible Current Import Operations Tax 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_import_operations_base1 = fields.Numeric(
        'Deductible Investment Import Operations Base 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_import_operations_tax1 = fields.Numeric(
        'Deductible Investment Import Operations Tax 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_intracommunity_operations_base1 = fields.Numeric(
        'Deductible Current Intracommunity Operations Base 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_intracommunity_operations_tax1 = fields.Numeric(
        'Deductible Current Intracommunity Operations Tax 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_intracommunity_operations_base1 = fields.Numeric(
        'Deductible Investment Intracommunity Operations Base 1',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_intracommunity_operations_tax1 = fields.Numeric(
        'Deductible Investment Intracommunity Operations Tax 1',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    deductible_compensations_base1 = fields.Numeric(
        'Deductible Compensations Base 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_compensations_tax1 = fields.Numeric(
        'Deductible Compensations Tax 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_regularization_base1 = fields.Numeric(
        'Deductible Regularization Base 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_regularization_tax1 = fields.Numeric(
        'Deductible Regularization Tax 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_regularization1 = fields.Numeric(
        'Deductible Investment Regularization 1', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_total1 = fields.Function(fields.Numeric(
            'Total Deductible 1', digits=(15, 2),
            states=_STATES_390, depends=_DEPENDS_390),
        'get_deductible_total1')
    deductible_current_domestic_operations_base2 = fields.Numeric(
        'Deductible Current Domestic Operations Base 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_domestic_operations_tax2 = fields.Numeric(
        'Deductible Current Domestic Operations Tax 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_domestic_operations_base2 = fields.Numeric(
        'Deductible Investment Domestic Operations Base 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_domestic_operations_tax2 = fields.Numeric(
        'Deductible Investment Domestic Operations Tax 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_import_operations_base2 = fields.Numeric(
        'Deductible Current Import Operations Base 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_import_operations_tax2 = fields.Numeric(
        'Deductible Current Import Operations Tax 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_import_operations_base2 = fields.Numeric(
        'Deductible Investment Import Operations Base 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_import_operations_tax2 = fields.Numeric(
        'Deductible Investment Import Operations Tax 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_intracommunity_operations_base2 = fields.Numeric(
        'Deductible Current Intracommunity Operations Base 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_current_intracommunity_operations_tax2 = fields.Numeric(
        'Deductible Current Intracommunity Operations Tax 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_intracommunity_operations_base2 = fields.Numeric(
        'Deductible Investment Intracommunity Operations Base 2',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_intracommunity_operations_tax2 = fields.Numeric(
        'Deductible Investment Intracommunity Operations Tax 2',
        digits=(15, 2), states=_STATES_390, depends=_DEPENDS_390)
    deductible_compensations_base2 = fields.Numeric(
        'Deductible Compensations Base 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_compensations_tax2 = fields.Numeric(
        'Deductible Compensations Tax 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_regularization_base2 = fields.Numeric(
        'Deductible Regularization Base 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_regularization_tax2 = fields.Numeric(
        'Deductible Regularization Tax 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_investment_regularization2 = fields.Numeric(
        'Deductible Investment Regularization 2', digits=(15, 2),
        states=_STATES_390, depends=_DEPENDS_390)
    deductible_total2 = fields.Function(fields.Numeric(
            'Total Deductible 2', digits=(15, 2),
            states=_STATES_390, depends=_DEPENDS_390),
        'get_deductible_total2')

    # Page DID
    company_party = fields.Function(fields.Many2One('party.party',
            'Company Party', context={
                'company': Eval('company', -1),
            },
            depends=['company']),
        'on_change_with_company_party')
    bank_account = fields.Many2One('bank.account', 'Bank Account',
        domain=[
            ('owners', '=', Eval('company_party')),
        ], states={
            'required': Eval('type').in_(['U', 'D', 'X']) or Bool(Eval('complementary_declaration_amount')),
            },
        depends=['company_party', 'type'])
    return_sepa_check = fields.Selection([
            ('0', 'Empty'),
            ('1', 'Spain account'),
            ('2', 'SEPA European Union'),
            ('3', 'Other countries'),
            ], 'Sepa Check On Return',
        states={
            'invisible': Eval('type') != 'X',
            'required': Bool(Eval('complementary_declaration_amount')),
            })
    swift_bank = fields.Char('Swift',
        states={
            'invisible': Eval('type') != 'X',
            })
    return_bank_name = fields.Char('Bank Name',
        states={
            'invisible': Eval('type') != 'X',
            'required': Bool(Eval('complementary_declaration_amount')),
            })
    return_bank_address = fields.Char('Bank Address',
        states={
            'invisible': Eval('type') != 'X',
            })
    return_bank_city = fields.Char('Bank City',
        states={
            'invisible': Eval('type') != 'X',
            })
    return_bank_country_code = fields.Char('Bank Country Code',
        states={
            'invisible': Eval('type') != 'X',
            })

    # Footer
    state = fields.Selection([
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled')
            ], 'State', readonly=True)
    calculation_date = fields.DateTime('Calculation Date', readonly=True)
    file_ = fields.Binary('File', filename='filename', states={
            'invisible': Eval('state') != 'done',
            }, readonly=True)
    filename = fields.Function(fields.Char("File Name"),
        'get_filename')

    # Create the account move. And check if need to post it and close
    # the period.
    move = fields.Many2One('account.move', 'Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    post_and_close = fields.Boolean("Post and Close",
        help='If checked the account move will be posted and the corresponding'
        ' period or periods will be closed.')
    move_account = fields.Many2One(
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
            'required': Bool(Eval('post_and_close')),
            },
        help='Account used for the counterpart in the creation of the account'
        ' move when generate the 303 model.')
    move_journal = fields.Many2One(
            'account.journal', "Journal for Move",
            states={
                'required': Bool(Eval('post_and_close')),
                },
            context={
                'company': Eval('company', -1),
                },
            help='Journal used for the counterpart in the creation of the '
            'account move when generate the 303 model.')
    move_description = fields.Char('Description for Move',
        states={
            'invisible': ~Bool(Eval('post_and_close')),
            },
        help='Optionaly you can add information to the account move if it is'
        ' created automatically.')

    #extras
    apply_old_tax = fields.Function(fields.Boolean('Apply Old Tax'),
        'get_apply_old_tax')

    @classmethod
    def __setup__(cls):
        super(Report, cls).__setup__()
        cls._order = [
            ('year', 'DESC'),
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
        FiscalYear = pool.get('account.fiscalyear')

        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        model_table = cls.__table__()
        module_table = Module.__table__()
        sql_table = ModelData.__table__()
        fiscalyear_table = FiscalYear.__table__()

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

        joint_presentation_allowed = table.column_exist(
            'joint_presentation_allowed')

        super(Report, cls).__register__(module_name)

        if joint_presentation_allowed:
            table.not_null_action('joint_presentation_allowed',
                action='remove')

        # migration fiscalyear to year
        if table.column_exist('fiscalyear'):
            query = model_table.update(columns=[model_table.year],
                    values=[Extract('YEAR', fiscalyear_table.start_date)],
                    from_=[fiscalyear_table],
                    where=model_table.fiscalyear == fiscalyear_table.id)
            cursor.execute(*query)
            table.drop_column('fiscalyear')
        if table.column_exist('fiscalyear_code'):
            table.drop_column('fiscalyear_code')

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
    def default_joint_taxation_state_provincial_councils():
        return 0

    @staticmethod
    def default_previous_period_pending_amount_to_compensate():
        return 0

    @staticmethod
    def default_previous_period_amount_to_compensate():
        return 0

    @staticmethod
    def default_before_result():
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
    def default_passive_subject_voluntarily_sii():
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

    @staticmethod
    def default_return_sepa_check():
        return '0'

    @staticmethod
    def default_special_info_required_declare_third_party_operation():
        return ' '

    @staticmethod
    def default_additional_page_indicator():
        return ' '

    @staticmethod
    def default_prorrata_type1():
        return ' '

    @staticmethod
    def default_prorrata_type2():
        return ' '

    @staticmethod
    def default_prorrata_type3():
        return ' '

    @staticmethod
    def default_prorrata_type4():
        return ' '

    @staticmethod
    def default_prorrata_type5():
        return ' '

    @classmethod
    def default_post_and_close(cls):
        pool = Pool()
        Configuration = pool.get('account.configuration')

        config = Configuration(1)
        return config.aeat303_post_and_close or False

    def get_apply_old_tax(self, name):
        if (self.year < 2024
            or (self.year == 2024
                and self.period not in ('4T', '10', '11', '12'))):
            return True
        return False

    @classmethod
    def default_move_account(cls):
        pool = Pool()
        Configuration = pool.get('account.configuration')

        config = Configuration(1)
        return (config.aeat303_move_account.id
            if config.aeat303_move_account else None)

    @classmethod
    def default_move_journal(cls):
        pool = Pool()
        Configuration = pool.get('account.configuration')

        config = Configuration(1)
        return (config.aeat303_move_journal.id
            if config.aeat303_move_journal else None)

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

    @fields.depends('exonerated_mod390', 'period')
    def on_change_with_exonerated_mod390(self, name=None):
        if self.period in ('4T', '12') and self.exonerated_mod390 == '0':
            return '2'
        elif self.period in ('4T', '12'):
            return self.exonerated_mod390
        else:
            return '0'

    @fields.depends('annual_operation_volume', 'exonerated_mod390')
    def on_change_with_annual_operation_volume(self, name=None):
        if self.exonerated_mod390 == '1':
            return self.annual_operation_volume
        else:
            return '0'

    @fields.depends('state_administration_amount',
        'aduana_tax_pending', 'previous_period_pending_amount_to_compensate')
    def set_previous_period_amount_to_compensate(self):
        result = ((self.state_administration_amount or _Z)
            + (self.aduana_tax_pending or _Z))
        if (result > 0 and (self.previous_period_pending_amount_to_compensate
                    or self.previous_period_pending_amount_to_compensate != _Z
                    )):
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

    @fields.depends('passive_subject_foral_administration', 'regime_type',
        'joint_liquidation', 'recc', 'recc_receiver', 'special_prorate',
        'special_prorate_revocation', 'auto_bankruptcy_declaration',
        'passive_subject_voluntarily_sii')
    def on_change_passive_subject_foral_administration(self):
        if self.passive_subject_foral_administration == '1':
            self.regime_type = '2'
            self.joint_liquidation = '2'
            self.recc = '2'
            self.recc_receiver = '2'
            self.special_prorate = '2'
            self.special_prorate_revocation = '2'
            self.auto_bankruptcy_declaration = '2'
            self.passive_subject_voluntarily_sii = '2'

    @fields.depends('bank_account', 'type', 'swift_bank', 'return_bank_name',
        'return_bank_address', 'return_bank_city', 'return_bank_country_code')
    def set_bank_account_information(self):
        if (self.bank_account and self.type and any(n.type == 'iban'
                    for n in self.bank_account.numbers)
                and self.type in ('X')):
            self.swift_bank = (self.bank_account.bank
                and self.bank_account.bank.bic or '')
            self.return_bank_name = (self.bank_account.bank
                and self.bank_account.bank.rec_name or '')
            self.return_bank_address = (self.bank_account.bank
                and self.bank_account.bank.party.addresses
                and ' '.join(
                    self.bank_account.bank.party.addresses[0].
                    full_address.replace('\n', '').split())
                or '')
            self.return_bank_city = (self.bank_account.bank
                and self.bank_account.bank.party.addresses
                and self.bank_account.bank.party.addresses[0].city
                or '')
            self.return_bank_country_code = (self.bank_account.bank
                and self.bank_account.bank.party.addresses
                and self.bank_account.bank.party.addresses[0].country
                and self.bank_account.bank.party.addresses[0].
                    country.code or '')
        else:
            if (self.bank_account and self.type and self.bank_account
                    and any(n.type == 'iban'
                        for n in self.bank_account.numbers)
                    and self.type in ('D')
                    and self.bank_account.numbers[0].number.startswith('ES')):
                self.return_sepa_check = '1'
            else:
                self.return_sepa_check = '0'
            self.swift_bank = ''
            self.return_bank_name = ''
            self.return_bank_address = ''
            self.return_bank_city = ''
            self.return_bank_country_code = ''

    @fields.depends(methods=['set_bank_account_information'])
    def on_change_bank_account(self):
        self.set_bank_account_information()

    @fields.depends(methods=['set_bank_account_information'])
    def on_change_type(self):
        self.set_bank_account_information()

    def get_currency(self, name):
        return self.company.currency.id

    def get_general_regime_result(self, name):
        return (self.accrued_total_tax or _Z) - (self.deductible_total or _Z)

    def get_accrued_total_tax(self, name):
        return ((self.accrued_vat_tax_0 or _Z)
            + (self.accrued_vat_tax_1 or _Z)
            + (self.accrued_vat_tax_4 or _Z)
            + (self.accrued_vat_tax_2 or _Z)
            + (self.accrued_vat_tax_3 or _Z)
            + (self.accrued_vat_tax_5 or _Z)
            + (self.intracommunity_adquisitions_tax or _Z)
            + (self.other_passive_subject_tax or _Z)
            + (self.accrued_vat_tax_modification or _Z)
            + (self.accrued_re_tax_4 or _Z)
            + (self.accrued_re_tax_1 or _Z)
            + (self.accrued_re_tax_2 or _Z)
            + (self.accrued_re_tax_3 or _Z)
            + (self.accrued_re_tax_5 or _Z)
            + (self.accrued_re_tax_modification or _Z)
                )

    def get_deductible_total(self, name):
        return ((self.deductible_current_domestic_operations_tax or _Z)
            + (self.deductible_investment_domestic_operations_tax or _Z)
            + (self.deductible_current_import_operations_tax or _Z)
            + (self.deductible_investment_import_operations_tax or _Z)
            + (self.deductible_current_intracommunity_operations_tax or _Z)
            + (self.deductible_investment_intracommunity_operations_tax or _Z)
            + (self.deductible_regularization_tax or _Z)
            + (self.deductible_compensations or _Z)
            + (self.deductible_investment_regularization or _Z)
            + (self.deductible_pro_rata_regularization or _Z)
                )

    def get_sum_results(self, name):
        # Here have to sum the box 46 + 58 + 76. The 58 is only for There
        #  Regime Simplified. By the moment this type are not supported so
        #  only sum 46 + 76.
        return ((self.general_regime_result or _Z)
            + (self.result_tax_regularitzation or _Z))

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
            + (self.joint_taxation_state_provincial_councils or _Z)
            + (self.complementary_declaration_other_adjustements or _Z))

    def get_liquidation_result(self, name):
        return ((self.result or _Z) - (self.to_deduce or _Z)
            + (self.before_result or _Z))

    def get_total_operations_volume(self, name):
        return ((self.special_info_rg_operations or _Z)
            + (self.special_info_recc or _Z)
            + (self.special_info_intracommunity_deliveries_2bdeduced or _Z)
            + (self.special_info_exempt_op_2bdeduced or _Z)
            + (self.special_info_exempt_op_wo_permission_2bdeduced or _Z)
            + (self.special_info_w_passive_subject or _Z)
            + (self.annual_subject_operations_w_reverse_charge or _Z)
            + (self.annual_oss_not_subject_operations or _Z)
            + (self.annual_oss_subject_operations or _Z)
            + (self.annual_intragroup_transaction or _Z)
            + (self.special_info_operations_rs or _Z)
            + (self.special_info_farming_cattleraising_fishing or _Z)
            + (self.special_info_passive_subject_re or _Z)
            + (self.special_info_art_antiques_collectibles or _Z)
            + (self.special_info_travel_agency or _Z)
            - (self.special_info_financial_op_not_usual or _Z)
            - (self.special_info_delivery_investment_domestic_operations
                    or _Z))

    def get_deductible_total1(self, name):
        return _Z

    def get_deductible_total2(self, name):
        return _Z

    def get_filename(self, name):
        return 'aeat303-%s-%s.txt' % (
            self.year, self.period)

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()
            report.check_compensate()
            report.check_type()
            report.check_sepa_check()
            report.check_exonerated_mod390()
            report.check_annual_operation_volume()
            report.check_prorrata_percent()

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

    def check_type(self):
        if (self.type and self.period and self.type == 'X'
                and self.period not in ('3T', '4T', '07', '08', '09', '10',
                    '11', '12')):
            raise UserError(gettext('aeat_303.msg_invalid_type_period',
                    report=self))

    def check_sepa_check(self):
        if self.type in ('D', 'X') and self.return_sepa_check == '0':
            raise UserError(gettext(
                    'aeat_303.msg_invalid_sepa_check',
                    report=self))

    def check_exonerated_mod390(self):
        if ((self.period not in ('12', '4T') and self.exonerated_mod390 != '0')
                or (self.period in ('12', '4T')
                and self.exonerated_mod390 == '0')):
            raise UserError(gettext(
                    'aeat_303.msg_invalid_exonerated_mod390',
                    report=self))

    def check_annual_operation_volume(self):
        if ((self.period not in ('12', '4T')
                    and self.annual_operation_volume != '0')
                or (self.period in ('12', '4T')
                and self.exonerated_mod390 == '1'
                and self.annual_operation_volume == '0')):
            raise UserError(gettext(
                    'aeat_303.msg_invalid_annual_operation_volume',
                    report=self))

    def check_prorrata_percent(self):
        if ((self.prorrata_percent1 or _Z) > Decimal('100.00')
                or (self.prorrata_percent2 or _Z) > Decimal('100.00')
                or (self.prorrata_percent3 or _Z) > Decimal('100.00')
                or (self.prorrata_percent4 or _Z) > Decimal('100.00')
                or (self.prorrata_percent5 or _Z) > Decimal('100.00')
                ):
            raise UserError(gettext(
                    'aeat_303.msg_invalid_prorrata_percent',
                    report=self))

    @classmethod
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
        pool = Pool()
        Mapping = pool.get('aeat.303.mapping')
        Period = pool.get('account.period')
        TaxCode = pool.get('account.tax.code')

        for report in reports:
            mapping = {}
            mapping_exonerated390 = {}
            fixed = {}
            for mapp in Mapping.search([
                    ('type_', '=', 'code'),
                    ('company', '=', report.company),
                    ]):
                for code in mapp.code_by_companies:
                    mapping[code.id] = mapp.aeat303_field.name
            for mapp in Mapping.search([
                    ('type_', '=', 'exonerated390'),
                    ('company', '=', report.company),
                    ]):
                for code in mapp.code_by_companies:
                    mapping_exonerated390[code.id] = mapp.aeat303_field.name
            for mapp in Mapping.search([
                    ('type_', '=', 'numeric'),
                    ('company', '=', report.company),
                    ]):
                fixed[mapp.aeat303_field.name] = mapp.number

            if len(fixed) == 0:
                raise UserError(gettext('aeat_303.msg_no_config'))

            year = report.year
            periods = report.get_periods()

            for field, value in fixed.items():
                setattr(report, field, value)
            for field in mapping.values():
                setattr(report, field, Decimal('0.0'))
            for field in mapping_exonerated390.values():
                setattr(report, field, Decimal('0.0'))

            # For the value of the field accrued_re_percent_1 we have to fill
            # 3 differents Recargos Equivalencia.
            # As Information note [1] say, whe have to show the value with the
            # max amount of the 3 possibles.
            #
            # https://sede.agenciatributaria.gob.es/Sede/Nota_informativa_sobre_los_nuevos_tipos_de_recargo_de_equivalencia__en_el_IVA.html
            if report.apply_old_tax:

                accrued_re_base_1 = {
                    '0.0': 0,
                    '0.5': 0,
                    '0.62': 0,
                    }
                with Transaction().set_context(periods=periods):
                    for tax in TaxCode.browse(mapping.keys()):
                        value = getattr(report, mapping[tax.id])
                        amount = (value or 0) + tax.amount
                        setattr(report, mapping[tax.id], amount)
                        if mapping[tax.id] == 'accrued_re_base_1':
                            for key in accrued_re_base_1.keys():
                                if key in tax.code:
                                    accrued_re_base_1[key] += tax.amount
                report.accrued_re_percent_1 = max(accrued_re_base_1,
                    key=accrued_re_base_1.get)
                report.accrued_vat_percent_4 = Decimal('5.0')
            else:
                accrued_re_base_5 = {
                    '0.26': 0,
                    '0.5': 0,
                    }
                with Transaction().set_context(periods=periods):
                    for tax in TaxCode.browse(mapping.keys()):
                        value = getattr(report, mapping[tax.id])
                        amount = (value or 0) + tax.amount
                        setattr(report, mapping[tax.id], amount)
                        if mapping[tax.id] == 'accrued_re_base_5':
                            for key in accrued_re_base_5.keys():
                                if key in tax.code:
                                    accrued_re_base_5[key] += tax.amount
                report.accrued_re_percent_5 = max(accrued_re_base_5,
                    key=accrued_re_base_5.get)

            if report.period in ('12', '4T'):
                periods = [p.id for p in Period.search([
                        ('start_date', '>=', datetime.date(year, 1, 1)),
                        ('end_date', '<=', datetime.date(year, 12, 31)),
                        ('company', '=', report.company),
                        ])]
                with Transaction().set_context(periods=periods):
                    for tax in TaxCode.browse(
                            mapping_exonerated390.keys()):
                        value = getattr(
                            report, mapping_exonerated390[tax.id])
                        amount = (value or 0) + tax.amount
                        setattr(report, mapping_exonerated390[tax.id],
                            amount)

            report.save()

        cls.write(reports, {
                'calculation_date': datetime.datetime.now(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, reports):
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        for report in reports:
            report.create_file()
            report.create_move()
            # Means that we have to post the move created and close the
            # period or periods related.
            if report.post_and_close:
                periods = report.get_periods()
                Move.post([report.move])
                Period.close(Period.browse(periods))

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, reports):
        pool = Pool()
        Move = pool.get('account.move')

        to_update = []
        for report in reports:
            move = report.move
            if not move:
                continue
            for line in move.lines:
                if line.reconciliation is not None:
                    raise UserError(
                        gettext('aeat_303.msg_not_possible_cancel',
                            report=report.id))
            to_update.append(report)
        if to_update:
            moves = [x.move for x in to_update]
            Move.draft(moves)
            Move.delete(moves)
            cls.write(to_update, {'move': None,})

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
        annual_resume_record = Record(aeat303.ANNUAL_RESUME_RECORD)
        annual_additional_record = Record(
           aeat303.ANNUAL_RESUME_ADDITIONAL_RECORD)
        bank_data_record = Record(aeat303.BANK_DATA_RECORD)
        columns = [x for x in self.__class__._fields if x not in
            ('report', 'bank_account')]
        for column in columns:
            value = getattr(self, column, None)
            if not value:
                continue
            if column == 'year':
                value = str(self.year)
            if column in header._fields:
                setattr(header, column, value)
            if column in record._fields:
                setattr(record, column, value)
            if column in general_record._fields:
                setattr(general_record, column, value)
            # If period is diffenret of 12/4T the 4 and 5 page will be without
            #   content.
            ## if self.period in ('12', '4T'):
            ##     if column in annual_resume_record._fields:
            ##         setattr(annual_resume_record, column, value)
            ##     if column in annual_additional_record._fields:
            ##         setattr(annual_additional_record, column, value)
            if column in bank_data_record._fields:
                setattr(bank_data_record, column, value)
            if column in footer._fields:
                setattr(footer, column, value)
        record.bankruptcy = bool(self.auto_bankruptcy_declaration != ' ')
        bank_data_record.bank_account = next((n.number_compact
                for n in self.bank_account.numbers
                if n.type == 'iban'), '') if self.bank_account else ''
        ## if self.period in ('12', '4T'):
        ##     records = [header, record, general_record, annual_resume_record,
        ##         annual_additional_record, bank_data_record]
        ## else:
        ##     records = [header, record, general_record, bank_data_record]
        records = [header, record, general_record, bank_data_record]
        records.append(footer)
        try:
            data = retrofix_write(records, separator='')
        except AssertionError as e:
            raise UserError(str(e))
        data = remove_accents(data).upper()
        if isinstance(data, str):
            data = data.encode('iso-8859-1', errors='ignore')
        self.file_ = self.__class__.file_.cast(data)
        self.save()

    def create_move(self):
        pool = Pool()
        Mapping = pool.get('aeat.303.mapping')
        TaxCode = pool.get('account.tax.code')
        Tax = pool.get('account.tax')
        TaxLine = pool.get('account.tax.line')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        # If this two fields are not set, means not required to create
        # the AEAT303 move.
        if (not self.move_account or not self.move_journal):
            return

        codes = []
        # Get all the codes from AEAT303 Mapping table.
        for mapp in Mapping.search([
                ('type_', '=', 'code'),
                ('company', '=', self.company),
                ]):
            codes.extend((x.id for x in mapp.code_by_companies))
        if not codes:
            return

        periods = self.get_periods()
        description = self.move_description or 'AEAT 303'
        with Transaction().set_context(periods=periods):
            mapp_code_lines = {}
            for code in TaxCode.browse(codes):
                if not code.amount:
                    continue

                # To create the AEAT303 account move need the last level of a
                # code tree, so search all the child of the code and us only
                # the child without childs, last level.
                children = []
                childs = TaxCode.search([
                        ('parent', 'child_of', [code]),
                        ])
                if len(childs) == 1:
                    children = childs
                else:
                    for child in childs:
                        if not child.childs and child.amount:
                            children.append(child)
                # Only create the domain for the tax codes that are "Tax",
                # not "Base".
                # With that doamin, get the related account tax lines, to get
                # the related account move, so could be done the counterpart
                # account move.
                for child in children:
                    if not child.lines:
                        continue
                    domain = [['OR'] + [x._line_domain for x in child.lines
                        if x.amount == 'tax']]
                    if domain == [['OR']]:
                        continue
                    #domain += Tax._amount_domain()
                    domain.extend(Tax._amount_domain())
                    tax_lines = TaxLine.search(domain)
                    mapp_code_lines[child] = [x.move_line for x in tax_lines]
            if not mapp_code_lines:
                return

            # Create the AET303 move with the move lines obtained fron tax
            # code.
            move = Move()
            move.journal = self.move_journal
            move.period = periods[-1]
            move.date = move.period.end_date
            move.origin = self
            move.state = 'draft'
            move.description = description
            move.save()

            move_lines = {}
            for code, lines in mapp_code_lines.items():
                for line in lines:
                    key = (code, line.account)
                    if key in move_lines:
                        move_lines[key].credit += line.debit
                        move_lines[key].debit += line.credit
                    else:
                        move_line = MoveLine()
                        move_line.move = move
                        move_line.account = line.account
                        move_line.credit = line.debit
                        move_line.debit = line.credit
                        move_line.description = code.name
                        # TODO: Control if analytic exist
                        move_lines[key] = move_line
        counterpart_line = MoveLine()
        counterpart_line.move = move
        counterpart_line.account = self.move_account
        if self.liquidation_result >= 0:
            counterpart_line.credit = self.liquidation_result
            counterpart_line.debit = _Z
        else:
            counterpart_line.debit = -1 * self.liquidation_result
            counterpart_line.credit = _Z
        counterpart_line.description = description
        # Ensure that all the moves are set only the debit or credit,
        # not both either 0 on both.
        lines = []
        for key, line in move_lines.items():
            if line.debit and line.credit:
                balance = line.debit - line.credit
                if balance == _Z:
                    continue
                elif balance >= _Z:
                    line.debit = balance
                    line.credit = _Z
                else:
                    line.credit = -balance
                    line.debit = _Z
            lines.append(line)
        MoveLine.save(lines + [counterpart_line])
        self.move = move
        self.save()

    def get_periods(self):
        pool = Pool()
        Period = pool.get('account.period')

        period = self.period
        if 'T' in period:
            period = period[0]
            start_month = (int(period) - 1) * 3 + 1
            end_month = start_month + 2
        else:
            start_month = int(period)
            end_month = start_month
        year = self.year
        lday = calendar.monthrange(year, end_month)[1]
        periods = [p.id for p in Period.search([
                ('start_date', '>=', datetime.date(year, start_month, 1)),
                ('end_date', '<=', datetime.date(year, end_month, lday)),
                ('company', '=', self.company),
                ('type', '=', 'standard'),
                ], order=[('end_date', 'ASC')])]
        return periods
