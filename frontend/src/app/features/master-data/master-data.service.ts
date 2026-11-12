import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { isRow, normalizeRows } from '../workspace/resource-api.service';
import { Row } from '../workspace/workspace-config';

export interface MasterQuery {
  page: number;
  pageSize: number;
  search?: string;
  sort?: string | null;
  order?: 'asc' | 'desc';
  filters?: Record<string, string>;
}

export interface MasterPage {
  rows: Row[];
  count: number;
}

@Injectable({ providedIn: 'root' })
export class MasterDataApi {
  private readonly http = inject(HttpClient);

  list(endpoint: string, query: MasterQuery): Observable<MasterPage> {
    let params = new HttpParams()
      .set('page', String(query.page))
      .set('pageSize', String(query.pageSize));
    if (query.search?.trim()) {
      params = params.set('search', query.search.trim());
    }
    if (query.sort) {
      params = params.set('sort', query.sort).set('order', query.order ?? 'asc');
    }
    for (const [key, value] of Object.entries(query.filters ?? {})) {
      if (value) {
        params = params.set(key, value);
      }
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
}