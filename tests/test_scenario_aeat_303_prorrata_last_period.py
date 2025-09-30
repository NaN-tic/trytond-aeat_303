import datetime
import unittest
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import create_fiscalyear
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Imports
        today = datetime.date(datetime.date.today().year, 12, 15)
        last_year = today - relativedelta(years=1)

        # Install aeat_303
        activate_modules(['aeat_303', 'account_es', 'account_invoice'])

        # Create company
        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()

        # Create fiscal years
        last_fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company, today=last_year))
        last_fiscalyear.click('create_period')
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company, today=today))
        fiscalyear.click('create_period')

        # Create chart of accounts
        AccountTemplate = Model.get('account.account.template')
        Account = Model.get('account.account')
        account_template, = AccountTemplate.find([('parent', '=', None),
                                                  ('name', 'ilike',
                                                   'Plan General Contable%')])
        create_chart = Wizard('account.create_chart')
        create_chart.execute('account')
        create_chart.form.account_template = account_template
        create_chart.form.company = company
        create_chart.execute('create_account')
        receivable, = Account.find([
            ('type.receivable', '=', True),
            ('code', '=', '4300'),
            ('company', '=', company.id),
        ],
                                   limit=1)
        payable, = Account.find([
            ('type.payable', '=', True),
            ('code', '=', '4100'),
            ('company', '=', company.id),
        ],
                                limit=1)
        revenue, = Account.find([
            ('type.revenue', '=', True),
            ('code', '=', '7000'),
            ('company', '=', company.id),
        ],
                                limit=1)
        expense, = Account.find([
            ('type.expense', '=', True),
            ('code', '=', '600'),
            ('company', '=', company.id),
        ],
                                limit=1)
        create_chart.form.account_receivable = receivable
        create_chart.form.account_payable = payable
        create_chart.execute('create_properties')

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        identifier = party.identifiers.new()
        identifier.type = 'eu_vat'
        identifier.code = 'ES00000000T'
        party.save()

        # Create account category
        Tax = Model.get('account.tax')
        ProductCategory = Model.get('product.category')
        account_category1 = ProductCategory(name="Account Category")
        account_category1.accounting = True
        account_category1.account_expense = expense
        account_category1.account_revenue = revenue
        tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
        ],
                        limit=1)
        account_category1.customer_taxes.append(tax)
        tax, = Tax.find([
            ('group.kind', '=', 'purchase'),
            ('name', '=', 'IVA Deducible 21% (operaciones corrientes)'),
            ('parent', '=', None),
        ],
                        limit=1)
        account_category1.supplier_taxes.append(tax)
        account_category1.save()

        account_category2 = ProductCategory(name="Account Category")
        account_category2.accounting = True
        account_category2.account_expense = expense
        account_category2.account_revenue = revenue
        tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
        ],
                        limit=1)
        account_category2.customer_taxes.append(tax)
        tax, = Tax.find([
            ('group.kind', '=', 'purchase'),
            ('name', '=', '21% IVA no Deducible'),
            ('parent', '=', None),
        ],
                        limit=1)
        account_category2.supplier_taxes.append(tax)
        account_category2.save()

        # Create deductible product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        deductible_template = ProductTemplate()
        deductible_template.name = 'product_deductible'
        deductible_template.default_uom = unit
        deductible_template.type = 'goods'
        deductible_template.account_category = account_category1
        deductible_product, = deductible_template.products
        deductible_product.cost_price = Decimal('80')
        deductible_template.save()
        deductible_product, = deductible_template.products

        # Create non-deductible product
        total_template = ProductTemplate()
        total_template.name = 'product_non_deductible'
        total_template.default_uom = unit
        total_template.type = 'goods'
        total_template.account_category = account_category2
        total_product, = total_template.products
        total_product.cost_price = Decimal('80')
        total_template.save()
        total_product, = total_template.products

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create deductible invoice for last years prorrata
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.invoice_date = last_year
        invoice.type = 'in'
        invoice.party = party
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = deductible_product
        line.quantity = 90
        line.unit_price = Decimal(100)
        line.account = expense
        invoice.click('post')

        # Create deductible invoice for last years prorrata
        invoice = Invoice()
        invoice.invoice_date = last_year
        invoice.type = 'in'
        invoice.party = party
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = total_product
        line.quantity = 10
        line.unit_price = Decimal(100)
        line.account = expense
        invoice.click('post')

        # Prepare prorrata configuration
        Config = Model.get('account.configuration')
        config = Config(1)
        config.aeat303_prorrata_account, = Account.find([
            ('company', '=', company.id),
            ('code', '=', '634'),
        ], limit=1)
        config.aeat303_prorrata_fiscalyear = last_fiscalyear
        config.save()
        config.click('calculate_prorrata')
        self.assertEqual(config.aeat303_prorrata_percent, 90)

        # Create deductible invoice
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.invoice_date = today
        invoice.type = 'in'
        invoice.party = party
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = deductible_product
        line.quantity = 95
        line.unit_price = Decimal(100)
        line.account = expense
        invoice.click('post')

        # Create deductible invoice
        invoice = Invoice()
        invoice.invoice_date = today
        invoice.type = 'in'
        invoice.party = party
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = total_product
        line.quantity = 5
        line.unit_price = Decimal(100)
        line.account = expense
        invoice.click('post')

        # Generate 303 Report
        Report = Model.get('aeat.303.report')
        report = Report()
        report.year = today.year
        report.type = 'I'
        report.regime_type = '3'
        report.period = "%02d" % (today.month)
        report.return_sepa_check = '0'
        report.exonerated_mod390 = '0' if report.period != '12' else '2'
        report.company_vat = '123456789'
        report.click('calculate')
        self.assertEqual(report.deductible_current_domestic_operations_tax, Decimal('1795.50')) #Box value after applying prorrata (base value - base value * prorrata)
        self.assertEqual(report.deductible_investment_domestic_operations_tax, Decimal('0.00')) #No operation has been made that affects this box
        self.assertEqual(report.deductible_regularization_tax, Decimal('0.00')) #No operation has been made that affects this box
        self.assertEqual(report.preprorrata_deductible_current_domestic_operations_tax, Decimal('1995.00')) #Value before applying prorrata (base value)
        self.assertEqual(report.preprorrata_deductible_investment_domestic_operations_tax, Decimal('0.00')) #Thus, there was no previous value either
        self.assertEqual(report.preprorrata_deductible_regularization_tax, Decimal('0.00')) #Thus, there was no previous value either
        self.assertEqual(report.deductible_pro_rata_regularization, Decimal('99.75')) #Prorrata regularization, as the prorrata we have been aplying (90), is different from the one calculated for the current year (95) for the last period.

        # Test report is generated correctly
        report.file_
        report.click('process')
        self.assertEqual(bool(report.file_), True)

        # Test update config prorrata fiscalyear and percent
        config = Config(1)
        self.assertEqual(config.aeat303_prorrata_fiscalyear, fiscalyear)
        self.assertEqual(config.aeat303_prorrata_percent, 95)
        report.click('cancel')
        config = Config(1)
        self.assertEqual(config.aeat303_prorrata_fiscalyear, last_fiscalyear)
        self.assertEqual(config.aeat303_prorrata_percent, 90)
