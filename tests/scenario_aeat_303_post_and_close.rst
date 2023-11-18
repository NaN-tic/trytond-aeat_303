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
    ...     create_chart, get_accounts, create_tax
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
    ...         ('type.receivable', '=', True),
    ...         ('code', '=', '4300'),
    ...         ('company', '=', company.id),
    ...         ], limit=1)
    >>> payable, = Account.find([
    ...         ('type.payable', '=', True),
    ...         ('code', '=', '4100'),
    ...         ('company', '=', company.id),
    ...         ], limit=1)
    >>> revenue, = Account.find([
    ...         ('type.revenue', '=', True),
    ...         ('code', '=', '7000'),
    ...         ('company', '=', company.id),
    ...         ], limit=1)
    >>> expense, = Account.find([
    ...         ('type.expense', '=', True),
    ...         ('code', '=', '600'),
    ...         ('company', '=', company.id),
    ...         ], limit=1)
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

Create account category::

    >>> Tax = Model.get('account.tax')
    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> tax, = Tax.find([
    ...     ('group.kind', '=', 'sale'),
    ...     ('name', '=', 'IVA 21%'),
    ...     ('parent', '=', None),
    ...     ], limit = 1)
    >>> account_category.customer_taxes.append(tax)
    >>> tax, = Tax.find([
    ...     ('group.kind', '=', 'purchase'),
    ...     ('name', '=', 'IVA Deducible 21% (operaciones corrientes)'),
    ...     ('parent', '=', None),
    ...     ], limit = 1)
    >>> account_category.supplier_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
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

Get account and journal for the account move::

    >>> Journal = Model.get('account.journal')
    >>> move_account, = Account.find([
    ...         ('code', '=', '4750'),
    ...         ('type', '!=', None),
    ...         ('type.expense', '=', False),
    ...         ('type.revenue', '=', False),
    ...         ('type.debt', '=', False),
    ...         ('company', '=', company.id),
    ...         ], limit=1)
    >>> move_journal, = Journal.find([
    ...         ('code', '=', 'MISC'),
    ...         ])

Generate 303 Report and only create the move::

    >>> Report = Model.get('aeat.303.report')
    >>> report1 = Report()
    >>> report1.year = today.year
    >>> report1.type = 'I'
    >>> report1.regime_type = '3'
    >>> report1.period = "%02d" % (today.month)
    >>> report1.return_sepa_check = '0'
    >>> report1.exonerated_mod390 = '0' if report1.period != '12' else '2'
    >>> report1.company_vat = '123456789'
    >>> report1.move_account = move_account
    >>> report1.move_journal = move_journal
    >>> report1.post_and_close = False
    >>> report1.click('calculate')
    >>> report1.accrued_vat_base_3
    Decimal('240.00')
    >>> report1.accrued_vat_tax_3
    Decimal('50.40')

Test report is generated correctly::

    >>> report1.file_
    >>> report1.click('process')
    >>> bool(report1.file_)
    True
    >>> bool(report1.move)
    True
    >>> report1.move.state
    'draft'

Generate 303 Report and create the move, post it and close period::

    >>> report2 = Report()
    >>> report2.year = today.year
    >>> report2.type = 'I'
    >>> report2.regime_type = '3'
    >>> report2.period = "%02d" % (today.month)
    >>> report2.return_sepa_check = '0'
    >>> report2.exonerated_mod390 = '0' if report2.period != '12' else '2'
    >>> report2.company_vat = '123456789'
    >>> report2.move_account = move_account
    >>> report2.move_journal = move_journal
    >>> report2.post_and_close = True
    >>> report2.click('calculate')
    >>> report2.accrued_vat_base_3
    Decimal('240.00')
    >>> report2.accrued_vat_tax_3
    Decimal('50.40')

Post move genereated in the before report test to allow close the period::

    >>> Move = Model.get('account.move')
    >>> Move.post([report1.move], config.context)

Test report is generated correctly::

    >>> report2.file_
    >>> report2.click('process')
    >>> bool(report2.file_)
    True
    >>> bool(report2.move)
    True
    >>> report2.move.state
    'posted'
    >>> report2.move.period.state
    'closed'
