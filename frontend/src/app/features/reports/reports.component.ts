import { HttpClient, HttpParams } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { apiErrorMessage } from '../../core/auth.models';
import { AuthService } from '../../core/auth.service';
import { Row, formatValue } from '../workspace/workspace-config';

interface ReportColumn {
  key: string;
  label: string;
  kind?: 'money' | 'number';
}

interface ReportSection {
  title: string;
  columns: ReportColumn[];
  rows: Row[];
  note?: string;
}

interface Metric {
  label: string;
  value: string;
  note: string;
  link?: string;
  tone?: 'actual' | 'operational' | 'muted';
}

interface Bar {
  label: string;
  value: number;
  display: string;
  percent: number;
}

type BarInput = Omit<Bar, 'percent'>;

type ReportTab =
  | 'overview'
  | 'financial'
  | 'ledger'
  | 'receivable'
  | 'payable'
  | 'procurement'
  | 'inventory'
  | 'projects'
  | 'operations'
  | 'banking'
  | 'tax';

interface TabDefinition {
  id: ReportTab;
  label: string;
  description: string;
}

const TABS: TabDefinition[] = [
  {
    id: 'overview',
    label: 'Executive',
    description: 'Posted results, cash, commitments and operational activity in one view.',
  },
  {
    id: 'financial',
    label: 'Financial statements',
    description: 'Profit or loss, balance sheet, cash flow and period close status.',
  },
  {
    id: 'ledger',
    label: 'Ledger',
    description: 'Trial balance, general ledger and the complete journal register.',
  },
  {
    id: 'receivable',
    label: 'Receivables',
    description: 'Approved customer invoice balances by ageing bucket.',
  },
  {
    id: 'payable',
    label: 'Payables',
    description: 'Approved supplier invoice balances by ageing bucket.',
  },
  {
    id: 'procurement',
    label: 'Procurement',
    description: 'Orders, commitments, supplier activity and outstanding deliveries.',
  },
  {
    id: 'inventory',
    label: 'Inventory',
    description: 'Stock balances, valuation, movements and low-stock alerts.',
  },
  {
    id: 'projects',
    label: 'Projects',
    description: 'Budget, actual cost, commitments and estimated margin by project.',
  },
  {
    id: 'operations',
    label: 'Services & equipment',
    description: 'Work orders, maintenance, utilisation, rentals and overdue returns.',
  },
  {
    id: 'banking',
    label: 'Banking',
    description: 'Bank accounts, statements, reconciliations and cash accounts.',
  },
  {
    id: 'tax',
    label: 'Tax',
    description: 'Tax configuration and approved invoice tax totals, separated from remittance.',
  },
];

const MONEY_KEYS = new Set([
  'amount',
  'balance',
  'value',
  'total',
  'subtotal',
  'revenue',
  'expenses',
  'gross_profit',
  'net_result',
  'actual_cost',
  'actual_total',
  'budget_total',
  'open_commitment',
  'open_commitments',
  'committed_value',
  'contract_value',
  'estimated_cost_to_complete',
  'estimated_margin',
  'available_budget',
  'invoice_value',
  'order_value',
  'approved_invoice_value',
  'recorded_movement',
  'opening_balance',
  'imprest_amount',
  'debit',
  'credit',
  'overdue',
  'cost',
  'vat',
  'wht',
  'recoverable',
  'rental_value',
  'closing_cash',
  'opening_cash',
  'net_change',
  'statement_closing_balance',
]);

/**
 * Reporting workspace. Every total and row is calculated by Django; this
 * component only formats the returned records and keeps the filters.
 */
@Component({
  selector: 'app-reports',
  imports: [
    FormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    RouterLink,
  ],
  templateUrl: './reports.component.html',
  styleUrl: './reports.component.scss',
})
export class ReportsComponent implements OnInit {
  private readonly http = inject(HttpClient);
  protected readonly auth = inject(AuthService);

  protected readonly tabs = TABS;
  protected readonly visibleTabs = computed(() => {
    const permissions = this.auth.user()?.permissions ?? [];
    if (!permissions.includes('reporting.view_reporting')) {
      return [];
    }
    return TABS.filter(
      (item) =>
        !['overview', 'financial', 'ledger', 'tax'].includes(item.id) ||
        permissions.includes('reporting.view_financialreporting'),
    );
  });
  protected readonly tab = signal<ReportTab>('overview');
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly warnings = signal<string[]>([]);
  protected readonly metrics = signal<Metric[]>([]);
  protected readonly sections = signal<ReportSection[]>([]);
  protected readonly bars = signal<Bar[]>([]);
  protected readonly barDetail = signal<string | null>(null);
  protected readonly asOfLabel = signal('');

  protected readonly accounts = signal<Row[]>([]);

  protected accountId: number | null = null;
  protected start = this.monthStart();
  protected end = this.today();
  protected glStart = '';
  protected glEnd = '';

  ngOnInit(): void {
    this.loadOptions('/api/v1/accounts/?page_size=100', this.accounts);
    const available = this.visibleTabs();
    if (!available.some((item) => item.id === this.tab())) {
      this.tab.set(available[0]?.id ?? 'procurement');
    }
    if (!available.length) {
      return;
    }
    this.run();
  }

  protected canExport(): boolean {
    return (this.auth.user()?.permissions ?? []).includes('reporting.export_reporting');
  }

  protected currentTab(): TabDefinition {
    return TABS.find((item) => item.id === this.tab()) ?? TABS[0];
  }

  protected selectTab(tab: ReportTab): void {
    this.tab.set(tab);
    this.error.set(null);
    this.sections.set([]);
    this.metrics.set([]);
    this.bars.set([]);
    this.barDetail.set(null);
    this.run();
  }

