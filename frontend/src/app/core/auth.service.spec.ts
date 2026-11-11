import { HttpClient, provideHttpClient, withInterceptors, withXsrfConfiguration } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AuthenticatedUser } from './auth.models';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';
import { TEST_USER } from './testing/auth.fixtures';

const UNAUTHENTICATED = {
  error: {
    code: 'not_authenticated',
    message: 'Authentication credentials were not provided.',
    details: null,
    request_id: 'req-1',
  },
};

function nextTick(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve));
}

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(
          withInterceptors([authInterceptor]),
          withXsrfConfiguration({ cookieName: 'csrftoken', headerName: 'X-CSRFToken' }),
        ),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    document.cookie = 'csrftoken=; Max-Age=0; path=/';
    http.verify();
  });

  it('bootstraps the CSRF cookie and an existing session', async () => {
    const ready = service.bootstrap();

    http.expectOne('/api/v1/auth/csrf/').flush({ csrfToken: 'token' });
    await nextTick();
    http.expectOne('/api/v1/auth/me/').flush(TEST_USER);
    await ready;

    expect(service.isAuthenticated()).toBe(true);
    expect(service.user()?.email).toBe('ama@example.com');
    expect(service.resolved()).toBe(true);
  });

  it('treats a rejected session as anonymous instead of failing', async () => {
    const ready = service.bootstrap();

    http.expectOne('/api/v1/auth/csrf/').flush({ csrfToken: 'token' });
    await nextTick();
    http
      .expectOne('/api/v1/auth/me/')
      .flush(UNAUTHENTICATED, { status: 401, statusText: 'Unauthorized' });
    await ready;

    expect(service.isAuthenticated()).toBe(false);
    expect(service.resolved()).toBe(true);
  });

  it('posts credentials and stores the signed-in user', () => {
    let received: AuthenticatedUser | undefined;

    service.login('ama@example.com', 'secret').subscribe((user) => (received = user));

    const request = http.expectOne('/api/v1/auth/login/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ email: 'ama@example.com', password: 'secret' });
    request.flush(TEST_USER);

    expect(received?.email).toBe('ama@example.com');
    expect(service.user()?.full_name).toBe('Ama Okafor');
  });

  it('sends the CSRF token header from the cookie on mutations', () => {
    document.cookie = 'csrftoken=csrf-token-value; path=/';

    service.login('ama@example.com', 'secret').subscribe();

    const request = http.expectOne('/api/v1/auth/login/');
    expect(request.request.headers.get('X-CSRFToken')).toBe('csrf-token-value');
    request.flush(TEST_USER);
  });

  it('clears the session on logout even when the request fails', () => {
    service.login('ama@example.com', 'secret').subscribe();
    http.expectOne('/api/v1/auth/login/').flush(TEST_USER);

    service.logout().subscribe();
    http
      .expectOne('/api/v1/auth/logout/')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(service.user()).toBeNull();
  });

  it('clears the session when any request reports an expired session', () => {
    service.login('ama@example.com', 'secret').subscribe();
    http.expectOne('/api/v1/auth/login/').flush(TEST_USER);

    TestBed.inject(HttpClient).get('/api/v1/private/').subscribe({ error: () => undefined });
    http.expectOne('/api/v1/private/').flush(
      { error: { code: 'session_expired', message: 'Expired.', details: null, request_id: 'r' } },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(service.user()).toBeNull();
  });
});
