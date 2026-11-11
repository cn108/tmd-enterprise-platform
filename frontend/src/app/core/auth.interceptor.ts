import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { ApiErrorBody } from './auth.models';
import { SessionStore } from './session.store';

/**
 * Sends cookies with API calls and clears the local session when the backend
 * says the session is gone. It does not redirect: routing decisions belong to
 * the guard, which avoids redirect loops on background requests.
 */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const session = inject(SessionStore);
  const withCredentials = request.clone({ withCredentials: true });

  return next(withCredentials).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        const code = (error.error as ApiErrorBody | null)?.error?.code;
        if (code === 'not_authenticated' || code === 'session_expired') {
          session.setAnonymous();
        }
      }
      return throwError(() => error);
    }),
  );
};
