# This file is part of the account_invoice_multisequence module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, In, Not
from trytond.transaction import Transaction


__all__ = ['AccountJournalInvoiceSequence', 'Journal', 'FiscalYear', 'Invoice']
_ZERO = Decimal('0.0')


class AccountJournalInvoiceSequence(ModelSQL, ModelView):
    'Account Journal Invoice Sequence'
    __name__ = 'account.journal.invoice.sequence'
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscalyear',
        required=True, domain=[
            ('company', '=', Eval('company', -1)),
            ], depends=['company'])
    period = fields.Many2One('account.period', 'Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear'))
            ], depends=['fiscalyear'])
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True)
    type = fields.Function(fields.Char('Type'), 'on_change_with_type')
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence',
        states={
            'required': Eval('type') == 'revenue',
            'invisible': Eval('type') != 'revenue',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Credit Note Sequence',
        states={
            'required': Eval('type') == 'revenue',
            'invisible': Eval('type') != 'revenue',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence',
        states={
            'required': Eval('type') == 'expense',
            'invisible': Eval('type') != 'expense',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence',
        states={
            'required': Eval('type') == 'expense',
            'invisible': Eval('type') != 'expense',
            },
        domain=[
            ('code', '=', 'account.invoice'),
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])

    @classmethod
    def __setup__(cls):
        super(AccountJournalInvoiceSequence, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('period_uniq', Unique(t, t.journal, t.period),
                'Period can be used only once per Journal Sequence.'),
        ]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('journal')
    def on_change_with_type(self, name=None):
        if self.journal:
            return self.journal.type


class Journal:
    __metaclass__ = PoolMeta
    __name__ = 'account.journal'

    def get_invoice_sequence(self, invoice):
        pool = Pool()
        Date = pool.get('ir.date')
        JournalSequence = pool.get('account.journal.invoice.sequence')
        date = invoice.invoice_date or Date.today()
        company_id = Transaction().context.get('company')

        sequences = JournalSequence.search([
                ('journal', '=', self.id),
                ('company', '=', company_id),
                ])
        for sequence in sequences:
            period = sequence.period
            if period and (period.start_date <= date and
                    period.end_date >= date):
                if invoice.untaxed_amount >= _ZERO:
                    return getattr(
                        sequence, invoice.type + '_invoice_sequence')
                else:
                    return getattr(
                        sequence, invoice.type + '_credit_note_sequence')
        for sequence in sequences:
            fiscalyear = sequence.fiscalyear
            if (fiscalyear.start_date <= date and
                    fiscalyear.end_date >= date):
                if invoice.untaxed_amount >= _ZERO:
                    return getattr(
                        sequence, invoice.type + '_invoice_sequence')
                else:
                    return getattr(
                        sequence, invoice.type + '_credit_note_sequence')

    @classmethod
    def view_attributes(cls):
        return super(Journal, cls).view_attributes() + [
            ('//page[@id="sequences"]', 'states', {
                    'invisible': Not(In(Eval('type'), ['revenue', 'expense'])),
                    })]


class FiscalYear:
    __metaclass__ = PoolMeta
    __name__ = 'account.fiscalyear'
    journal_sequences = fields.One2Many('account.journal.invoice.sequence',
        'fiscalyear', 'Journal Sequences')


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    def set_number(self):
        '''
        Set number to the invoice
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence.strict')
        Date = pool.get('ir.date')

        if self.number:
            return

        sequence = self.journal.get_invoice_sequence(self)
        if sequence:
            with Transaction().set_context(
                    date=self.invoice_date or Date.today()):
                number = Sequence.get_id(sequence.id)
                self.number = number
                if not self.invoice_date and self.type == 'out':
                    self.invoice_date = Transaction().context['date']
                self.save()

        return super(Invoice, self).set_number()
