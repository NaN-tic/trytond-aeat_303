================
Invoice Scenario
================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install aeat_303::

    >>> config = activate_modules(['aeat_303', 'account_es', 'account_invoice'])

Create company::

    >>> eur = get_currency('EUR')
    >>> _ = create_company(currency=eur)
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', None),
    ...     ('name', 'ilike', 'Plan General Contable%')])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('code', '=', '4300'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('code', '=', '4100'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('code', '=', '7000'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('code', '=', '600'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> identifier = party.identifiers.new()
    >>> identifier.type='eu_vat'
    >>> identifier.code='ES00000000T'
    >>> party.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> Tax = Model.get('account.tax')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> tax, = Tax.find([
    ...     ('group.kind', '=', 'sale'),
    ...     ('name', '=', 'IVA 21%'),
    ...     ('parent', '=', None),
    ...     ], limit = 1)
    >>> template.customer_taxes.append(tax)
    >>> tax, = Tax.find([
    ...     ('group.kind', '=', 'purchase'),
    ...     ('name', '=', '21% IVA Soportado (operaciones corrientes)'),
    ...     ('parent', '=', None),
    ...     ], limit = 1)
    >>> template.supplier_taxes.append(tax)
    >>> product, = template.products
    >>> product.cost_price = Decimal('25')
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create out invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.unit_price = Decimal('40.0')
    >>> line.quantity = 5
    >>> len(line.taxes)
    1
    >>> line.amount
    Decimal('200.00')
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> line.amount
    Decimal('20.00')
    >>> line = invoice.lines.new()
    >>> len(line.taxes) == 0
    True
    >>> line.account = revenue
    >>> line.description = 'Test 2'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(40)
    >>> tax, = Tax.find([
    ...     ('group.kind', '=', 'sale'),
    ...     ('name', '=', 'IVA 21%'),
    ...     ('parent', '=', None),
    ...     ], limit = 1)
    >>> line.taxes.append(tax)
    >>> line.amount
    Decimal('40.00')
    >>> invoice.click('post')

Generate 303 Report::

    >>> Report = Model.get('aeat.303.report')
    >>> report = Report()
    >>> report.fiscalyear_code = 2013
    >>> report.type = 'I'
    >>> report.regime_type = '3'
    >>> report.period = "%02d" % (today.month)
    >>> report.company_vat = '123456789'
    >>> report.contact_name = 'Guido van Rosum'
    >>> report.contact_phone = '987654321'
    >>> report.representative_vat = '22334455'
    >>> report.click('calculate')
    >>> report.accrued_vat_base_3
    Decimal('240.00')
    >>> report.accrued_vat_tax_3
    Decimal('50.40')

Test report is generated correctly::

    >>> report.file_
    >>> report.click('process')
    >>> bool(report.file_)
    True
