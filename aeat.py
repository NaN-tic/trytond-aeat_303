import retrofix
from retrofix import aeat303
from decimal import Decimal
import datetime
import calendar

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from sql import Literal


__all__ = ['Report', 'TemplateTaxCodeMapping', 'TemplateTaxCodeRelation',
    'TaxCodeMapping', 'TaxCodeRelation', 'CreateChart',
    'UpdateChart']

_STATES = {
    'readonly': Eval('state') == 'done',
    }

_DEPENDS = ['state']

__metaclass__ = PoolMeta

_Z = Decimal("0.0")


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
    number = fields.Numeric('Number', states={
            'required': Eval('type_') == 'numeric',
            'invisible': Eval('type_') != 'numeric',
        }, depends=['type_'])

    @classmethod
    def __setup__(cls):
        super(TemplateTaxCodeMapping, cls).__setup__()
        cls._sql_constraints += [
            ('aeat303_field_uniq', 'unique (aeat303_field)',
                'unique_field')
            ]
        cls._error_messages.update({
                'unique_field': 'Field must be unique.',
                })

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


class UpdateChart:
    __name__ = 'account.update_chart'

    def transition_update(self):
        pool = Pool()
        MappingTemplate = pool.get('aeat.303.template.mapping')
        Mapping = pool.get('aeat.303.mapping')
        ret = super(UpdateChart, self).transition_update()
        #Update current values
        ids = []
        for mapping in Mapping.search([]):
            if not mapping.template:
                continue
            vals = mapping.template._get_mapping_value(mapping=mapping)
            if vals:
                Mapping.write([mapping], vals)
            ids.append(mapping.template.id)

        company = self.start.account.company.id
        #Create new one's
        to_create = []
        for template in MappingTemplate.search([('id', 'not in', ids)]):
            vals = template._get_mapping_value()
            if vals:
                vals['company'] = company
                to_create.append(vals)
        if to_create:
            Mapping.create(to_create)
        return ret


