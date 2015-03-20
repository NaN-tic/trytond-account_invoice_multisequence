# This file is part of the account_invoice_multisequence module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, In, Not
from trytond.transaction import Transaction


__all__ = ['AccountJournalInvoiceSequence', 'Journal', 'FiscalYear', 'Invoice']
__metaclass__ = PoolMeta


class AccountJournalInvoiceSequence(ModelSQL, ModelView):
    'Account Journal Invoice Sequence'
    __name__ = 'account.journal.invoice.sequence'
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscalyear',
        required=True)
    period = fields.Many2One('account.period', 'Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear'))
            ], depends=['fiscalyear'])
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True)
    type = fields.Function(fields.Char('Type'), 'get_type')
    out_invoice_sequence = fields.Many2One('ir.sequence.strict',
        'Customer Invoice Sequence',
        states={
            'required': Eval('type') == 'revenue',
            'invisible': Eval('type') != 'revenue',
            },
        domain=[
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
            ['OR',
                ('company', '=', Eval('company')),
                ('company', '=', None),
                ]
            ],
        depends=['company', 'type'])

    @classmethod
    def __setup__(cls):
        super(AccountJournalInvoiceSequence, cls).__setup__()
        cls._sql_constraints += [
            ('period_uniq', 'UNIQUE(journal, period)',
                'Period can be used only once per Journal Sequence.'),
        ]

    def get_type(self, name):
        return self.journal.type

    @fields.depends('journal')
    def on_change_journal(self):
        return {
            'type': self.journal.type,
            }


class Journal:
    __name__ = 'account.journal'
    sequences = fields.One2Many('account.journal.invoice.sequence', 'journal',
        'Sequences', states={
            'invisible': Not(In(Eval('type'), ['revenue', 'expense'])),
            })

    def get_invoice_sequence(self, invoice):
        pool = Pool()
        Date = pool.get('ir.date')
        date = invoice.invoice_date or Date.today()
        for sequence in self.sequences:
            period = sequence.period
            if period and (period.start_date <= date and
                    period.end_date >= date):
                return getattr(sequence, invoice.type + '_sequence')
        for sequence in self.sequences:
            fiscalyear = sequence.fiscalyear
            if (fiscalyear.start_date <= date and
                    fiscalyear.end_date >= date):
                return getattr(sequence, invoice.type + '_sequence')


class FiscalYear:
    __name__ = 'account.fiscalyear'
    journal_sequences = fields.Function(fields.One2Many('ir.sequence.strict',
            None, 'Journal Sequences'), 'get_journal_sequences')

    def get_journal_sequences(self, name):
        pool = Pool()
        InvoiceSequences = pool.get('account.journal.invoice.sequence')
        sequences = InvoiceSequences.search([('fiscalyear', '=', self.id)])
        result = [s.out_invoice_sequence.id for s in sequences]
        result.extend([s.out_credit_note_sequence.id for s in sequences])
        return result


class Invoice:
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
                self.number = Sequence.get_id(sequence.id)
                self.save()

        return super(Invoice, self).set_number()