  protected run(): void {
    this.error.set(null);
    this.sections.set([]);
    this.metrics.set([]);
    this.bars.set([]);
    this.warnings.set([]);
    this.barDetail.set(null);
    this.asOfLabel.set(`${this.start || 'beginning'} to ${this.end || 'today'}`);
    if (!this.start || !this.end) {
      this.error.set('Choose a start and end date.');
      return;
    }
    if (this.end < this.start) {
      this.error.set('The end date cannot precede the start date.');
      return;
    }
    switch (this.tab()) {
      case 'overview':
        this.loadOverview();
        break;
      case 'financial':
        this.loadFinancial();
        break;
      case 'ledger':
        this.loadLedger();
        break;
      case 'receivable':
        this.loadReceivables();
        break;
      case 'payable':
        this.loadPayables();
        break;
      case 'procurement':
        this.loadProcurement();
        break;
      case 'inventory':
        this.loadInventory();
        break;
      case 'projects':
        this.loadProjects();
        break;
      case 'operations':
        this.loadOperations();
        break;
      case 'banking':
        this.loadBanking();
        break;
      case 'tax':
        this.loadTax();
        break;
    }
  }

  protected exportReport(output: 'csv' | 'pdf'): void {
    let params = this.reportParams();
    params = params.set('output', output);
    if (this.tab() === 'ledger' && this.accountId) {
      params = params.set('account', String(this.accountId));
    }
    const name = this.exportName();
    window.open(`/api/v1/reporting/${name}/export/?${params.toString()}`, '_blank');
  }

  protected print(): void {
    window.print();
  }

  protected selectBar(bar: Bar): void {
    this.barDetail.set(`${bar.label}: ${bar.display} (${this.asOfLabel()})`);
  }

