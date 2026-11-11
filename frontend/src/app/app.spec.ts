import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { App } from './app';
import { HealthService } from './core/health.service';

describe('App', () => {
  const healthStub = {
    check: () => of({ status: 'ok', checks: { database: 'ok' } }),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [{ provide: HealthService, useValue: healthStub }],
    }).compileComponents();
  });

  it('renders the platform name', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('h1') as HTMLElement;
    expect(heading.textContent).toContain('TMD Platform');
  });

  it('shows the API readiness reported by the backend', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();

    const status = fixture.nativeElement.querySelector('.status') as HTMLElement;
    expect(status.textContent).toContain('API reachable');
  });

  it('states that business logic is disabled', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const footer = fixture.nativeElement.querySelector('.app-footer') as HTMLElement;
    expect(footer.textContent).toContain('no business logic enabled');
  });
});