class CreateChart:
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
    number = fields.Numeric('Number', states={
            'required': Eval('type_') == 'numeric',
            'invisible': Eval('type_') != 'numeric',
        }, depends=['type_'])
    template = fields.Many2One('aeat.303.template.mapping', 'Template')

    @classmethod
    def __setup__(cls):
        super(TaxCodeMapping, cls).__setup__()
        cls._sql_constraints += [
            ('aeat303_field_uniq', 'unique (company, aeat303_field)',
                'unique_field')
            ]
        cls._error_messages.update({
                'unique_field': 'Field must be unique.',
                })

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
    company_vat = fields.Char('VAT number', size=9, states={
            'required': Eval('state') == 'calculated',
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    first_name = fields.Char('First Name')
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
    simplificated_regime = fields.Boolean('Tribute exclusively on '
        'simplificated regime')
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
    difference = fields.Function(fields.Numeric('Difference', digits=(16, 2)),
        'get_difference')
    state_administration_percent = fields.Numeric(
        'State Administration Percent', digits=(16, 2))
    state_administration_amount = fields.Function(
        fields.Numeric('State Administration Amount', digits=(16, 2)),
        'get_state_administration_amount')
    previous_period_amount_to_compensate = fields.Numeric(
        'Previous Period Amount To Compensate', digits=(16, 2))
    intracommunity_deliveries = fields.Numeric(
        'Intracommunity Deliveries', digits=(16, 2))
    exports = fields.Numeric('Exports', digits=(16, 2))
    not_subject_or_reverse_charge = fields.Numeric(
        'Not Subject Or Reverse Charge', digits=(16, 2))
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
    without_activity = fields.Boolean('Without Activity')
    company_party = fields.Function(fields.Many2One('party.party',
            'Company Party'),
        'on_change_with_company_party')
    bank_account = fields.Many2One('bank.account', 'Bank Account',
        domain=[
            ('owners', '=', Eval('company_party')),
        ],
        depends=['company_party'])
    complementary_autoliquidation = fields.Selection([
            ('0', 'No'),
            ('1', 'Yes'),
            ], 'Complementary Autoliquidation')
    previous_declaration_receipt = fields.Numeric(
        'Previous Declaration Receipt', digits=(16, 2))
    joint_presentation_allowed = fields.Selection([
            (' ', 'No'),
            ('1', 'Yes'),
            ], 'Joint Presentation Allowed', required=True)
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
    file_ = fields.Binary('File', states={
            'invisible': Eval('state') != 'done',
            }, readonly=True)
    filename = fields.Function(fields.Char("File Name"),
        'get_filename')

    @classmethod
    def __setup__(cls):
        super(cls, Report).__setup__()
        cls._error_messages.update({
                'invalid_currency': ('Currency in AEAT 303 report "%s" must be'
                    ' Euro.'),
                'no_config': 'No configuration found for AEAT303. Please, '
                    'update your chart of accounts.'
                })
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
        Module = pool.get('ir.module.module')
        cursor = Transaction().cursor
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
        super(Report, cls).__register__(module_name)

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_payment_type():
        return '0'

    @staticmethod
    def default_complementary_autoliquidation():
        return '0'

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
    def default_fiscalyear_code():
        FiscalYear = Pool().get('account.fiscalyear')
        fiscalyear = FiscalYear.find(
            Transaction().context.get('company'), exception=False)
        if fiscalyear:
            try:
                fiscalyear = FiscalYear(fiscalyear)
                return int(fiscalyear.code)
            except (ValueError, TypeError):
                return None

    @staticmethod
    def default_compensation_fee():
        return 0

    @staticmethod
    def default_joint_presentation_allowed():
        return ' '

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

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        if self.company:
            return self.company.party.id

    @fields.depends('fiscalyear')
    def on_change_with_fiscalyear_code(self):
        try:
            return int(self.fiscalyear.code) if self.fiscalyear else None
        except (ValueError, TypeError):
            return None

    def get_currency(self, name):
        return self.company.currency.id

    def get_difference(self, name):
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

    def get_state_administration_amount(self, name):
        return (self.difference * self.state_administration_percent /
            Decimal('100.0'))

    def get_result(self, name):
        return (self.state_administration_amount -
            self.previous_period_amount_to_compensate +
            self.joint_taxation_state_provincial_councils)

    def get_liquidation_result(self, name):
        return self.result - self.to_deduce

    def get_filename(self, name):
        return 'aeat303-%s-%s.txt' % (
            self.fiscalyear_code, self.period)

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()

    def check_euro(self):
        if self.currency.code != 'EUR':
            self.raise_user_error('invalid_currency', self.rec_name)

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
            cls.raise_user_error('no_config')

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

            for field, value in fixed.iteritems():
                setattr(report, field, value)
            for field in mapping.values():
                setattr(report, field, Decimal('0.0'))
            with Transaction().set_context(periods=periods):
                for tax in TaxCode.browse(mapping.keys()):
                    value = getattr(report, mapping[tax.id])
                    setattr(report, mapping[tax.id], value + tax.sum)
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
        record = retrofix.Record(aeat303.RECORD)
        additional_record = retrofix.Record(aeat303.ADDITIONAL_RECORD)
        columns = [x for x in self.__class__._fields if x not in
            ('report', 'bank_account')]
        for column in columns:
            value = getattr(self, column, None)
            if not value:
                continue
            if column == 'first_name':
                column = 'company_name'
            if column == 'fiscalyear':
                value = str(self.fiscalyear_code)
            if column in record._fields:
                setattr(record, column, value)
            if column in additional_record._fields:
                setattr(additional_record, column, value)
        record.bankruptcy == bool(self.auto_bankruptcy_declaration != ' ')
        if self.bank_account:
            for number in self.bank_account.numbers:
                if number.type == 'iban':
                    additional_record.bank_account = number.number
                    break
        data = retrofix.write([record, additional_record])
        data = data.encode('iso-8859-1')
        self.file_ = bytes(data)
        self.save()