  protected cell(row: Row, column: ReportColumn): string {
    const key = column.key;
    const value = row[key];
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    if (column.kind === 'number') {
      return this.number(value);
    }
    if (column.kind === 'money') {
      return this.money(value);
    }
    if (key === 'value' && row['kind']) {
      return row['kind'] === 'money' ? this.money(value) : this.number(value);
    }
    if (MONEY_KEYS.has(key) && !Number.isNaN(Number(value)) && String(value).trim() !== '') {
      return this.money(value);
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (key === 'status' || key === 'activity' || key === 'bucket' || key === 'type') {
      return formatValue(value, 'status');
    }
    if (key.endsWith('_date') || key === 'date' || key === 'received_on' || key === 'completed_on') {
      return String(value).slice(0, 10);
    }
    if (typeof value === 'number') {
      return this.number(value);
    }
    return String(value);
  }

  protected visibleRows(rows: Row[]): Row[] {
    return rows.slice(0, 250);
  }

  private loadOverview(): void {
    this.get('/api/v1/reporting/overview/', this.reportParams(), (body) => {
      const actual = this.obj(body['actual']);
      const cash = this.obj(body['cash']);
      const receivable = this.obj(body['receivables']);
      const payable = this.obj(body['payables']);
      const inventory = this.obj(body['inventory']);
      const projects = this.obj(body['projects']);
      const procurement = this.obj(body['procurement']);
      const operations = this.obj(body['operations']);
      this.metrics.set([
        {
          label: 'Revenue (posted)',
          value: this.money(actual['revenue']),
          note: 'Posted ledger income for the period',
          tone: 'actual',
          link: '/accounting',
        },
        {
          label: 'Expenses (posted)',
          value: this.money(actual['expenses']),
          note: 'Posted ledger expenditure for the period',
          tone: 'actual',
          link: '/accounting',
        },
        {
          label: 'Net result (posted)',
          value: this.money(actual['net_result']),
          note: 'Income less expenses from posted journals',
          tone: 'actual',
        },
        {
          label: 'Cash and bank',
          value: cash['available'] ? this.money(cash['gl_closing_cash']) : 'Unavailable',
          note: cash['available']
            ? 'Closing GL cash from linked bank accounts'
            : String(cash['reason'] ?? 'No bank GL mapping'),
          tone: cash['available'] ? 'actual' : 'muted',
          link: '/banking',
        },
        {
          label: 'Receivables',
          value: receivable['mixed_currency'] ? 'Multiple currencies' : this.money(receivable['total']),
          note: receivable['mixed_currency']
            ? 'Approved customer invoice balances; no exchange rate is assumed'
            : 'Approved customer invoice balances',
          tone: 'operational',
          link: '/invoicing',
        },
        {
          label: 'Payables',
          value: payable['mixed_currency'] ? 'Multiple currencies' : this.money(payable['total']),
          note: payable['mixed_currency']
            ? 'Approved supplier invoice balances; no exchange rate is assumed'
            : 'Approved supplier invoice balances',
          tone: 'operational',
          link: '/invoicing',
        },
        {
          label: 'Inventory value',
          value: inventory['available'] ? this.money(inventory['value']) : 'Unavailable',
          note: inventory['available']
            ? `Method: ${String(inventory['method'])}`
            : String(inventory['reason'] ?? 'No valuation method'),
          tone: inventory['available'] ? 'operational' : 'muted',
          link: '/inventory',
        },
        {
          label: 'Active projects',
          value: this.number(projects['active']),
          note: `${this.money(projects['open_commitments'])} open commitments`,
          tone: 'operational',
          link: '/projects',
        },
      ]);
      this.warnings.set(this.strings(body['warnings']));
      this.sections.set([
        {
          title: 'What each figure means',
          columns: [
            { key: 'measure', label: 'Measure' },
            { key: 'basis', label: 'Basis' },
          ],
          rows: Object.entries(this.obj(body['definitions'])).map(([measure, basis]) => ({
            measure: formatValue(measure, 'status'),
            basis,
          })),
        },
        {
          title: 'Operational position',
          columns: [
            { key: 'measure', label: 'Measure' },
            { key: 'value', label: 'Value' },
            { key: 'note', label: 'Basis' },
          ],
          rows: [
            {
              measure: 'Procurement commitments',
              value: procurement['committed_value'],
              kind: 'money',
              note: `${String(procurement['orders'] ?? 0)} orders; not an expense`,
            },
            {
              measure: 'Outstanding deliveries',
              value: procurement['outstanding_deliveries'],
              kind: 'count',
              note: 'Delivery schedules with quantity still due',
            },
            {
              measure: 'Open work orders',
              value: operations['open_work_orders'],
              kind: 'count',
              note: 'Excludes completed, accepted and cancelled',
            },
            {
              measure: 'Overdue equipment returns',
              value: operations['overdue_returns'],
              kind: 'count',
              note: 'Latest movement is still a dispatch',
            },
            {
              measure: 'Project actual cost',
              value: projects['actual_cost'],
              kind: 'money',
              note: 'Approved invoices, project issues and direct costs',
            },
            {
              measure: 'Project budget',
              value: projects['total_budget'],
              kind: 'money',
              note: 'Latest approved budget per project',
            },
          ],
        },
      ]);
      this.bars.set(
        this.makeBars([
          { label: 'Revenue', value: Number(actual['revenue'] ?? 0), display: this.money(actual['revenue']) },
          { label: 'Expenses', value: Number(actual['expenses'] ?? 0), display: this.money(actual['expenses']) },
          {
            label: 'Receivables',
            value: Number(receivable['total'] ?? 0),
            display: this.money(receivable['total']),
          },
          {
            label: 'Payables',
            value: Number(payable['total'] ?? 0),
            display: this.money(payable['total']),
          },
        ]),
      );
    });
  }

  private loadFinancial(): void {
    const params = this.reportParams();
    this.loading.set(true);
    forkJoin({
      statements: this.http
        .get<Row>('/api/v1/reporting/financial-statements/', { params })
        .pipe(catchError(() => of(null))),
      trial: this.http
        .get<Row>('/api/v1/reporting/trial-balance/', { params })
        .pipe(catchError(() => of(null))),
      periods: this.http
        .get<Row>('/api/v1/reporting/periods/', { params })
        .pipe(catchError(() => of(null))),
    }).subscribe({
      next: ({ statements, trial, periods }) => {
        this.loading.set(false);
        if (!statements) {
          this.error.set('The financial statements could not be loaded.');
          return;
        }
        const income = this.obj(statements['income_statement']);
        const balance = this.obj(statements['balance_sheet']);
        const cash = this.obj(statements['cash_flow']);
        this.metrics.set([
          {
            label: 'Total income',
            value: this.money(income['total_income']),
            note: 'Posted ledger accounts for the period',
            tone: 'actual',
          },
          {
            label: 'Total expenses',
            value: this.money(income['total_expenses']),
            note: 'Posted ledger accounts for the period',
            tone: 'actual',
          },
          {
            label: 'Net result',
            value: this.money(income['net_result']),
            note: 'Income less expenses; period-close journals excluded',
            tone: 'actual',
          },
          {
            label: 'Total assets',
            value: this.money(balance['total_assets']),
            note: `As at ${String(balance['as_of'] ?? this.end)}`,
            tone: 'actual',
          },
          {
            label: 'Liabilities + equity',
            value: this.money(balance['total_equity_and_liabilities']),
            note: balance['balanced'] === true ? 'Balance sheet balances' : 'Does not balance',
            tone: balance['balanced'] === true ? 'actual' : 'operational',
          },
          {
            label: 'Closing cash',
            value: cash['available'] ? this.money(cash['closing_cash']) : 'Unavailable',
            note: cash['available']
              ? cash['complete'] === false
                ? 'Incomplete: an account-role mapping is missing'
                : 'From linked bank GL accounts'
              : String(cash['reason'] ?? ''),
            tone: cash['available'] && cash['complete'] !== false ? 'actual' : 'muted',
          },
        ]);
        this.warnings.set(this.strings(statements['warnings']));
        this.sections.set([
          {
            title: 'Profit or loss — income',
            columns: [
              { key: 'code', label: 'Code' },
              { key: 'name', label: 'Account' },
              { key: 'amount', label: 'Amount (NGN)' },
            ],
            rows: this.rows(income['income']),
          },
          {
            title: 'Profit or loss — expenses',
            columns: [
              { key: 'code', label: 'Code' },
              { key: 'name', label: 'Account' },
              { key: 'amount', label: 'Amount (NGN)' },
            ],
            rows: this.rows(income['expenses']),
          },
          {
            title: 'Balance sheet',
            columns: [
              { key: 'group', label: 'Group' },
              { key: 'code', label: 'Code' },
              { key: 'name', label: 'Account' },
              { key: 'amount', label: 'Amount (NGN)' },
            ],
            rows: [
              ...this.group('Asset', balance['assets']),
              ...this.group('Liability', balance['liabilities']),
              ...this.group('Equity', balance['equity']),
            ],
            note: `Unclosed result: ${this.money(balance['unclosed_result'])}. ${
              balance['balanced'] === true ? 'Assets equal liabilities plus equity.' : 'The balance sheet does not balance.'
            }`,
          },
          {
            title: 'Cash flow by activity',
            columns: [
              { key: 'activity', label: 'Activity' },
              { key: 'amount', label: 'Net cash (NGN)' },
            ],
            rows: this.rows(cash['by_activity']),
            note: cash['available']
              ? `Opening ${this.money(cash['opening_cash'])}; closing ${this.money(cash['closing_cash'])}. ${
                  cash['complete'] === false ? 'Incomplete: unclassified accounts are shown above. ' : ''
                }${String(cash['method'] ?? '')}`
              : String(cash['reason'] ?? 'No linked bank GL accounts.'),
          },
          {
            title: 'Cash flow detail',
            columns: [
              { key: 'journal_date', label: 'Date' },
              { key: 'journal_number', label: 'Journal' },
              { key: 'description', label: 'Description' },
              { key: 'counterpart_account', label: 'Counterpart' },
              { key: 'activity', label: 'Activity' },
              { key: 'amount', label: 'Cash flow (NGN)' },
            ],
            rows: this.rows(cash['rows']),
          },
          {
            title: 'Trial balance',
            columns: [
              { key: 'code', label: 'Code' },
              { key: 'name', label: 'Account' },
              { key: 'account_type', label: 'Type' },
              { key: 'debit', label: 'Debit' },
              { key: 'credit', label: 'Credit' },
              { key: 'balance', label: 'Balance' },
            ],
            rows: this.rows(trial?.['rows']),
            note: trial
              ? `Debits ${this.money(trial['total_debit'])}; credits ${this.money(trial['total_credit'])}; ${
                  trial['balanced'] === true ? 'balanced' : 'not balanced'
                }.`
              : 'Trial balance unavailable.',
          },
          {
            title: 'Financial periods',
            columns: [
              { key: 'fiscal_year', label: 'Year' },
              { key: 'name', label: 'Period' },
              { key: 'start_date', label: 'Start' },
              { key: 'end_date', label: 'End' },
              { key: 'status', label: 'Status' },
              { key: 'posted_journals', label: 'Posted' },
              { key: 'unposted_journals', label: 'Unposted' },
              { key: 'debit', label: 'Debit' },
              { key: 'credit', label: 'Credit' },
              { key: 'balanced', label: 'Balanced' },
            ],
            rows: this.rows(periods?.['rows']),
          },
        ]);
        this.bars.set(
          this.makeBars([
            { label: 'Income', value: Number(income['total_income'] ?? 0), display: this.money(income['total_income']) },
            {
              label: 'Expenses',
              value: Number(income['total_expenses'] ?? 0),
              display: this.money(income['total_expenses']),
            },
            {
              label: 'Net result',
              value: Math.abs(Number(income['net_result'] ?? 0)),
              display: this.money(income['net_result']),
            },
          ]),
        );
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error));
      },
    });
  }

  private loadLedger(): void {
    const trialParams = this.reportParams();
    let ledgerParams = new HttpParams().set('start', this.glStart || this.start).set('end', this.glEnd || this.end);
    if (this.accountId) {
      ledgerParams = ledgerParams.set('account', String(this.accountId));
    }
    this.loading.set(true);
    forkJoin({
      trial: this.http.get<Row>('/api/v1/reporting/trial-balance/', { params: trialParams }),
      register: this.http.get<Row>('/api/v1/reporting/journal-register/', {
        params: this.reportParams(),
      }),
      ledger: this.accountId
        ? this.http.get<Row>('/api/v1/reporting/general-ledger/', { params: ledgerParams })
        : of(null),
    }).subscribe({
      next: ({ trial, register, ledger }) => {
        this.loading.set(false);
        this.metrics.set([
          {
            label: 'Total debit',
            value: this.money(trial['total_debit']),
            note: 'All posted lines up to the end date',
            tone: 'actual',
          },
          {
            label: 'Total credit',
            value: this.money(trial['total_credit']),
            note: 'All posted lines up to the end date',
            tone: 'actual',
          },
          {
            label: 'Posted journals',
            value: this.number(register['posted_count']),
            note: `${this.money(register['posted_total'])} posted debits`,
            tone: 'actual',
          },
          {
            label: 'Unposted journals',
            value: this.number(register['unposted_count']),
            note: 'Excluded from every financial statement',
            tone: 'operational',
          },
        ]);
        const sections: ReportSection[] = [
          {
            title: 'Trial balance',
            columns: [
              { key: 'code', label: 'Code' },
              { key: 'name', label: 'Account' },
              { key: 'account_type', label: 'Type' },
              { key: 'debit', label: 'Debit' },
              { key: 'credit', label: 'Credit' },
              { key: 'balance', label: 'Balance' },
            ],
            rows: this.rows(trial['rows']),
            note: trial['balanced'] === true ? 'Debits equal credits.' : 'The trial balance is not balanced.',
          },
          {
            title: 'Journal register',
            columns: [
              { key: 'number', label: 'Journal' },
              { key: 'journal_date', label: 'Date' },
              { key: 'description', label: 'Description' },
              { key: 'source', label: 'Source' },
              { key: 'status', label: 'Status' },
              { key: 'total_debit', label: 'Debit' },
              { key: 'created_by', label: 'Created by' },
              { key: 'posted_by', label: 'Posted by' },
            ],
            rows: this.rows(register['rows']),
            note: 'Unposted rows are shown for control but never included in financial totals.',
          },
        ];
        if (ledger) {
          sections.unshift({
            title: `General ledger — ${String(ledger['code'])} ${String(ledger['name'])}`,
            columns: [
              { key: 'journal_date', label: 'Date' },
              { key: 'journal_number', label: 'Journal' },
              { key: 'description', label: 'Description' },
              { key: 'debit', label: 'Debit' },
              { key: 'credit', label: 'Credit' },
              { key: 'balance', label: 'Running balance' },
            ],
            rows: this.rows(ledger['entries']),
            note: `Opening ${this.money(ledger['opening_balance'])}; closing ${this.money(ledger['closing_balance'])}.`,
          });
        }
        this.sections.set(sections);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error));
      },
    });
  }

  private loadReceivables(): void {
    this.get('/api/v1/reporting/receivables-ageing/', this.reportParams(), (body) => {
      this.ageing(body, 'customer', 'Customer invoices');
    });
  }

  private loadPayables(): void {
    this.get('/api/v1/reporting/payables-ageing/', this.reportParams(), (body) => {
      this.ageing(body, 'supplier', 'Supplier invoices');
    });
  }

  private ageing(body: Row, party: string, title: string): void {
    const mixed = body['mixed_currency'] === true;
    const rawBuckets = this.rows(body['buckets']);
    const buckets: Row[] = mixed
      ? this.rows(body['by_currency']).flatMap((currency) =>
          this.rows(currency['buckets']).map((bucket): Row => ({
            ...bucket,
            currency: currency['currency'],
          })),
        )
      : rawBuckets;
    this.metrics.set([
      {
        label: 'Outstanding',
        value: mixed ? 'Multiple currencies' : this.money(body['total']),
        note: mixed
          ? 'Separate currency totals are shown below; no exchange rate is assumed'
          : `${title} approved at the reporting date`,
        tone: 'operational',
      },
      {
        label: 'Overdue',
        value: mixed ? 'See currency totals' : this.money(body['overdue']),
        note: 'Past the recorded due date',
        tone: 'operational',
      },
      ...(mixed ? [] : buckets.slice(0, 3)).map((row) => ({
        label: String(row['bucket']),
        value: this.money(row['amount']),
        note: 'Ageing bucket',
        tone: 'operational' as const,
      })),
    ]);
    this.sections.set([
      {
        title: 'Ageing summary',
        columns: [
          ...(mixed ? [{ key: 'currency', label: 'Currency' }] : []),
          { key: 'bucket', label: 'Bucket' },
          { key: 'amount', label: mixed ? 'Balance' : 'Balance (NGN)' },
        ],
        rows: buckets,
        note: `Source: ${formatValue(body['source'], 'status')}. ${
          mixed
            ? 'Multiple currencies are present and are not added together; each currency total is shown separately. '
            : ''
        }These are document balances, not ledger receivables or payables.`,
      },
      {
        title: title,
        columns: [
          { key: 'number', label: 'Document' },
          { key: party, label: party === 'customer' ? 'Customer' : 'Supplier' },
          { key: 'invoice_date', label: 'Invoice date' },
          { key: 'due_date', label: 'Due date' },
          { key: 'currency', label: 'Currency' },
          { key: 'balance', label: 'Balance' },
          { key: 'days_overdue', label: 'Days overdue' },
          { key: 'bucket', label: 'Bucket' },
          { key: 'project', label: 'Project' },
        ],
        rows: this.rows(body['rows']),
      },
    ]);
    this.bars.set(
      this.makeBars(
        buckets.map((row) => ({
          label: String(row['bucket']),
          value: Number(row['amount'] ?? 0),
          display: this.money(row['amount']),
        })),
      ),
    );
  }

  private loadProcurement(): void {
    this.get('/api/v1/reporting/procurement/', this.reportParams(), (body) => {
      const orders = this.obj(body['purchase_orders']);
      const deliveries = this.rows(body['outstanding_deliveries']);
      this.metrics.set([
        {
          label: 'Orders raised',
          value: this.number(orders['count']),
          note: 'Purchase orders created in the period',
          tone: 'operational',
          link: '/procurement',
        },
        {
          label: 'Committed value',
          value: this.money(orders['committed_value']),
          note: 'Approved, issued or received orders; not expenses',
          tone: 'operational',
        },
        {
          label: 'Approved invoices',
          value: this.money(body['approved_invoice_value']),
          note: `${this.number(body['approved_invoice_count'])} supplier invoices`,
          tone: 'actual',
          link: '/invoicing',
        },
        {
          label: 'Outstanding deliveries',
          value: this.number(deliveries.length),
          note: 'Schedules with quantity still due',
          tone: 'operational',
        },
        {
          label: 'Average lead time',
          value: body['average_lead_time_days'] ? `${String(body['average_lead_time_days'])} days` : '—',
          note: 'Recorded supplier quote lead times',
          tone: 'operational',
        },
      ]);
      this.sections.set([
        {
          title: 'Purchase orders by status',
          columns: [
            { key: 'status', label: 'Status' },
            { key: 'count', label: 'Orders' },
            { key: 'value', label: 'Order value (NGN)' },
          ],
          rows: this.rows(orders['by_status']),
          note: String(body['note'] ?? ''),
        },
        {
          title: 'Supplier activity',
          columns: [
            { key: 'supplier', label: 'Supplier' },
            { key: 'orders', label: 'Orders' },
            { key: 'order_value', label: 'Order value' },
            { key: 'approved_invoice_value', label: 'Approved invoices' },
          ],
          rows: this.rows(body['suppliers']),
        },
        {
          title: 'Outstanding deliveries',
          columns: [
            { key: 'order', label: 'Order' },
            { key: 'supplier', label: 'Supplier' },
            { key: 'item', label: 'Item' },
            { key: 'due_date', label: 'Due' },
            { key: 'ordered', label: 'Ordered' },
            { key: 'delivered', label: 'Delivered' },
            { key: 'outstanding', label: 'Outstanding' },
            { key: 'overdue', label: 'Overdue' },
          ],
          rows: deliveries,
        },
      ]);
      this.bars.set(
        this.makeBars(
          this.rows(orders['by_status']).map((row) => ({
            label: formatValue(row['status'], 'status'),
            value: Number(row['count'] ?? 0),
            display: `${this.number(row['count'])} orders · ${this.money(row['value'])}`,
          })),
        ),
      );
    });
  }

  private loadInventory(): void {
    this.get('/api/v1/reporting/inventory/', this.reportParams(), (body) => {
      this.metrics.set([
        {
          label: 'Stock value',
          value: body['valuation_available'] ? this.money(body['total_value']) : 'Unavailable',
          note: body['valuation_available']
            ? `${String(body['valuation_method'])} valuation`
            : String(body['valuation_error'] ?? 'No valuation method'),
          tone: body['valuation_available'] ? 'operational' : 'muted',
          link: '/inventory',
        },
        {
          label: 'Total quantity',
          value: body['valuation_available'] ? this.number(body['total_quantity'], 4) : '—',
          note: 'Derived from the stock movement ledger',
          tone: 'operational',
        },
        {
          label: 'Low-stock alerts',
          value: this.number(this.rows(body['low_stock']).length),
          note: 'At or below a recorded reorder level',
          tone: 'operational',
        },
        {
          label: 'Damaged lines',
          value: this.number(this.rows(body['damaged']).length),
          note: 'Written off in the reporting period',
          tone: 'operational',
        },
      ]);
      if (body['valuation_available'] !== true) {
        this.warnings.set([String(body['valuation_error'] ?? 'Valuation is unavailable.')]);
      }
      this.sections.set([
        {
          title: 'Stock balances and valuation',
          columns: [
            { key: 'item_code', label: 'Item' },
            { key: 'item_name', label: 'Name' },
            { key: 'warehouse_code', label: 'Warehouse' },
            { key: 'on_hand', label: 'On hand' },
            { key: 'reserved', label: 'Reserved' },
            { key: 'available', label: 'Available' },
            { key: 'unit_cost', label: 'Unit cost' },
            { key: 'value', label: 'Value' },
          ],
          rows: this.rows(body['balances']),
        },
        {
          title: 'Stock movements',
          columns: [
            { key: 'number', label: 'Movement' },
            { key: 'date', label: 'Date' },
            { key: 'type', label: 'Type' },
            { key: 'item', label: 'Item' },
            { key: 'warehouse', label: 'Warehouse' },
            { key: 'quantity', label: 'Quantity' },
            { key: 'value', label: 'Value' },
            { key: 'project', label: 'Project' },
          ],
          rows: this.rows(body['movements']),
        },
        {
          title: 'Issued to projects',
          columns: [
            { key: 'number', label: 'Issue' },
            { key: 'date', label: 'Date' },
            { key: 'project', label: 'Project' },
            { key: 'item', label: 'Item' },
            { key: 'quantity', label: 'Quantity' },
            { key: 'value', label: 'Value' },
          ],
          rows: this.rows(body['project_issues']),
        },
        {
          title: 'Low-stock alerts',
          columns: [
            { key: 'item_code', label: 'Item' },
            { key: 'warehouse_code', label: 'Warehouse' },
            { key: 'minimum_quantity', label: 'Minimum' },
            { key: 'on_hand', label: 'On hand' },
            { key: 'available', label: 'Available' },
            { key: 'shortfall', label: 'Shortfall' },
          ],
          rows: this.rows(body['low_stock']),
        },
        {
          title: 'Inventory ageing (FIFO layers)',
          columns: [
            { key: 'item', label: 'Item' },
            { key: 'warehouse', label: 'Warehouse' },
            { key: 'received_on', label: 'Received' },
            { key: 'age_days', label: 'Age (days)' },
            { key: 'bucket', label: 'Bucket' },
            { key: 'remaining_quantity', label: 'Remaining' },
            { key: 'value', label: 'Value' },
          ],
          rows: this.rows(body['ageing']),
        },
      ]);
      this.bars.set(
        this.makeBars([
          { label: 'Available', value: Number(body['total_quantity'] ?? 0), display: `${this.number(body['total_quantity'], 4)} units` },
          { label: 'Low stock', value: this.rows(body['low_stock']).length, display: `${this.rows(body['low_stock']).length} alerts` },
          { label: 'Damaged', value: this.rows(body['damaged']).length, display: `${this.rows(body['damaged']).length} lines` },
        ]),
      );
    });
  }

  private loadProjects(): void {
    this.get('/api/v1/reporting/projects/', this.reportParams(), (body) => {
      const projects = this.rows(body['projects']);
      const profitability = this.rows(body['profitability']);
      this.metrics.set([
        {
          label: 'Projects',
          value: this.number(projects.length),
          note: `${this.number(projects.filter((row) => row['status'] === 'active').length)} active`,
          tone: 'operational',
          link: '/projects',
        },
        {
          label: 'Approved budgets',
          value: this.money(this.sum(projects, 'budget_total')),
          note: 'Latest approved budget per project',
          tone: 'operational',
        },
        {
          label: 'Actual cost',
          value: this.money(this.sum(projects, 'actual_total')),
          note: 'Invoices, project issues and approved direct costs',
          tone: 'operational',
        },
        {
          label: 'Open commitments',
          value: this.money(this.sum(projects, 'open_commitment')),
          note: 'Order value not yet invoiced',
          tone: 'operational',
        },
        {
          label: 'Estimated margin',
          value: this.money(this.sum(profitability, 'estimated_margin')),
          note: 'Estimate only; revenue recognition is disabled',
          tone: 'operational',
        },
      ]);
      this.sections.set([
        {
          title: 'Project budget and cost',
          columns: [
            { key: 'code', label: 'Project' },
            { key: 'name', label: 'Name' },
            { key: 'status', label: 'Status' },
            { key: 'budget_version', label: 'Budget v.' },
            { key: 'budget_total', label: 'Budget' },
            { key: 'actual_total', label: 'Actual cost' },
            { key: 'open_commitment', label: 'Open commitment' },
            { key: 'available_budget', label: 'Available' },
          ],
          rows: projects,
        },
        {
          title: 'Estimated profitability',
          columns: [
            { key: 'project', label: 'Project' },
            { key: 'contract_value', label: 'Contract value' },
            { key: 'actual_cost', label: 'Actual cost' },
            { key: 'open_commitments', label: 'Open commitments' },
            { key: 'estimated_cost_to_complete', label: 'Est. final cost' },
            { key: 'estimated_margin', label: 'Est. margin' },
            { key: 'estimated_margin_percent', label: 'Margin %' },
          ],
          rows: profitability.map((row) => ({ ...row, ...(this.obj(row['project']) as Row) })),
          note: String(body['note'] ?? ''),
        },
        {
          title: 'Milestones',
          columns: [
            { key: 'project', label: 'Project' },
            { key: 'milestone', label: 'Milestone' },
            { key: 'due_date', label: 'Due' },
            { key: 'completed_on', label: 'Completed' },
            { key: 'status', label: 'Status' },
            { key: 'overdue', label: 'Overdue' },
          ],
          rows: this.rows(body['milestones']),
        },
        {
          title: 'Approved direct cost by category',
          columns: [
            { key: 'category', label: 'Category' },
            { key: 'count', label: 'Entries' },
            { key: 'amount', label: 'Amount' },
          ],
          rows: this.rows(body['approved_cost_by_category']),
        },
      ]);
      this.bars.set(
        this.makeBars(
          projects.slice(0, 6).map((row) => ({
            label: String(row['code']),
            value: Number(row['actual_total'] ?? 0),
            display: `${this.money(row['budget_total'])} budget · ${this.money(row['actual_total'])} actual`,
          })),
        ),
      );
    });
  }

  private loadOperations(): void {
    this.get('/api/v1/reporting/operations/', this.reportParams(), (body) => {
      const orders = this.obj(body['work_orders']);
      const maintenance = this.obj(body['maintenance']);
      const utilisation = this.rows(body['equipment_utilisation']);
      this.metrics.set([
        {
          label: 'Work orders',
          value: this.number(orders['total']),
          note: `${String(orders['completion_rate'] ?? '—')}% completed or accepted`,
          tone: 'operational',
          link: '/services',
        },
        {
          label: 'Maintenance cost',
          value: this.money(maintenance['cost']),
          note: `${this.number(maintenance['count'])} maintenance records`,
          tone: 'operational',
        },
        {
          label: 'Rental value',
          value: this.money(body['rental_value']),
          note: 'Agreements overlapping the period',
          tone: 'operational',
          link: '/leasing',
        },
        {
          label: 'Overdue returns',
          value: this.number(this.rows(body['overdue_returns']).length),
          note: 'Latest movement is still a dispatch',
          tone: 'operational',
        },
        {
          label: 'Equipment register',
          value: this.number(body['equipment_count']),
          note: 'All recorded equipment',
          tone: 'operational',
        },
      ]);
      this.sections.set([
        {
          title: 'Work orders by status',
          columns: [
            { key: 'status', label: 'Status' },
            { key: 'count', label: 'Work orders' },
          ],
          rows: this.rows(orders['by_status']),
        },
        {
          title: 'Equipment utilisation',
          columns: Object.keys(utilisation[0] ?? {}).map((key) => ({
            key,
            label: formatValue(key, 'status'),
          })),
          rows: utilisation,
        },
        {
          title: 'Rental agreements',
          columns: [
            { key: 'number', label: 'Agreement' },
            { key: 'customer', label: 'Customer' },
            { key: 'status', label: 'Status' },
            { key: 'start_date', label: 'Start' },
            { key: 'end_date', label: 'End' },
            { key: 'value', label: 'Value' },
          ],
          rows: this.rows(body['rental_agreements']),
        },
        {
          title: 'Overdue returns',
          columns: [
            { key: 'agreement', label: 'Agreement' },
            { key: 'customer', label: 'Customer' },
            { key: 'equipment', label: 'Equipment' },
            { key: 'expected_return', label: 'Expected return' },
          ],
          rows: this.rows(body['overdue_returns']),
        },
      ]);
      this.bars.set(
        this.makeBars(
          this.rows(orders['by_status']).map((row) => ({
            label: formatValue(row['status'], 'status'),
            value: Number(row['count'] ?? 0),
            display: `${this.number(row['count'])} work orders`,
          })),
        ),
      );
    });
  }

  private loadBanking(): void {
    this.get('/api/v1/reporting/banking/', this.reportParams(), (body) => {
      const statements = this.obj(body['statements']);
      const accounts = this.rows(body['accounts']);
      this.metrics.set([
        {
          label: 'Bank accounts',
          value: this.number(accounts.length),
          note: 'Active and inactive accounts on record',
          tone: 'operational',
          link: '/banking',
        },
        {
          label: 'Statements',
          value: this.number(statements['count']),
          note: `${this.number(statements['reconciled'])} reconciled`,
          tone: 'operational',
        },
        {
          label: 'Cash accounts',
          value: this.number(this.rows(body['cash_accounts']).length),
          note: 'Petty cash and imprest accounts',
          tone: 'operational',
        },
        {
          label: 'Reconciliations',
          value: this.number(this.rows(body['reconciliations']).length),
          note: 'Periods overlapping the range',
          tone: 'operational',
        },
      ]);
      this.sections.set([
        {
          title: 'Bank accounts',
          columns: [
            { key: 'code', label: 'Code' },
            { key: 'name', label: 'Account' },
            { key: 'bank', label: 'Bank' },
            { key: 'gl_account', label: 'GL account' },
            { key: 'opening_balance', label: 'Opening balance' },
            { key: 'recorded_movement', label: 'Recorded movement' },
          ],
          rows: accounts,
          note: String(body['note'] ?? ''),
        },
        {
          title: 'Reconciliations',
          columns: [
            { key: 'number', label: 'Reconciliation' },
            { key: 'bank_account', label: 'Account' },
            { key: 'period_start', label: 'Start' },
            { key: 'period_end', label: 'End' },
            { key: 'status', label: 'Status' },
            { key: 'posting_status', label: 'Posting' },
            { key: 'posting_blocker', label: 'Posting blocker' },
            { key: 'statement_closing_balance', label: 'Statement closing' },
          ],
          rows: this.rows(body['reconciliations']),
        },
        {
          title: 'Cash accounts',
          columns: [
            { key: 'code', label: 'Code' },
            { key: 'name', label: 'Name' },
            { key: 'opening_balance', label: 'Opening balance' },
            { key: 'imprest_amount', label: 'Imprest' },
            { key: 'recorded_vouchers', label: 'Recorded vouchers' },
          ],
          rows: this.rows(body['cash_accounts']),
        },
      ]);
    });
  }

  private loadTax(): void {
    this.get('/api/v1/reporting/tax/', this.reportParams(), (body) => {
      const input = this.obj(body['input_vat']);
      const output = this.obj(body['output_vat']);
      const mixed = body['mixed_currency'] === true;
      const inputRows = mixed
        ? this.rows(input['by_currency']).map((row) => ({
            measure: `Input VAT (${String(row['currency'])})`,
            value: row['vat_total'],
          }))
        : [
            { measure: 'VAT recorded', value: input['vat'] },
            { measure: 'VAT recoverable', value: input['recoverable'] },
            { measure: 'WHT recorded', value: input['wht'] },
          ];
      const outputRows = mixed
        ? this.rows(output['by_currency']).map((row) => ({
            measure: `Output VAT (${String(row['currency'])})`,
            value: row['vat_total'],
          }))
        : [
            { measure: 'Output VAT', value: output['vat'] },
            { measure: 'Customer WHT', value: output['wht'] },
            { measure: 'Credit / debit note VAT', value: this.obj(body['notes'])['vat'] },
          ];
      this.metrics.set([
        {
          label: 'Input VAT',
          value: mixed ? 'Multiple currencies' : this.money(input['vat']),
          note: `${this.number(input['approved_invoices'])} approved supplier invoices${
            mixed ? '; no exchange rate is assumed' : ''
          }`,
          tone: 'operational',
        },
        {
          label: 'Recoverable input VAT',
          value: mixed ? 'See currency totals' : this.money(input['recoverable']),
          note: 'As recorded on approved invoices',
          tone: 'operational',
        },
        {
          label: 'Output VAT',
          value: mixed ? 'Multiple currencies' : this.money(output['vat']),
          note: `${this.number(output['approved_invoices'])} approved customer invoices`,
          tone: 'operational',
        },
        {
          label: 'WHT recorded',
          value: mixed ? 'See currency totals' : this.money(input['wht']),
          note: 'Supplier document withholding',
          tone: 'operational',
        },
      ]);
      this.sections.set([
        {
          title: 'Tax configuration register',
          columns: [
            { key: 'code', label: 'Code' },
            { key: 'name', label: 'Name' },
            { key: 'tax_type', label: 'Type' },
            { key: 'rate', label: 'Rate' },
            { key: 'jurisdiction', label: 'Jurisdiction' },
            { key: 'review_status', label: 'Review' },
          ],
          rows: this.rows(body['configurations']),
          note: String(body['note'] ?? ''),
        },
        {
          title: 'Input tax by approved document',
          columns: [
            { key: 'measure', label: 'Measure' },
            { key: 'value', label: 'Amount' },
          ],
          rows: inputRows,
        },
        {
          title: 'Output tax and notes',
          columns: [
            { key: 'measure', label: 'Measure' },
            { key: 'value', label: 'Amount' },
          ],
          rows: outputRows,
        },
      ]);
    });
  }

  private get(url: string, params: HttpParams, onSuccess: (body: Row) => void): void {
    this.loading.set(true);
    this.http.get<Row>(url, { params }).subscribe({
      next: (body) => {
        this.loading.set(false);
        onSuccess(body);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error));
      },
    });
  }

  private loadOptions(url: string, target: { set: (rows: Row[]) => void }): void {
    this.http.get<unknown>(url).subscribe({
      next: (body) => {
        const rows = Array.isArray(body)
          ? (body as Row[])
          : Array.isArray((body as Row)?.['results'])
            ? ((body as Row)['results'] as Row[])
            : [];
        target.set(rows);
      },
      error: () => target.set([]),
    });
  }

  private reportParams(): HttpParams {
    return new HttpParams().set('start', this.start).set('end', this.end);
  }

  private exportName(): string {
    switch (this.tab()) {
      case 'financial':
        return 'financial-statements';
      case 'ledger':
        return 'journal-register';
      case 'receivable':
        return 'receivables-ageing';
      case 'payable':
        return 'payables-ageing';
      case 'operations':
        return 'operations';
      default:
        return this.tab();
    }
  }

  private makeBars(rows: BarInput[]): Bar[] {
    const max = Math.max(...rows.map((row) => Math.abs(row.value)), 0);
    return rows.map((row) => ({
      ...row,
      percent: max === 0 ? 0 : Math.round((Math.abs(row.value) / max) * 100),
    }));
  }

  private rows(value: unknown): Row[] {
    return Array.isArray(value) ? (value as Row[]) : [];
  }

  private obj(value: unknown): Row {
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Row) : {};
  }

  private strings(value: unknown): string[] {
    return Array.isArray(value) ? value.map(String) : [];
  }

  private group(label: string, value: unknown): Row[] {
    return this.rows(value).map((row) => ({ ...row, group: label }));
  }

  private sum(rows: Row[], key: string): number {
    return rows.reduce((total, row) => total + Number(row[key] || 0), 0);
  }

  private money(value: unknown): string {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    const amount = Number(value);
    if (Number.isNaN(amount)) {
      return String(value);
    }
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: 'NGN',
      maximumFractionDigits: 2,
    }).format(amount);
  }

  private number(value: unknown, digits = 0): string {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    const number = Number(value);
    if (Number.isNaN(number)) {
      return String(value);
    }
    return new Intl.NumberFormat('en-NG', { maximumFractionDigits: digits }).format(number);
  }

  private today(): string {
    return new Date().toISOString().slice(0, 10);
  }

  private monthStart(): string {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
  }
}
