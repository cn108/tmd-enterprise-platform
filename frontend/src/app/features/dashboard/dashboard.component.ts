import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { Params, RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/auth.models';
import { AuthService } from '../../core/auth.service';

type PeriodChoice = 'this_month' | 'last_month' | 'custom';

interface Focus {
  id: string;
  title: string;
  description: string;
}

interface DashboardCard {
  id: string;
  label: string;
  amount: string | null;
  count: number;
  available: boolean;
  basis: string;
  state: 'test' | 'actual' | 'recorded' | 'no_data';
  link: string;
  note: string;
  tone: 'neutral' | 'positive' | 'warning' | 'attention' | 'clear';
  change_percent: string | null;
}

interface FinancialHistoryPoint {
  month: string;
  receipts: string;
  payments: string;
}

interface PendingAction {
  id: string;
  label: string;
  count: number;
  link: string;
  description: string;
  tone: string;
}

interface OperationCard {
  id: string;
  label: string;
  value: string | number;
  format: 'currency' | 'number' | 'empty';
  detail: string;
  link: string;
}

interface Activity {
  id: number;
  action: string;
  entity: string;
  reference: string;
  user: string;
  occurred_at: string;
  link: string;
}

interface QuickAction {
  id: string;
  label: string;
  description: string;
  link: string;
}

interface ModuleAccess {
  id: string;
  label: string;
  path: string;
  description: string;
  readable: boolean;
  access: 'full' | 'limited' | 'view_only' | 'restricted' | 'standard';
}

interface ProcurementOrder {
  id: number;
  number: string;
  supplier: string;
  status: string;
  created_at: string;
  total_value: string;
  link: string;
}

interface ProcurementActivity {
  title: string;
  description: string;
  cards: OperationCard[];
  recent_orders: ProcurementOrder[];
}

interface ProjectPerformanceRow {
  id: number;
  code: string;
  name: string;
  status: string;
  budget_total: string;
  actual_total: string;
  open_commitment: string;
  available_budget: string;
  utilisation_percent: string | null;
  link: string;
}

interface ProjectPerformance {
  rows: ProjectPerformanceRow[];
  summary: {
    project_count: number;
    budget_total: string;
    actual_total: string;
    open_commitment: string;
    available_budget: string;
    used_total: string;
    utilisation_percent: string | null;
  };
  note: string;
}

interface Dashboard {
  generated_at: string;
  currency: string;
  period: { start: string; end: string };
  focus: Focus;
  issuance_authorised: boolean;
  test_mode: boolean;
  notices: string[];
  financial_overview: DashboardCard[] | null;
  financial_history: FinancialHistoryPoint[] | null;
  invoice_management: DashboardCard[] | null;
  pending_actions: PendingAction[];
  module_access: ModuleAccess[];
  quick_actions: QuickAction[];
  operations: {
    id: string;
    title: string;
    description: string;
    cards: OperationCard[];
  } | null;
  procurement_activity: ProcurementActivity | null;
  project_performance: ProjectPerformance | null;
  recent_activity: Activity[];
}

interface ChartTick {
  ratio: number;
  label: string;
}

const KPI_LABELS: Record<string, string> = {
  customer_outstanding: 'Outstanding Customer Invoices',
  customer_overdue: 'Overdue Receivables',
  supplier_outstanding: 'Outstanding Supplier Invoices',
  supplier_due: 'Due for Payment',
  payments_received: 'Payments Received (This Period)',
  payments_made: 'Payments Made (This Period)',
};

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrls: [
    './dashboard.component.scss',
    './dashboard-header.scss',
    './dashboard-chart.scss',
    './dashboard-cards.scss',
    './dashboard-activity.scss',
    './dashboard-modules.scss',
  ],
})
export class DashboardComponent {
  private readonly http = inject(HttpClient);
  protected readonly auth = inject(AuthService);

