# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import aeat
from . import account
from . import configuration


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationAEAT303,
        aeat.Report,
        aeat.TemplateTaxCodeMapping,
        aeat.TemplateTaxCodeRelation,
        aeat.TaxCodeMapping,
        aeat.TaxCodeRelation,
        account.Move,
        module='aeat_303', type_='model')
    Pool.register(
        aeat.CreateChart,
        aeat.UpdateChart,
        module='aeat_303', type_='wizard')
