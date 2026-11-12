import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

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
  recent_activity: Activity[];
}

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
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

  constructor() {
    this.load();
  }

  protected setPeriod(value: string): void {
    const choice = value as PeriodChoice;
    this.period.set(choice);
    this.customError.set(null);
    if (choice === 'this_month') {
      this.start.set(this.monthStart(0));
      this.end.set(this.today());
      this.load();
    } else if (choice === 'last_month') {
      const previous = new Date();
      previous.setDate(1);
      previous.setMonth(previous.getMonth() - 1);
      this.start.set(this.toIso(previous));
      this.end.set(this.toIso(new Date(previous.getFullYear(), previous.getMonth() + 1, 0)));
      this.load();
    }
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

  protected stateLabel(state: DashboardCard['state']): string {
    return {
      test: 'Test',
      actual: 'Approved',
      recorded: 'Recorded',
      no_data: 'No data',
    }[state];
  }

  protected naira(value: string | null): string {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency',
      currency: 'NGN',
      currencyDisplay: 'narrowSymbol',
      minimumFractionDigits: 2,
    }).format(Number(value ?? 0));
  }

  protected operationValue(card: OperationCard): string {
    if (card.format === 'currency') {
      return card.value === '' || card.value === null ? 'Not available' : this.naira(String(card.value));
    }
    if (card.format === 'empty' || card.value === '' || card.value === null) {
      return 'Not available';
    }
    return new Intl.NumberFormat('en-NG').format(Number(card.value));
  }

  protected activityTime(value: string): string {
    return new Intl.DateTimeFormat('en-NG', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));
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
