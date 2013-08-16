import retrofix
from retrofix import aeat303
import datetime

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval

__all__ = ['Report']

_STATES={
    'readonly': Eval('state') == 'done',
    }

_DEPENDS=['state']


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
            ('1T','First quarter'),
            ('2T','Second quarter'),
            ('3T','Third quarter'),
            ('4T','Fourth quarter'),
            ('01','January'),
            ('02','February'),
            ('03','March'),
            ('04','April'),
            ('05','May'),
            ('06','June'),
            ('07','July'),
            ('08','August'),
            ('09','September'),
            ('10','October'),
            ('11','November'),
            ('12','December'),
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
    deductible_total = fields.Numeric('Deductible Total', digits=(16, 2))
    difference = fields.Numeric('Difference', digits=(16, 2))
    state_administration_percent = fields.Numeric(
        'State Administration Percent', digits=(16, 2))
    state_administration_amount = fields.Numeric('State Administration Amount',
        digits=(16, 2))
    previous_period_amount_to_compensate = fields.Numeric(
        'Previous Period Amount To Compensate', digits=(16, 2))
    intracommunity_deliveries = fields.Numeric(
        'Intracommunity Deliveries', digits=(16, 2))
    exports = fields.Numeric('Exports', digits=(16, 2))
    not_subject_or_reverse_charge = fields.Numeric(
        'Not Subject Or Reverse Charge', digits=(16, 2))
    joint_taxation_state_provincial_councils = fields.Numeric(
        'Joint Taxation State Provincial Councils', digits=(16, 2))
    result = fields.Numeric('Result', digits=(16, 2))
    to_deduce = fields.Numeric('To Deduce', digits=(16, 2))
    liquidation_result = fields.Numeric('Liquidation Result', digits=(16, 2))
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
                'invalid_currency': ('Currency in AEAT 303 report "%s" must be '
                    'Euro.')
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
    def default_state_percent():
        return 100

    @staticmethod
    def default_compensation_fee():
        return 0

    @staticmethod
    def default_joint_presentation_allowed():
        return ' '

    @staticmethod
    def default_auto_bankruptcy_declaration():
        return ' '

    def on_change_with_fiscalyear_code(self):
        return self.fiscalyear.code if self.fiscalyear else None

    def get_currency(self, name):
        return self.company.currency.id

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
        record = retrofix.Record(retrofix.aeat303.RECORD)
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