  protected readonly data = signal<Dashboard | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly period = signal<PeriodChoice>('this_month');
  protected readonly start = signal(this.monthStart(0));
  protected readonly end = signal(this.today());
  protected readonly customError = signal<string | null>(null);

  protected readonly greetingName = computed(
    () => (this.auth.user()?.full_name ?? '').split(/\s+/).filter(Boolean)[0] ?? '',
  );
  protected readonly financialCards = computed(() => this.data()?.financial_overview ?? []);
  protected readonly chartRows = computed(() => this.data()?.financial_history ?? []);
  protected readonly chartMax = computed(() => {
    const values = this.chartRows().flatMap((row) => [Number(row.receipts), Number(row.payments)]);
    return this.niceMaximum(Math.max(0, ...values));
  });
  protected readonly chartTicks = computed<ChartTick[]>(() =>
    [1, 0.75, 0.5, 0.25, 0].map((ratio) => ({
      ratio,
      label: this.compactAmount(this.chartMax() * ratio),
    })),
  );
  protected readonly chartSummary = computed(() => {
    if (!this.chartRows().length) {
      return 'No receipts or payments are available for the selected period.';
    }
    return this.chartRows()
      .map((row) => {
        const month = new Intl.DateTimeFormat('en-NG', {
          month: 'long',
          year: 'numeric',
        }).format(new Date(`${row.month}T00:00:00`));
        return `${month}: ${this.naira(row.receipts)} received, ${this.naira(row.payments)} paid`;
      })
      .join('; ');
  });
  protected readonly procurementCards = computed(
    () => this.data()?.procurement_activity?.cards.slice(0, 4) ?? [],
  );
  protected readonly firstProject = computed(
    () => this.data()?.project_performance?.rows[0] ?? null,
  );
  protected readonly projectUtilisation = computed(() => {
    const summary = this.data()?.project_performance?.summary;
    if (!summary) {
      return 0;
    }
    if (summary.utilisation_percent !== null && summary.utilisation_percent !== undefined) {
      return this.clampPercent(Number(summary.utilisation_percent));
    }
    const budget = Number(summary.budget_total);
    const used = Number(summary.actual_total) + Number(summary.open_commitment);
    return budget > 0 ? this.clampPercent((used / budget) * 100) : 0;
  });
  protected readonly projectUsed = computed(() => {
    const summary = this.data()?.project_performance?.summary;
    if (!summary) {
      return '0.00';
    }
    return (
      summary.used_total ?? String(Number(summary.actual_total) + Number(summary.open_commitment))
    );
  });
  protected readonly reportsPath = computed(() => {
    const reports = this.data()?.module_access.find((module) => module.id === 'reports');
    return reports?.readable ? reports.path : '/';
  });

  protected linkPath(link: string): string {
    return link.split('?', 1)[0] || '/';
  }

  protected linkQuery(link: string): Params {
    const query = link.split('?')[1];
    return query ? Object.fromEntries(new URLSearchParams(query)) : {};
  }

  constructor() {
    this.load();
  }

  protected setPeriod(value: string): void {
    const choice = value as PeriodChoice;
    this.period.set(choice);
    this.customError.set(null);
    if (choice === 'custom') {
      return;
    }
    if (choice === 'this_month') {
      this.start.set(this.monthStart(0));
      this.end.set(this.today());
    } else if (choice === 'last_month') {
      const previous = new Date();
      previous.setDate(1);
      previous.setMonth(previous.getMonth() - 1);
      this.start.set(this.toIso(previous));
      this.end.set(this.toIso(new Date(previous.getFullYear(), previous.getMonth() + 1, 0)));
    }
    this.load();
  }

  protected setStart(value: string): void {
    this.start.set(value);
  }

  protected setEnd(value: string): void {
    this.end.set(value);
  }

  protected applyCustom(): void {
    if (!this.start() || !this.end()) {
      this.customError.set('Choose a start and end date.');
      return;
    }
    if (this.end() < this.start()) {
      this.customError.set('The end date cannot precede the start date.');
      return;
    }
    this.customError.set(null);
    this.load();
  }

