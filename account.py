# This file is part of the account_invoice_multisequence module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from collections import OrderedDict
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, In, Not, Id
from trytond.transaction import Transaction

_ZERO = Decimal(0)


class AccountJournalInvoiceSequence(ModelSQL, ModelView):
    'Account Journal Invoice Sequence'
    __name__ = 'account.journal.invoice.sequence'
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscalyear',
        required=True, domain=[
            ('company', '=', Eval('company', -1)),
            ])
    period = fields.Many2One('account.period', 'Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear'))
            ])
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    type = fields.Function(fields.Char('Type'), 'on_change_with_type')
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence',
        states={'required': Eval('type') == 'revenue',
                'invisible': Eval('type') != 'revenue',
                },
        domain=[
            ('sequence_type', '=', Id('account_invoice',
                    'sequence_type_account_invoice')),
            ['OR',
                ('company', '=', Eval('company', -1)),
                ('company', '=', None),
                ]
            ])
    out_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Credit Note Sequence',
        domain=[
            ('sequence_type', '=', Id('account_invoice',
                    'sequence_type_account_invoice')),
            ['OR',
                ('company', '=', Eval('company', -1)),
                ('company', '=', None),
                ]
            ])
    in_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Invoice Sequence',
        domain=[
            ('sequence_type', '=', Id('account_invoice',
                    'sequence_type_account_invoice')),
            ['OR',
                ('company', '=', Eval('company', -1)),
                ('company', '=', None),
                ]
            ])
    in_credit_note_sequence = fields.Many2One('ir.sequence.strict',
        'Supplier Credit Note Sequence',
        domain=[
            ('sequence_type', '=', Id('account_invoice',
                    'sequence_type_account_invoice')),
            ['OR',
                ('company', '=', Eval('company', -1)),
                ('company', '=', None),
                ]
            ])

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


class Journal(metaclass=PoolMeta):
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


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'
    journal_sequences = fields.One2Many('account.journal.invoice.sequence',
        'fiscalyear', 'Journal Sequences')


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    def _number_sequence(self, pattern=None):
        pool = Pool()
        Date = pool.get('ir.date')

        sequence = self.journal and self.journal.get_invoice_sequence(self)
        accounting_date = self.accounting_date or self.invoice_date or Date.today()
        if sequence:
            with Transaction().set_context(
                    date=accounting_date,
                    company=self.company.id):
                return sequence, accounting_date
        return super()._number_sequence(pattern)


class RenewFiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear.renew'

    def fiscalyear_defaults(self):
        defaults = super(RenewFiscalYear, self).fiscalyear_defaults()
        defaults['invoice_sequences'] = None
        return defaults

    @property
    def invoice_sequence_fields(self):
        return ['out_invoice_sequence', 'out_credit_note_sequence',
            'in_invoice_sequence', 'in_credit_note_sequence']

    def create_fiscalyear(self):
        pool = Pool()
        Sequence = pool.get('ir.sequence.strict')
        InvoiceSequence = pool.get('account.journal.invoice.sequence')

        fiscalyear = super().create_fiscalyear()

        if not self.start.reset_sequences:
            return fiscalyear

        sequences = OrderedDict()
        for invoice_sequence in fiscalyear.journal_sequences:
            for field in self.invoice_sequence_fields:
                sequence = getattr(invoice_sequence, field, None)
                if sequence:
                    sequences[sequence.id] = sequence
        copies = Sequence.copy(list(sequences.values()), default={
                'name': lambda data: data['name'].replace(
                    self.start.previous_fiscalyear.name,
                    self.start.name)
                })
        Sequence.write(copies, {
                'number_next': Sequence.default_number_next(),
                })
        mapping = {}
        for previous_id, new_sequence in zip(sequences.keys(), copies):
            mapping[previous_id] = new_sequence.id
        to_write = []
        for new_sequence, old_sequence in zip(
                fiscalyear.journal_sequences,
                self.start.previous_fiscalyear.journal_sequences):
            values = {}
            for field in self.invoice_sequence_fields:
                sequence = getattr(old_sequence, field, None)
                if not sequence:
                    continue
                values[field] = mapping[sequence.id]
            to_write.extend(([new_sequence], values))
        if to_write:
            InvoiceSequence.write(*to_write)
        return fiscalyear
