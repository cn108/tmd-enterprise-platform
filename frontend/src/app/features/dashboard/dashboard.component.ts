import { KeyValuePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { apiErrorMessage } from '../../core/auth.models';
import { AuthService } from '../../core/auth.service';
import { HealthService, Readiness } from '../../core/health.service';
import { ResourceApi } from '../workspace/resource-api.service';

interface QueueDefinition {
  id: string;
  label: string;
  description: string;
  endpoint: string;
  link: string;
  filters?: Record<string, string>;
  permission?: string;
}

interface QueueState extends QueueDefinition {
  count: number | null;
}

/**
 * Queues are real list endpoints with a status filter; the count is the server's
 * `count` for the whole filtered set, not the number of rows on this page.
 */
const QUEUES: QueueDefinition[] = [
  {
    id: 'requests',
    label: 'Purchase requests awaiting approval',
    description: 'Submitted requests that an authorised approver must decide.',
    endpoint: '/api/v1/purchase-requests/',
    link: '/procurement',
    filters: { status: 'submitted' },
    permission: 'procurement.approve_purchaserequest',
  },
  {
    id: 'orders',
    label: 'Purchase orders awaiting approval',
    description: 'Orders held before issue to a supplier.',
    endpoint: '/api/v1/purchase-orders/',
    link: '/procurement',
    filters: { status: 'submitted' },
    permission: 'procurement.approve_purchaseorder',
  },
  {
    id: 'journals',
    label: 'Journals awaiting approval',
    description: 'Draft journals submitted for a second person to review.',
    endpoint: '/api/v1/journals/',
    link: '/accounting',
    filters: { status: 'submitted' },
    permission: 'accounting.approve_journal',
  },
  {
    id: 'alerts',
    label: 'Reorder alerts',
    description: 'Items at or below their recorded reorder level.',
    endpoint: '/api/v1/reorder-alerts/',
    link: '/inventory',
  },
];

@Component({
  selector: 'app-dashboard',
  imports: [KeyValuePipe, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  private readonly health = inject(HealthService);
  private readonly api = inject(ResourceApi);
  protected readonly auth = inject(AuthService);

  protected readonly readiness = signal<Readiness | null>(null);
  protected readonly apiUnreachable = signal(false);
  protected readonly queues = signal<QueueState[]>([]);
  protected readonly queuesLoading = signal(true);
  protected readonly queuesError = signal<string | null>(null);

  protected readonly permissions = () => this.auth.user()?.permissions ?? [];

  constructor() {
    this.health.check().subscribe({
      next: (status) => this.readiness.set(status),
      error: () => this.apiUnreachable.set(true),
    });
    this.loadQueues();
  }

  protected mayAct(permission?: string): boolean {
    return !permission || this.permissions().includes(permission);
  }

  protected reloadQueues(): void {
    this.loadQueues();
  }

  private loadQueues(): void {
    this.queuesLoading.set(true);
    this.queuesError.set(null);

    const requests = Object.fromEntries(
      QUEUES.map((queue) => [
        queue.id,
        this.api
          .list(queue.endpoint, { page: 1, pageSize: 1, filters: queue.filters })
          .pipe(catchError(() => of(null))),
      ]),
    );

    forkJoin(requests).subscribe({
      next: (results) => {
        const states = QUEUES.map((queue) => {
          const result = results[queue.id];
          return { ...queue, count: result ? result.count : null };
        });
        this.queues.set(states);
        this.queuesLoading.set(false);
        if (states.some((state) => state.count === null)) {
          this.queuesError.set(
            'Some queues could not be loaded. The rest of the dashboard is still live.',
          );
        }
      },
      error: (error: unknown) => {
        this.queues.set([]);
        this.queuesError.set(apiErrorMessage(error));
        this.queuesLoading.set(false);
      },
    });
  }
}