  protected reload(): void {
    this.load();
  }

  protected cardTitle(card: DashboardCard): string {
    return KPI_LABELS[card.id] ?? card.label;
  }

  protected cardAmount(card: DashboardCard): string {
    return card.available ? this.naira(card.amount) : '—';
  }

  protected cardFootnote(card: DashboardCard): string {
    if (!card.available) {
      return 'No records in this period';
    }
    if (card.change_percent !== null && card.change_percent !== undefined) {
      return `${this.changeSymbol(card)} ${this.changeValue(card)}% vs previous period`;
    }
    return `${card.count} ${card.count === 1 ? 'record' : 'records'} in this period`;
  }

  protected hasTrend(card: DashboardCard): boolean {
    return card.available && card.change_percent !== null && card.change_percent !== undefined;
  }

  protected trendPositive(card: DashboardCard): boolean {
    return Number(card.change_percent ?? 0) >= 0;
  }

  protected cardTone(id: string): string {
    return (
      {
        customer_outstanding: 'blue',
        customer_overdue: 'red',
        supplier_outstanding: 'green',
        supplier_due: 'orange',
        payments_received: 'emerald',
        payments_made: 'violet',
      }[id] ?? 'blue'
    );
  }

  protected cardIcon(id: string): string {
    return (
      {
        customer_outstanding: 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h5',
        customer_overdue: 'M12 3 2.5 20h19zM12 9v5M12 17h.01',
        supplier_outstanding: 'M3 4h2l2.2 10h10.4L20 7H6M9 20h.01M17 20h.01',
        supplier_due: 'M4 6h16v15H4zM8 3v5M16 3v5M4 10h16M8 14h3M8 17h6',
        payments_received: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 7v9M8 12l4 4 4-4',
        payments_made: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 17V8M8 12l4-4 4 4',
      }[id] ?? 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18'
    );
  }

  protected monthDate(value: string): Date {
    const [year, month] = value.split('-').map(Number);
    return new Date(year, (month ?? 1) - 1, 1);
  }

  protected chartHeight(value: string): number {
    const max = this.chartMax();
    const numeric = Number(value);
    if (!max || !numeric) {
      return 0;
    }
    return Math.max(1.5, Math.min(100, (numeric / max) * 100));
  }

  protected chartTotal(value: string): string {
    return this.naira(value);
  }

  protected projectPercentLabel(row: ProjectPerformanceRow): string {
    if (row.utilisation_percent === null) {
      return 'No approved budget';
    }
    return `${Number(row.utilisation_percent).toFixed(1)}% used`;
  }

  protected projectDonut(): string {
    const percent = this.projectUtilisation();
    return `conic-gradient(#2fbf83 0 ${percent}%, #e9eef4 ${percent}% 100%)`;
  }

  protected projectBudgetAvailable(): boolean {
    return Number(this.data()?.project_performance?.summary.budget_total ?? 0) > 0;
  }

  protected operationValue(card: OperationCard): string {
    if (card.format === 'currency') {
      return card.value === '' || card.value === null
        ? 'Not available'
        : this.naira(String(card.value));
    }
    if (card.format === 'empty' || card.value === '' || card.value === null) {
      return 'Not available';
    }
    return new Intl.NumberFormat('en-NG').format(Number(card.value));
  }

