import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AuthService } from '../../core/auth.service';
import { TEST_USER } from '../../core/testing/auth.fixtures';
import { HealthService } from '../../core/health.service';
import { DashboardComponent } from './dashboard.component';

describe('DashboardComponent', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: { user: signal(TEST_USER).asReadonly() } },
        {
          provide: HealthService,
          useValue: { check: () => of({ status: 'ok', checks: { database: 'ok' } }) },
        },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  function flushQueues(): void {
    http
      .expectOne('/api/v1/purchase-requests/?page=1&page_size=1&status=submitted')
      .flush({ count: 2, results: [] });
    http
      .expectOne('/api/v1/purchase-orders/?page=1&page_size=1&status=submitted')
      .flush({ count: 0, results: [] });
    http
      .expectOne('/api/v1/journals/?page=1&page_size=1&status=submitted')
      .flush({ count: 1, results: [] });
    http
      .expectOne('/api/v1/reorder-alerts/?page=1&page_size=1')
      .flush({ count: 3, rows: [] });
  }

  it('greets the signed-in user', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flushQueues();
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('h1') as HTMLElement;
    expect(heading.textContent).toContain('Ama Okafor');
  });

  it('shows the backend readiness reported by the API', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flushQueues();
    fixture.detectChanges();

    const status = fixture.nativeElement.querySelector('.status') as HTMLElement;
    expect(status.textContent).toContain('API reachable');
  });

  it('renders live queue counts from the API', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flushQueues();
    fixture.detectChanges();

    const counts = Array.from(
      fixture.nativeElement.querySelectorAll('.queue__count') as NodeListOf<HTMLElement>,
    ).map((element) => element.textContent?.trim());

    expect(counts).toEqual(['2', '0', '1', '3']);
  });

  it('names the permission required instead of offering an unavailable approval', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flushQueues();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('procurement.approve_purchaserequest');

    // The approval queue must not offer a link that leads only to a disabled action.
    const approvalQueue = fixture.nativeElement.querySelector('.queue') as HTMLElement;
    expect(approvalQueue.querySelector('.queue__link')).toBeNull();
    expect(approvalQueue.textContent).toContain('Requires procurement.approve_purchaserequest');
  });

  it('does not present an empty queue as zero when the request fails', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();

    http
      .expectOne('/api/v1/purchase-requests/?page=1&page_size=1&status=submitted')
      .flush(null, { status: 500, statusText: 'Server Error' });
    http
      .expectOne('/api/v1/purchase-orders/?page=1&page_size=1&status=submitted')
      .flush({ count: 0, results: [] });
    http
      .expectOne('/api/v1/journals/?page=1&page_size=1&status=submitted')
      .flush({ count: 0, results: [] });
    http
      .expectOne('/api/v1/reorder-alerts/?page=1&page_size=1')
      .flush({ count: 0, rows: [] });
    fixture.detectChanges();

    const counts = Array.from(
      fixture.nativeElement.querySelectorAll('.queue__count') as NodeListOf<HTMLElement>,
    ).map((element) => element.textContent?.trim());

    expect(counts[0]).toBe('—');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Some queues could not be loaded',
    );
  });
});
