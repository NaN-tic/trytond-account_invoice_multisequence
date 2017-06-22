==============================
Invoice MultiSequence Scenario
==============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install sale::

    >>> Module = Model.get('ir.module')
    >>> account_invoice_multisequence_module, = Module.find(
    ...     [('name', '=', 'account_invoice_multisequence')])
    >>> account_invoice_multisequence_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create tax::

    >>> tax = set_tax_code(create_tax(Decimal('.10')))
    >>> tax.save()
    >>> invoice_base_code = tax.invoice_base_code
    >>> invoice_tax_code = tax.invoice_tax_code
    >>> credit_note_base_code = tax.credit_note_base_code
    >>> credit_note_tax_code = tax.credit_note_tax_code

Create new Journal with custom sequences::

    >>> Journal = Model.get('account.journal')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> Sequence = Model.get('ir.sequence')
    >>> sequence_journal, = Sequence.find([('code', '=', 'account.journal')])
    >>> invoice_seq = SequenceStrict(name=fiscalyear.name,
    ...     code='account.invoice',
    ...     company=company)
    >>> invoice_seq.save()
    >>> invoice_credit_seq = SequenceStrict(name=fiscalyear.name,
    ...     code='account.invoice',
    ...     prefix='C',
    ...     company=company)
    >>> invoice_credit_seq.save()
    >>> journal_revenue, = Journal.find([('type', '=', 'revenue')])
    >>> journal_revenue_custom = Journal(type='revenue',
    ...     name='Custom Revenue',
    ...     sequence=sequence_journal)
    >>> sequences = journal_revenue_custom.sequences.new()
    >>> sequences.fiscalyear = fiscalyear
    >>> sequences.out_invoice_sequence = invoice_seq
    >>> sequences.out_credit_note_sequence = invoice_credit_seq
    >>> journal_revenue_custom.save()

    >>> journal_expense, = Journal.find([('type', '=', 'expense')])
    >>> journal_expense_custom = Journal(type='expense',
    ...     name='Custom Expense',
    ...     sequence=sequence_journal)
    >>> sequences = journal_expense_custom.sequences.new()
    >>> sequences.fiscalyear = fiscalyear
    >>> sequences.in_invoice_sequence = invoice_seq
    >>> sequences.in_credit_note_sequence = invoice_credit_seq
    >>> journal_expense_custom.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('25')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create invoice on revenue journal::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.journal = journal_revenue
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.number
    u'1'

Create credit_note on revenue journal::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.journal = journal_revenue
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = -5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.number
    u'2'

Create invoice on custom journal::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> invoice.journal = journal_revenue_custom
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.number
    u'1'

Create credit_note on custom journal::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> invoice.journal = journal_revenue_custom
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = -5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.number
    u'C1'

Create invoice IN on custom journal::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> invoice.journal = journal_expense_custom
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.number
    u'2'

Create credit_note IN on custom journal::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> invoice.journal = journal_expense_custom
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = -5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.number
    u'C2'
