import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { beforeEach, describe, expect, it } from 'vitest';

import { AuthService } from '../../core/auth.service';
import { TEST_USER } from '../../core/testing/auth.fixtures';
import { HealthService } from '../../core/health.service';
import { DashboardComponent } from './dashboard.component';

describe('DashboardComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        { provide: AuthService, useValue: { user: signal(TEST_USER).asReadonly() } },
        {
          provide: HealthService,
          useValue: { check: () => of({ status: 'ok', checks: { database: 'ok' } }) },
        },
      ],
    }).compileComponents();
  });

  it('greets the signed-in user', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('h1') as HTMLElement;
    expect(heading.textContent).toContain('Ama Okafor');
  });

  it('shows the backend readiness reported by the API', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();

    const status = fixture.nativeElement.querySelector('.status') as HTMLElement;
    expect(status.textContent).toContain('API reachable');
  });
});
