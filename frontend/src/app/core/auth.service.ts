import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, firstValueFrom, of, tap } from 'rxjs';

import { AuthenticatedUser } from './auth.models';
import { SessionStore } from './session.store';

const AUTH_BASE = '/api/v1/auth';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly session = inject(SessionStore);

  private bootstrapPromise: Promise<void> | null = null;

  readonly user = this.session.user;
  readonly resolved = this.session.resolved;

  isAuthenticated(): boolean {
    return this.session.user() !== null;
  }

  /**
   * Fetches the CSRF cookie and learns whether a session already exists.
   * Idempotent: the initializer and the route guard may both call it.
   */
  bootstrap(): Promise<void> {
    this.bootstrapPromise ??= this.runBootstrap();
    return this.bootstrapPromise;
  }

  login(email: string, password: string): Observable<AuthenticatedUser> {
    return this.http
      .post<AuthenticatedUser>(`${AUTH_BASE}/login/`, { email, password })
      .pipe(tap((user) => this.session.setUser(user)));
  }

  /** Clears local state even if the request fails (an expired session cannot be revoked again). */
  logout(): Observable<void> {
    return this.http.post<void>(`${AUTH_BASE}/logout/`, {}).pipe(
      catchError(() => of(void 0)),
      tap(() => this.session.setAnonymous()),
    );
  }

  private async runBootstrap(): Promise<void> {
    // Issuing a token first means the SPA can send X-CSRFToken on its first
    // mutation after signing in.
    await firstValueFrom(
      this.http.get<{ csrfToken: string }>(`${AUTH_BASE}/csrf/`).pipe(
        catchError(() => of({ csrfToken: '' })),
      ),
    );

    const user = await firstValueFrom(
      this.http
        .get<AuthenticatedUser>(`${AUTH_BASE}/me/`)
        .pipe(catchError(() => of(null))),
    );

    if (user) {
      this.session.setUser(user);
    } else {
      this.session.setAnonymous();
    }
  }
}
