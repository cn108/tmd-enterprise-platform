import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

/** Base path for the versioned API. Served through the dev-server proxy locally. */
export const API_BASE_URL = '/api/v1';

export interface Readiness {
  status: string;
  checks?: Record<string, string>;
}

@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly http = inject(HttpClient);

  /** Readiness includes dependency checks, so it is the honest "is it usable" probe. */
  check(): Observable<Readiness> {
    return this.http.get<Readiness>(`${API_BASE_URL}/health/ready/`);
  }
}
