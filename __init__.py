# This file is part of the account_invoice_multisequence module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import account

def register():
    Pool.register(
        account.AccountJournalInvoiceSequence,
        account.Journal,
        account.FiscalYear,
        account.Invoice,
        module='account_invoice_multisequence', type_='model')
    Pool.register(
        account.RenewFiscalYear,
        module="account_invoice_multisequence", type_='wizard')

