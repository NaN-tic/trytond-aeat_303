# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import aeat
from . import account
from . import company
from . import configuration
from . import invoice
from . import statement


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationAEAT303,
        company.Company,
        aeat.Report,
        aeat.TemplateTaxCodeMapping,
        aeat.TemplateTaxCodeProrrataMapping,
        aeat.TemplateTaxCodeRelation,
        aeat.TemplateTaxCodePorrataRelation,
        aeat.TaxCodeMapping,
        aeat.TaxCodeProrrataMapping,
        aeat.TaxCodeRelation,
        aeat.TaxCodeProrrataRelation,
        account.Move,
        invoice.Invoice,
        invoice.InvoiceTax,
        module='aeat_303', type_='model')
    Pool.register(
        statement.Origin,
        module='aeat_303', type_='model',
        depends=['account_statement_enable_banking'])
    Pool.register(
        aeat.CreateChart,
        aeat.UpdateChart,
        module='aeat_303', type_='wizard')
