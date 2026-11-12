import { Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

import { Row, ResourceConfig, formatValue } from './workspace-config';

export interface RecordDetailData {
  resource: ResourceConfig;
  row: Row;
}

@Component({
  selector: 'app-record-detail',
  imports: [MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>{{ heading() }}</h2>
    <mat-dialog-content>
      <dl class="detail">
        @for (field of data.resource.detail; track field.key) {
          <div class="detail__item">
            <dt>{{ field.label }}</dt>
            <dd>{{ value(field.key) }}</dd>
          </div>
        }
      </dl>

      @if (data.resource.detailLines; as columns) {
        @if (lines().length > 0) {
          <h3 class="detail__heading">Lines</h3>
          <div class="detail__table">
            <table>
              <thead>
                <tr>
                  @for (column of columns; track column.key) {
                    <th scope="col">{{ column.label }}</th>
                  }
                </tr>
              </thead>
              <tbody>
                @for (line of lines(); track $index) {
                  <tr>
                    @for (column of columns; track column.key) {
                      <td>{{ lineValue(line, column.key) }}</td>
                    }
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-flat-button type="button" mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: `
    .detail {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
      gap: 0.85rem 1.5rem;
      margin: 0;
      min-width: min(40rem, 76vw);
    }

    .detail__item dt {
      color: var(--tmd-muted);
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .detail__item dd {
      margin: 0.15rem 0 0;
      color: var(--tmd-ink);
      overflow-wrap: anywhere;
    }

    .detail__heading {
      margin: 1.5rem 0 0.5rem;
      font-size: 0.95rem;
      color: var(--tmd-navy-soft);
    }

    .detail__table {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }

    th,
    td {
      padding: 0.45rem 0.5rem;
      border-bottom: 1px solid var(--tmd-line);
      text-align: left;
      white-space: nowrap;
    }

    th {
      color: var(--tmd-muted);
      font-size: 0.72rem;
      text-transform: uppercase;
    }
  `,
})
export class RecordDetailComponent {
  protected readonly data: RecordDetailData;

  constructor() {
    this.data = inject<RecordDetailData>(MAT_DIALOG_DATA);
  }

  protected heading(): string {
    const row = this.data.row;
    const label = row['number'] ?? row['code'] ?? row['name'] ?? row['id'];
    return `${label} · ${this.data.resource.singular}`;
  }

  protected value(key: string): string {
    const field = this.data.resource.detail?.find((item) => item.key === key);
    return formatValue(this.data.row[key], field?.kind);
  }

  protected lines(): Row[] {
    const value = this.data.row['lines'];
    if (!Array.isArray(value)) {
      return [];
    }
    return value.filter(
      (line): line is Row => typeof line === 'object' && line !== null && !Array.isArray(line),
    );
  }

  protected lineValue(line: Row, key: string): string {
    const field = this.data.resource.detailLines?.find((item) => item.key === key);
    return formatValue(line[key], field?.kind);
  }
}
