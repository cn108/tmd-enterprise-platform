import { TestBed } from '@angular/core/testing';
import { Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { describe, expect, it, vi } from 'vitest';

import { authGuard, guestGuard } from './auth.guard';
import { AuthService } from './auth.service';

function configure(authenticated: boolean, resolved = true) {
  const stub = {
    resolved: () => resolved,
    bootstrap: vi.fn(async () => undefined),
    isAuthenticated: () => authenticated,
  };

  TestBed.configureTestingModule({
    providers: [provideRouter([]), { provide: AuthService, useValue: stub }],
  });

  return stub;
}

const state = { url: '/projects' } as RouterStateSnapshot;

describe('authGuard', () => {
  it('allows a signed-in user', async () => {
    configure(true);

    const result = await TestBed.runInInjectionContext(() => authGuard(null as never, state));

    expect(result).toBe(true);
  });

  it('redirects an anonymous user to login with the intended destination', async () => {
    configure(false);

    const result = await TestBed.runInInjectionContext(() => authGuard(null as never, state));

    expect(result instanceof UrlTree).toBe(true);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe(
      '/login?returnUrl=%2Fprojects',
    );
  });

  it('resolves the session before deciding', async () => {
    const stub = configure(false, false);

    await TestBed.runInInjectionContext(() => authGuard(null as never, state));

    expect(stub.bootstrap).toHaveBeenCalledOnce();
  });
});

describe('guestGuard', () => {
  it('sends a signed-in user to the dashboard', async () => {
    configure(true);

    const result = await TestBed.runInInjectionContext(() => guestGuard(null as never, state));

    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/');
  });

  it('allows an anonymous user onto the login page', async () => {
    configure(false);

    const result = await TestBed.runInInjectionContext(() => guestGuard(null as never, state));

    expect(result).toBe(true);
  });
});
