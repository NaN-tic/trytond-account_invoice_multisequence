import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.account_invoice.exceptions import InvoiceNumberError
from trytond.modules.company.tests.tools import create_company, get_company
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
        yestarday = today - datetime.timedelta(days=1)

        # Install account_invoice_multisequence
        activate_modules('account_invoice_multisequence')

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')
        fiscalyear.save()

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create new Journal with custom sequences
        Journal = Model.get('account.journal')
        AccountJournalInvoiceSequence = Model.get(
            'account.journal.invoice.sequence')
        SequenceStrict = Model.get('ir.sequence.strict')
        Sequence = Model.get('ir.sequence')
        SequenceType = Model.get('ir.sequence.type')
        sequence_type, = SequenceType.find([('name', '=', 'Invoice')])
        invoice_seq = SequenceStrict(name=fiscalyear.name,
                                     sequence_type=sequence_type,
                                     company=company)
        invoice_seq.save()
        sequence_type, = SequenceType.find([('name', '=', 'Invoice')])
        invoice_credit_seq = SequenceStrict(name=fiscalyear.name,
                                            sequence_type=sequence_type,
                                            prefix='C',
                                            company=company)
        invoice_credit_seq.save()
        journal_revenue, = Journal.find([('type', '=', 'revenue')])
        journal_revenue_custom = Journal(type='revenue', name='Custom Revenue')
        journal_revenue_custom.save()
        out_sequence = AccountJournalInvoiceSequence()
        out_sequence.journal = journal_revenue_custom
        out_sequence.fiscalyear = fiscalyear
        out_sequence.out_invoice_sequence = invoice_seq
        out_sequence.out_credit_note_sequence = invoice_credit_seq
        out_sequence.save()
        journal_expense, = Journal.find([('type', '=', 'expense')])
        journal_expense_custom = Journal(type='expense', name='Custom Expense')
        journal_expense_custom.save()
        in_sequence = AccountJournalInvoiceSequence()
        in_sequence.journal = journal_expense_custom
        in_sequence.fiscalyear = fiscalyear
        in_sequence.in_invoice_sequence = invoice_seq
        in_sequence.in_credit_note_sequence = invoice_credit_seq
        in_sequence.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
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

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create invoice on revenue journal
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = party
        invoice.journal = journal_revenue
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('40')
        invoice.click('post')
        self.assertEqual(invoice.number, '1')

        # Create credit_note on revenue journal
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = party
        invoice.journal = journal_revenue
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = -5
        line.unit_price = Decimal('40')
        invoice.click('post')
        self.assertEqual(invoice.number, '2')

        # Create invoice on custom journal
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = party
        invoice.invoice_date = today
        invoice.journal = journal_revenue_custom
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('40')
        invoice.click('post')
        self.assertEqual(invoice.number, '1')

        # not allow to post an invoice that invoice date is before to other invoice
        invoice = Invoice()
        invoice.party = party
        invoice.invoice_date = yestarday
        invoice.journal = journal_revenue_custom
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('40')
        with self.assertRaises(InvoiceNumberError):
            invoice.click('post')

        # Create credit_note on custom journal
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = party
        invoice.invoice_date = today
        invoice.journal = journal_revenue_custom
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = -5
        line.unit_price = Decimal('40')
        invoice.click('post')
        self.assertEqual(invoice.number, 'C1')

        # Create invoice IN on custom journal
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.type = 'in'
        invoice.party = party
        invoice.invoice_date = today
        invoice.journal = journal_expense_custom
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('40')
        invoice.click('post')
        self.assertEqual(invoice.number, '2')

        # Create credit_note IN on custom journal
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.type = 'in'
        invoice.party = party
        invoice.invoice_date = today
        invoice.journal = journal_expense_custom
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = -5
        line.unit_price = Decimal('40')
        invoice.click('post')
        self.assertEqual(invoice.number, 'C2')

        # Set the sequence number
        sequence = fiscalyear.move_sequence
        sequence.number_next = 10
        sequence.save()

        # Renew fiscalyear using the wizard
        FiscalYear = Model.get('account.fiscalyear')
        fiscal_years = len(FiscalYear.find([]))
        self.assertEqual(fiscal_years, 1)
        renew_fiscalyear = Wizard('account.fiscalyear.renew')
        renew_fiscalyear.form.reset_sequences = False
        renew_fiscalyear.execute('create_')
        new_fiscalyear, = renew_fiscalyear.actions[0]
        self.assertEqual(len(new_fiscalyear.periods), 12)
        self.assertEqual(int(new_fiscalyear.move_sequence.number_next), 10)
        fiscal_years = len(FiscalYear.find([]))
        self.assertEqual(fiscal_years, 2)
        new_fiscal_year = FiscalYear.find(["id", "!=", fiscalyear.id])[0]
        separate = (new_fiscal_year.journal_sequences[0].id
                    != fiscalyear.journal_sequences[0].id)
        self.assertEqual(separate, True)
