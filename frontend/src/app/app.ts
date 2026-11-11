import { KeyValuePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { HealthService, Readiness } from './core/health.service';

@Component({
  imports: [RouterOutlet, KeyValuePipe],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  private readonly health = inject(HealthService);

  protected readonly title = signal('TMD Platform');
  protected readonly readiness = signal<Readiness | null>(null);
  protected readonly apiUnreachable = signal(false);

  constructor() {
    this.health.check().subscribe({
      next: (status) => this.readiness.set(status),
      error: () => this.apiUnreachable.set(true),
    });
  }
}
