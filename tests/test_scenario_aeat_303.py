import datetime
import unittest
from decimal import Decimal

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
        today = datetime.date.today()

        # Install aeat_303
        activate_modules(['aeat_303', 'account_es', 'account_invoice'])

        # Create company
        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
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
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
        ],
                        limit=1)
        account_category.customer_taxes.append(tax)
        tax, = Tax.find([
            ('group.kind', '=', 'purchase'),
            ('name', '=', 'IVA Deducible 21% (operaciones corrientes)'),
            ('parent', '=', None),
        ],
                        limit=1)
        account_category.supplier_taxes.append(tax)
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('40')
        template.account_category = account_category
        product, = template.products
        product.cost_price = Decimal('25')
        template.save()
        product, = template.products

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create out invoice
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = party
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.unit_price = Decimal('40.0')
        line.quantity = 5
        self.assertEqual(len(line.taxes), 1)
        self.assertEqual(line.amount, Decimal('200.00'))
        line = invoice.lines.new()
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        self.assertEqual(line.amount, Decimal('20.00'))
        line = invoice.lines.new()
        self.assertEqual(len(line.taxes), 0)
        line.account = revenue
        line.description = 'Test 2'
        line.quantity = 1
        line.unit_price = Decimal(40)
        tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
            ], limit=1)
        line.taxes.append(tax)
        self.assertEqual(line.amount, Decimal('40.00'))
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
        self.assertEqual(report.accrued_vat_base_3, Decimal('240.00'))
        self.assertEqual(report.accrued_vat_tax_3, Decimal('50.40'))

        # Test report is generated correctly
        report.file_
        report.click('process')
        self.assertEqual(bool(report.file_), True)
