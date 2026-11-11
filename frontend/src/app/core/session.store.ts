import { Injectable, signal } from '@angular/core';

import { AuthenticatedUser } from './auth.models';

/**
 * Session state only. It deliberately has no `HttpClient` dependency so the
 * interceptor can clear a dead session without creating a DI cycle
 * (interceptor -> auth service -> HttpClient -> interceptor).
 */
@Injectable({ providedIn: 'root' })
export class SessionStore {
  private readonly userSignal = signal<AuthenticatedUser | null>(null);
  private readonly resolvedSignal = signal(false);

  readonly user = this.userSignal.asReadonly();
  readonly resolved = this.resolvedSignal.asReadonly();

  setUser(user: AuthenticatedUser): void {
    this.userSignal.set(user);
    this.resolvedSignal.set(true);
  }

  setAnonymous(): void {
    this.userSignal.set(null);
    this.resolvedSignal.set(true);
  }
}
