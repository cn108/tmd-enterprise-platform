import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { apiErrorMessage } from '../../core/auth.models';
import { Row, SelectOption } from './workspace-config';

/** The backend's error envelope, narrowed to what a form needs. */
interface Envelope {
  error?: {
    message?: string;
    details?: unknown;
  };
}

export interface FieldErrors {
  /** Errors that belong to the form as a whole. */
  summary: string | null;
  /** Errors keyed by the API field name. */
  fields: Record<string, string>;
}

export interface ListQuery {
  /** One-based page number. */
  page: number;
  pageSize: number;
  search?: string;
  ordering?: string;
  /** Extra server filters, e.g. `{status: 'submitted'}` for a work queue. */
  filters?: Record<string, string>;
}

export interface PageResult {
  rows: Row[];
  /** Total matching records, not just the visible page. */
  count: number;
}

export function isRow(value: unknown): value is Row {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Accepts plain lists, `{rows: [...]}` reports, or DRF's `{results: [...]}`. */
export function normalizeRows(body: unknown): Row[] {
  if (Array.isArray(body)) {
    return body.filter(isRow);
  }
  if (isRow(body)) {
    for (const key of ['rows', 'results']) {
      const list = body[key];
      if (Array.isArray(list)) {
        return list.filter(isRow);
      }
    }
  }
  return [];
}

function flatten(detail: unknown, prefix = ''): Record<string, string> {
  if (typeof detail === 'string' || typeof detail === 'number') {
    return { [prefix || '_']: String(detail) };
  }
  if (Array.isArray(detail)) {
    const messages = detail.filter((item) => typeof item === 'string');
    if (messages.length > 0) {
      return { [prefix || '_']: messages.join(' ') };
    }
    const merged: Record<string, string> = {};
    detail.forEach((item, index) => {
      Object.assign(merged, flatten(item, prefix ? `${prefix}.${index}` : String(index)));
    });
    return merged;
  }
  if (isRow(detail)) {
    const merged: Record<string, string> = {};
    for (const [key, value] of Object.entries(detail)) {
      Object.assign(merged, flatten(value, prefix ? `${prefix}.${key}` : key));
    }
    return merged;
  }
  return {};
}

/**
 * Splits a failed response into per-field messages so a form can show the
 * server's own wording beside the control that caused it. The backend remains
 * the authority; this never replaces its message with a guess.
 */
export function fieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof HttpErrorResponse)) {
    return { summary: 'Something went wrong. Try again.', fields: {} };
  }
  const body = error.error as Envelope | null;
  const detail = body?.error?.details;
  const raw = flatten(detail);
  const fields: Record<string, string> = {};
  for (const [key, message] of Object.entries(raw)) {
    fields[key === '_' ? 'non_field_errors' : key] = message;
  }
  const summary = fields['non_field_errors'] ?? body?.error?.message ?? apiErrorMessage(error);
  return { summary, fields };
}

@Injectable({ providedIn: 'root' })
export class ResourceApi {
  private readonly http = inject(HttpClient);

  list(endpoint: string, query: ListQuery): Observable<PageResult> {
    let params = new HttpParams()
      .set('page', String(query.page))
      .set('page_size', String(query.pageSize));
    if (query.search?.trim()) {
      params = params.set('search', query.search.trim());
    }
    if (query.ordering) {
      params = params.set('ordering', query.ordering);
    }
    for (const [name, value] of Object.entries(query.filters ?? {})) {
      params = params.set(name, value);
    }
    return this.http.get<unknown>(endpoint, { params }).pipe(
      map((body) => {
        const rows = normalizeRows(body);
        const count =
          isRow(body) && typeof body['count'] === 'number' ? body['count'] : rows.length;
        return { rows, count };
      }),
    );
  }

  detail(endpoint: string, id: number): Observable<Row> {
    return this.http.get<Row>(`${endpoint}${id}/`);
  }

  create(endpoint: string, body: unknown): Observable<Row> {
    return this.http.post<Row>(endpoint, body);
  }

  update(endpoint: string, id: number, body: unknown): Observable<Row> {
    return this.http.patch<Row>(`${endpoint}${id}/`, body);
  }

  action(endpoint: string, id: number, path: string, body: unknown = {}): Observable<Row> {
    return this.http.post<Row>(`${endpoint}${id}/${path}/`, body);
  }

  /** Loads select choices from a coded list endpoint, bounded to one page. */
  options(endpoint: string, query: Record<string, string> = {}): Observable<SelectOption[]> {
    let params = new HttpParams().set('page_size', '100');
    for (const [name, value] of Object.entries(query)) {
      params = params.set(name, value);
    }
    return this.http.get<unknown>(endpoint, { params }).pipe(
      map((body) =>
        normalizeRows(body).map((row) => ({
          value: row['id'] as number,
          label: optionLabel(row),
        })),
      ),
    );
  }
}

function optionLabel(row: Row): string {
  if (typeof row['label'] === 'string' && row['label']) {
    return row['label'];
  }
  const code = typeof row['code'] === 'string' ? row['code'] : '';
  const number = typeof row['number'] === 'string' ? row['number'] : '';
  const name =
    (typeof row['name'] === 'string' && row['name']) ||
    (typeof row['legal_name'] === 'string' && row['legal_name']) ||
    (typeof row['title'] === 'string' && row['title']) ||
    (typeof row['description'] === 'string' && row['description']) ||
    '';
  const prefix = code || number;
  if (prefix && name) {
    return `${prefix} — ${name}`;
  }
  return prefix || name || `#${String(row['id'])}`;
}
