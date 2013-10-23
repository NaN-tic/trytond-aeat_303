import retrofix
from retrofix import aeat303
from decimal import Decimal
import datetime
import calendar

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

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

    mapping = fields.Many2One('aeat.303.template.mapping', 'Mapping')
    code = fields.Many2One('account.tax.code.template', 'Tax Code Template')


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
        if mapping and len(mapping.code) > 0:
            res['code'].append(['unlink_all'])
        if len(self.code) > 0:
            ids = [c.id for c in TaxCode.search([
                        ('template', 'in', [c.id for c in self.code])
                        ])]
            res['code'].append(['set', ids])
        if not mapping or mapping.template != self:
            res['template'] = self.id
        if len(res['code']) == 0:
            del res['code']
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
            vals = mapping.template._get_mapping_value(mapping=mapping)
            if vals:
                Mapping.write([mapping], vals)
            if mapping.template:
                ids.append(mapping.template.id)

        company = self.start.account.company.id
        #Create new one's
        to_create = []
        for template in MappingTemplate.search([('id', 'not in', ids)]):
            vals = template._get_mapping_value()
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
            vals['company'] = company
            to_create.append(vals)

        Mapping.create(to_create)
        return ret


class TaxCodeRelation(ModelSQL):
    '''
    AEAT 303 TaxCode Mapping Codes Relation
    '''
    __name__ = 'aeat.303.mapping-account.tax.code'

    mapping = fields.Many2One('aeat.303.mapping', 'Mapping')
    code = fields.Many2One('account.tax.code', 'Tax Code')


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
    fiscalyear_code = fields.Integer('Fiscal Year Code',
        on_change_with=['fiscalyear'], required=True)
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
    intracommunity_adquisitions_base = fields.Numeric(
        'Intracommunity Adquisitions Base', digits=(16, 2))
    intracommunity_adquisitions_tax = fields.Numeric(
        'Intracommunity Adquisitions Tax', digits=(16, 2))
    accrued_total_tax = fields.Numeric('Accrued Total Tax', digits=(16, 2))
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
    without_activity = fields.Boolean('Without Activity')
    refund_amount = fields.Numeric('Refund Amount', digits=(16, 2))
    refund_bank_account = fields.Numeric('Refund Bank Account', digits=(16, 2))
    payment_type = fields.Selection([
            ('0', 'N/A'),
            ('1', 'Cash'),
            ('2', 'Debit Entry'),
            ('3', 'Direct Billing'),
            ], 'Payment Type')
    payment_amount = fields.Numeric('Payment Amount', digits=(16, 2))
    payment_bank_account = fields.Char('Payment Bank Account', size=20)
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
    signature_city = fields.Char('Signature City', size=16)
    signature_day = fields.Char('Signature Day', size=2)
    signature_month = fields.Char('Signature Month', size=10)
    signature_year = fields.Char('Signature Year', size=4)
    calculation_date = fields.DateTime('Calculation Date', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled')
            ], 'State', readonly=True)
    file_ = fields.Binary('File', states={
            'invisible': Eval('state') != 'done',
            })

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

    def on_change_with_fiscalyear_code(self):
        return self.fiscalyear.code if self.fiscalyear else None

    def get_currency(self, name):
        return self.company.currency.id

    def get_difference(self, name):
        return (self.accrued_total_tax or _Z) - (self.deductible_total or _Z)

    def get_deductible_total(self, name):
        return ((self.deductible_current_domestic_operations_tax or _Z) +
            (self.deductible_investment_domestic_operations_tax or _Z) +
            (self.deductible_current_import_operations_tax or _Z) +
            (self.deductible_investment_import_operations_tax or _Z) +
            (self.deductible_current_intracommunity_operations_tax or _Z) +
            (self.deductible_investment_intracommunity_operations_tax or _Z) +
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
            multiplier = 1
            period = report.period
            if 'T' in period:
                period = period[0]
                multiplier = 3

            start_month = int(period) * multiplier
            end_month = start_month + multiplier

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
        columns = [getattr(self, x) for x in dir(self)
            if isinstance(getattr(self, x), fields.Field)]
        columns = [x for x in columns if x.name not in ('report',)]
        for column in columns:
            value = record[column]
            if column == 'without_activity':
                value = '1' if value else '0'
            setattr(record, column, record[column])
        data = retrofix.write([record])
        data = data.encode('iso-8859-1')
        self.file_ = buffer(data)
        self.save()