  protected relativeTime(value: string): string {
    const occurred = new Date(value).getTime();
    if (!Number.isFinite(occurred)) {
      return '';
    }
    const minutes = Math.max(0, Math.floor((Date.now() - occurred) / 60_000));
    if (minutes < 1) {
      return 'Just now';
    }
    if (minutes < 60) {
      return `${minutes}m ago`;
    }
    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
      return `${hours}h ago`;
    }
    const days = Math.floor(hours / 24);
    if (days < 7) {
      return `${days}d ago`;
    }
    return new Intl.DateTimeFormat('en-NG', { day: 'numeric', month: 'short' }).format(
      new Date(value),
    );
  }

  protected activityIcon(entity: string): string {
    const key = entity.toLowerCase();
    if (key.includes('payment')) {
      return 'M4 7h16v10H4zM4 10h16M8 15h4';
    }
    if (key.includes('order') || key.includes('receipt')) {
      return 'M3 4h2l2.2 10h10.4L20 7H6M9 20h.01M17 20h.01';
    }
    if (key.includes('stock') || key.includes('inventory')) {
      return 'M4 8 12 4l8 4v8l-8 4-8-4zM4 8l8 4 8-4M12 12v8';
    }
    if (key.includes('budget') || key.includes('project')) {
      return 'M12 3v9l6 3M12 3a9 9 0 1 0 9 9';
    }
    return 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h5';
  }

  protected activityTone(entity: string): string {
    const key = entity.toLowerCase();
    if (key.includes('payment')) {
      return 'emerald';
    }
    if (key.includes('order')) {
      return 'orange';
    }
    if (key.includes('stock') || key.includes('receipt')) {
      return 'green';
    }
    if (key.includes('budget') || key.includes('project')) {
      return 'violet';
    }
    return 'blue';
  }

  protected quickIcon(id: string): string {
    return (
      {
        create_supplier_invoice: 'M12 5v14M5 12h14',
        draft_customer_invoice: 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h5',
        record_payment: 'M4 7h16v10H4zM4 10h16M8 15h4',
        create_purchase_request: 'M3 4h2l2.2 10h10.4L20 7H6M9 20h.01M17 20h.01',
        upload_statement: 'M12 16V4M7 9l5-5 5 5M5 20h14',
        register_project: 'M3 6h7l2 2h9v11H3zM3 6v13',
      }[id] ?? 'M12 5v14M5 12h14'
    );
  }

  protected moduleAccessLabel(access: ModuleAccess['access']): string {
    return {
      full: 'Full access',
      limited: 'Limited actions',
      view_only: 'View only',
      restricted: 'Restricted',
      standard: 'Open',
    }[access];
  }

  private changeValue(card: DashboardCard): string {
    return Math.abs(Number(card.change_percent ?? 0)).toFixed(0);
  }

  private changeSymbol(card: DashboardCard): string {
    return this.trendPositive(card) ? '↑' : '↓';
  }

  private clampPercent(value: number): number {
    return Number.isFinite(value) ? Math.min(Math.max(value, 0), 100) : 0;
  }

  private niceMaximum(value: number): number {
    if (!Number.isFinite(value) || value <= 0) {
      return 0;
    }
    const exponent = Math.floor(Math.log10(value));
    const magnitude = 10 ** exponent;
    const normalized = value / magnitude;
    const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
    return step * magnitude;
  }

  private compactAmount(value: number): string {
    if (!value) {
      return '0';
    }
    if (value >= 1_000_000_000) {
      return `${(value / 1_000_000_000).toFixed(value % 1_000_000_000 ? 1 : 0)}B`;
    }
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(value % 1_000_000 ? 1 : 0)}M`;
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(value % 1_000 ? 0 : 0)}K`;
    }
    return new Intl.NumberFormat('en-NG', { maximumFractionDigits: 0 }).format(value);
  }

  protected naira(value: string | null): string {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: 'NGN',
      currencyDisplay: 'narrowSymbol',
      minimumFractionDigits: 2,
    }).format(Number(value ?? 0));
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    const params = new HttpParams().set('start', this.start()).set('end', this.end());
    this.http.get<Dashboard>('/api/v1/dashboard/', { params }).subscribe({
      next: (dashboard) => {
        this.data.set(dashboard);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.data.set(null);
        this.error.set(apiErrorMessage(error));
        this.loading.set(false);
      },
    });
  }

  private today(): string {
    return this.toIso(new Date());
  }

  private monthStart(offset: number): string {
    const now = new Date();
    return this.toIso(new Date(now.getFullYear(), now.getMonth() + offset, 1));
  }

  private toIso(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
}
