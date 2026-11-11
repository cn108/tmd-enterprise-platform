import { KeyValuePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';

import { AuthService } from '../../core/auth.service';
import { HealthService, Readiness } from '../../core/health.service';

@Component({
  selector: 'app-dashboard',
  imports: [KeyValuePipe],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  private readonly health = inject(HealthService);
  protected readonly auth = inject(AuthService);

  protected readonly readiness = signal<Readiness | null>(null);
  protected readonly apiUnreachable = signal(false);

  constructor() {
    this.health.check().subscribe({
      next: (status) => this.readiness.set(status),
      error: () => this.apiUnreachable.set(true),
    });
  }
}
