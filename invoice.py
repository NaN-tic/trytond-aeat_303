# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


def get_aduana_tax_pending_code_ids(company):
    pool = Pool()
    Mapping = pool.get('aeat.303.mapping')
    MappingTemplate = pool.get('aeat.303.template.mapping')
    TaxCode = pool.get('account.tax.code')

    code_ids = set()
    for mapping in Mapping.search([
                ('type_', '=', 'code'),
                ('company', '=', company.id),
                ('aeat303_field.name', '=', 'aduana_tax_pending'),
                ]):
        code_ids.update(code.id for code in mapping.code_by_companies)
    if code_ids:
        return code_ids

    for mapping in MappingTemplate.search([
                ('type_', '=', 'code'),
                ('aeat303_field.name', '=', 'aduana_tax_pending'),
                ]):
        template_ids = [code.id for code in mapping.code]
        if not template_ids:
            continue
        for code in TaxCode.search([
                    ('company', '=', company.id),
                    ('template', 'in', template_ids),
                    ]):
            code_ids.add(code.id)
    return code_ids


def is_aduana_tax_pending_tax(invoice_tax, code_ids):
    if not invoice_tax.tax:
        return False
    type_ = 'invoice' if (invoice_tax.base or 0) >= 0 else 'credit'
    for code_line in invoice_tax.tax.code_lines:
        if code_line.amount != 'tax' or code_line.type != type_:
            continue
        if code_line.code.id in code_ids:
            return True
    return False


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    def _compute_taxes(self):
        for key, value in super()._compute_taxes():
            value['deferred_dua_tax'] = bool(
                self.company and self.company.deferred_dua_tax)
            yield key, value

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        Warning = pool.get('res.user.warning')

        code_ids_by_company = {}
        to_save = []
        for invoice in invoices:
            if invoice.type != 'in' or not invoice.company.deferred_dua_tax:
                continue
            if invoice.lines or len(invoice.taxes) != 1:
                continue
            invoice_tax, = invoice.taxes
            if not invoice_tax.deferred_dua_tax:
                continue
            code_ids = code_ids_by_company.setdefault(
                invoice.company.id,
                get_aduana_tax_pending_code_ids(invoice.company))
            if not code_ids or not is_aduana_tax_pending_tax(
                    invoice_tax, code_ids):
                continue
            config = Configuration(1)
            account = config.get_multivalue(
                'aeat303_deferred_dua_account', company=invoice.company.id)
            if account and invoice.account != account:
                key = 'aeat303_deferred_dua_account_change_%s' % invoice.id
                if Warning.check(key):
                    raise UserWarning(key, gettext(
                            'aeat_303.msg_deferred_dua_account_change',
                            invoice=invoice.rec_name,
                            account=account.rec_name))
                invoice.account = account
                to_save.append(invoice)
        if to_save:
            cls.save(to_save)
        super()._post(invoices)


class InvoiceTax(metaclass=PoolMeta):
    __name__ = 'account.invoice.tax'

    deferred_dua_tax = fields.Boolean('Deferred DUA Tax', states={
            'readonly': Eval('invoice_state') != 'draft',
            })

    @fields.depends('invoice', '_parent_invoice.company')
    def on_change_invoice(self):
        company = self.invoice.company if self.invoice else None
        self.deferred_dua_tax = bool(company and company.deferred_dua_tax)

    @staticmethod
    def default_deferred_dua_tax():
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return bool(Company(company_id).deferred_dua_tax)
        return False
