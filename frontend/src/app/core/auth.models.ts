import { HttpErrorResponse } from '@angular/common/http';

/** Shape returned by `GET /api/v1/auth/me/` and `POST /api/v1/auth/login/`. */
export interface AuthenticatedUser {
  id: number;
  email: string;
  full_name: string;
  employee_ref: string;
  department: string | null;
  must_change_password: boolean;
  mfa_required: boolean;
  roles: string[];
  permissions: string[];
}

export interface MfaChallenge {
  token: string;
  purpose: 'verify' | 'enroll';
}

export interface MfaSetup {
  secret: string;
  otpauth_uri: string;
  recovery_codes: string[];
}

/** The backend's single error envelope (see `backend/shared/exceptions.py`). */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: unknown;
    request_id: string;
  };
}

/**
 * Turns an HTTP failure into something a person can act on.
 * Server messages are shown as-is because they are written for users and
 * deliberately do not reveal whether an account exists.
 */
export function apiErrorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const body = error.error as ApiErrorBody | null;
    if (body?.error?.message) {
      return body.error.message;
    }
    if (error.status === 0) {
      return 'The server could not be reached. Check your connection and try again.';
    }
  }
  return 'Something went wrong. Try again, or contact your administrator.';
}

/** Read the backend's MFA challenge without trusting any other error detail. */
export function mfaChallenge(error: unknown): MfaChallenge | null {
  if (!(error instanceof HttpErrorResponse)) {
    return null;
  }
  const body = error.error as ApiErrorBody | null;
  const code = body?.error?.code;
  const details = body?.error?.details as { challenge_token?: unknown } | null;
  if (
    (code !== 'mfa_required' && code !== 'mfa_enrollment_required') ||
    typeof details?.challenge_token !== 'string'
  ) {
    return null;
  }
  return {
    token: details.challenge_token,
    purpose: code === 'mfa_enrollment_required' ? 'enroll' : 'verify',
  };
}
