import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, firstValueFrom, of, tap, throwError } from 'rxjs';

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

  /**
   * Ends the server session, then clears local state.
   *
   * Local state is cleared only when the server confirms the session ended, or
   * when it reports the session was already gone. Any other failure keeps the
   * user signed in and is rethrown: telling someone they signed out while the
   * session is still live on the server is a security-relevant lie.
   */
  logout(): Observable<void> {
    return this.http.post<void>(`${AUTH_BASE}/logout/`, {}).pipe(
      tap(() => this.session.setAnonymous()),
      catchError((error: unknown) => {
        if (error instanceof HttpErrorResponse && error.status === 401) {
          this.session.setAnonymous();
          return of(void 0);
        }
        return throwError(() => error);
      }),
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
