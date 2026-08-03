import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.exceptions import UserWarning
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
        today = datetime.date.today()

        test_config = activate_modules(
            ['aeat_303', 'account_es', 'account_invoice'])

        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()
        company.deferred_dua_tax = True
        company.save()

        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

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
        ], limit=1)
        payable, = Account.find([
            ('type.payable', '=', True),
            ('code', '=', '4100'),
            ('company', '=', company.id),
        ], limit=1)
        alt_payable, = Account.find([
            ('type.payable', '=', True),
            ('code', '=', '4000'),
            ('company', '=', company.id),
        ], limit=1)
        revenue, = Account.find([
            ('type.revenue', '=', True),
            ('code', '=', '7000'),
            ('company', '=', company.id),
        ], limit=1)
        expense, = Account.find([
            ('type.expense', '=', True),
            ('code', '=', '600'),
            ('company', '=', company.id),
        ], limit=1)
        move_account, = Account.find([
            ('code', '=', '4750'),
            ('type', '!=', None),
            ('type.expense', '=', False),
            ('type.revenue', '=', False),
            ('type.debt', '=', False),
            ('company', '=', company.id),
        ], limit=1)
        create_chart.form.account_receivable = receivable
        create_chart.form.account_payable = payable
        create_chart.execute('create_properties')

        Config = Model.get('account.configuration')
        Mapping = Model.get('aeat.303.mapping')
        config = Config(1)
        config.aeat303_deferred_dua_account = payable
        config.save()

        mappings = Mapping.find([
            ('company', '=', company.id),
            ('aeat303_field.name', '=', 'aduana_tax_pending'),
        ])
        for mapping in mappings:
            for code in list(mapping.code_by_companies):
                mapping.code_by_companies.remove(code)
            mapping.save()

        Party = Model.get('party.party')
        party = Party(name='Party')
        identifier = party.identifiers.new()
        identifier.type = 'eu_vat'
        identifier.code = 'ES00000000T'
        party.account_payable = alt_payable
        party.save()

        Tax = Model.get('account.tax')
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name='Account Category')
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        sale_tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
        ], limit=1)
        account_category.customer_taxes.append(sale_tax)
        account_category.save()

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

        payment_term = create_payment_term()
        payment_term.save()

        import_tax, = Tax.find([
            ('group.kind', '=', 'purchase'),
            ('name', '=', 'IVA 21% Importaciones (Bienes corrientes)'),
            ('parent', '=', None),
        ], limit=1)

        Invoice = Model.get('account.invoice')
        sale_invoice = Invoice(type='out')
        sale_invoice.party = party
        sale_invoice.payment_term = payment_term
        line = sale_invoice.lines.new()
        line.product = product
        line.unit_price = Decimal('40.0')
        line.quantity = 5
        line = sale_invoice.lines.new()
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        line = sale_invoice.lines.new()
        line.account = revenue
        line.description = 'Test 2'
        line.quantity = 1
        line.unit_price = Decimal(40)
        sale_tax, = Tax.find([
            ('group.kind', '=', 'sale'),
            ('name', '=', 'IVA 21%'),
            ('parent', '=', None),
        ], limit=1)
        line.taxes.append(sale_tax)
        sale_invoice.click('post')

        included_dua = Invoice()
        included_dua.type = 'in'
        included_dua.invoice_date = today
        included_dua.party = party
        included_dua.payment_term = payment_term
        included_tax = included_dua.taxes.new()
        included_tax.manual = True
        included_tax.tax = import_tax
        included_tax.base = Decimal('100.00')
        self.assertTrue(included_tax.deferred_dua_tax)
        with self.assertRaises(UserWarning):
            included_dua.click('post')

        Warning = Model.get('res.user.warning')
        Warning(user=test_config.user,
            name='aeat303_deferred_dua_account_change_%s' % included_dua.id,
            always=True).save()
        included_dua.click('post')
        self.assertEqual(included_dua.account.id, payable.id)

        excluded_dua = Invoice()
        excluded_dua.type = 'in'
        excluded_dua.invoice_date = today
        excluded_dua.party = party
        excluded_dua.payment_term = payment_term
        excluded_tax = excluded_dua.taxes.new()
        excluded_tax.manual = True
        excluded_tax.tax = import_tax
        excluded_tax.base = Decimal('100.00')
        excluded_tax.deferred_dua_tax = False
        excluded_dua.click('post')
        self.assertEqual(excluded_dua.account.id, alt_payable.id)

        Journal = Model.get('account.journal')
        move_journal, = Journal.find([('code', '=', 'MISC')])

        Report = Model.get('aeat.303.report')
        report = Report()
        report.year = today.year
        report.type = 'I'
        report.regime_type = '3'
        report.period = '%02d' % today.month
        report.return_sepa_check = '0'
        report.exonerated_mod390 = '0' if report.period != '12' else '2'
        report.company_vat = '123456789'
        report.move_account = move_account
        report.move_journal = move_journal
        report.post_and_close = False
        report.click('calculate')

        self.assertEqual(report.aduana_tax_pending, Decimal('21.00'))

        report.click('process')
        counterpart, = [l for l in report.move.lines
            if l.account.id == move_account.id]
        self.assertEqual(counterpart.credit, Decimal('8.40'))
