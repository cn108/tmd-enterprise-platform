import { HttpErrorResponse } from '@angular/common/http';
import { NgTemplateOutlet } from '@angular/common';
import { A11yModule } from '@angular/cdk/a11y';
import { ScrollingModule } from '@angular/cdk/scrolling';
import { Component, ElementRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { Subject, debounceTime, forkJoin } from 'rxjs';

import { apiErrorMessage } from '../../core/auth.models';
import { AuthService } from '../../core/auth.service';
import { ConfirmDialogComponent, ConfirmResult } from '../workspace/confirm-dialog.component';
import { ResourceApi, fieldErrors } from '../workspace/resource-api.service';
import {
  ColumnConfig,
  FieldConfig,
  Row,
  SelectOption,
  columnText,
  formatValue,
  initialValue,
} from '../workspace/workspace-config';
import {
  ENTITY_ORDER,
  EntityKey,
  MASTER_ENTITIES,
  MasterColumn,
} from './master-data.config';
import { MasterDataApi } from './master-data.service';

type PanelMode = 'view' | 'create' | 'edit';

@Component({
  selector: 'app-master-data',
  imports: [A11yModule, NgTemplateOutlet, ReactiveFormsModule, RouterLink, ScrollingModule],
  templateUrl: './master-data.component.html',
  styleUrl: './master-data.component.scss',
})
export class MasterDataComponent {
  private readonly api = inject(MasterDataApi);
  private readonly resources = inject(ResourceApi);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly route = inject(ActivatedRoute);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly search$ = new Subject<string>();

  protected readonly entityKey = this.route.snapshot.data['entity'] as EntityKey;
  protected readonly entity = MASTER_ENTITIES[this.entityKey];
  protected readonly entities = ENTITY_ORDER.map((key) => MASTER_ENTITIES[key]);

  protected readonly rows = signal<Row[]>([]);
  protected readonly count = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly search = signal('');
  protected readonly sortKey = signal<string | null>('updated_at');
  protected readonly sortDir = signal<'asc' | 'desc'>('desc');
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(25);
  protected readonly filterValues = signal<Record<string, string>>({});
  protected readonly selected = signal<Set<number>>(new Set());
  protected readonly announce = signal('');

  protected readonly panelOpen = signal(false);
  protected readonly panelMode = signal<PanelMode>('view');
  protected readonly selectedRow = signal<Row | null>(null);
  protected readonly panelError = signal<string | null>(null);
  protected readonly panelSaving = signal(false);
  protected readonly options = signal<Record<string, SelectOption[]>>({});
  protected readonly form = new FormGroup<Record<string, AbstractControl>>({});
  private returnFocus: HTMLElement | null = null;

  protected readonly permissions = computed(() => this.auth.user()?.permissions ?? []);
  protected readonly canCreate = computed(() =>
    this.allowed(this.entity.createPermission ?? this.entity.resource.permission),
  );
  protected readonly canEdit = computed(() =>
    this.allowed(this.entity.editPermission ?? this.entity.resource.editPermission ?? this.entity.resource.permission),
  );
  protected readonly totalPages = computed(() =>
    Math.max(1, Math.ceil(this.count() / this.pageSize())),
  );
  protected readonly showingFrom = computed(() =>
    this.count() === 0 ? 0 : this.pageIndex() * this.pageSize() + 1,
  );
  protected readonly showingTo = computed(() =>
    Math.min(this.count(), (this.pageIndex() + 1) * this.pageSize()),
  );
  protected readonly pageNumbers = computed(() => {
    const total = this.totalPages();
    const current = this.pageIndex();
    const start = Math.max(0, Math.min(current - 2, total - 5));
    return Array.from({ length: Math.min(5, total) }, (_, index) => start + index);
  });
  protected readonly selectedCount = computed(() => this.selected().size);
  protected readonly allSelected = computed(
    () => this.rows().length > 0 && this.rows().every((row) => this.isSelected(row)),
  );
  protected readonly someSelected = computed(
    () => this.rows().some((row) => this.isSelected(row)) && !this.allSelected(),
  );
  protected readonly activeFilters = computed(() =>
    Object.entries(this.filterValues()).flatMap(([key, value]) => {
      const filter = this.entity.filters.find((item) => item.key === key);
      const option = filter?.options.find((item) => String(item.value) === value);
      return filter && value
        ? [{ key, value, label: filter.label, text: option?.label ?? value }]
        : [];
    }),
  );
  protected readonly lastUpdated = computed(() => {
    const dates = this.rows()
      .map((row) => row['updated_at'])
      .filter((value): value is string => typeof value === 'string');
    if (dates.length === 0) {
      return null;
    }
    return dates.sort().at(-1) ?? null;
  });

  constructor() {
    this.search$
      .pipe(debounceTime(300), takeUntilDestroyed())
      .subscribe((value) => {
        this.search.set(value);
        this.pageIndex.set(0);
        this.load();
      });
    this.load();
  }

  protected allowed(permission?: string): boolean {
    return !permission || this.permissions().includes(permission);
  }

  protected onSearch(value: string): void {
    this.search$.next(value);
  }

  protected setFilter(key: string, event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.filterValues.update((current) => {
      const next = { ...current };
      if (value) {
        next[key] = value;
      } else {
        delete next[key];
      }
      return next;
    });
    this.pageIndex.set(0);
    this.load();
  }

  protected removeFilter(key: string): void {
    this.filterValues.update((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    this.pageIndex.set(0);
    this.load();
  }

  protected clearAll(): void {
    this.filterValues.set({});
    this.pageIndex.set(0);
    this.load();
  }

  protected filterValue(key: string): string {
    return this.filterValues()[key] ?? '';
  }

  protected sortBy(column: MasterColumn): void {
    if (!column.sortable) {
      return;
    }
    const key = column.sortKey ?? column.key;
    if (this.sortKey() === key) {
      this.sortDir.set(this.sortDir() === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortKey.set(key);
      this.sortDir.set('asc');
    }
    this.pageIndex.set(0);
    this.announce.set(`Sorted by ${column.label} ${this.sortDir() === 'asc' ? 'ascending' : 'descending'}`);
    this.load();
  }

  protected ariaSort(column: MasterColumn): 'ascending' | 'descending' | 'none' {
    if (this.sortKey() !== (column.sortKey ?? column.key)) {
      return 'none';
    }
    return this.sortDir() === 'asc' ? 'ascending' : 'descending';
  }

  protected onPageSize(event: Event): void {
    this.pageSize.set(Number((event.target as HTMLSelectElement).value));
    this.pageIndex.set(0);
    this.load();
  }

  protected goToPage(index: number): void {
    if (index < 0 || index >= this.totalPages() || index === this.pageIndex()) {
      return;
    }
    this.pageIndex.set(index);
    this.load();
  }

  protected jumpToPage(event: Event): void {
    const input = event.target as HTMLInputElement;
    const page = Number(input.value);
    if (Number.isInteger(page) && page >= 1 && page <= this.totalPages()) {
      this.goToPage(page - 1);
    }
    input.value = '';
  }

  protected cell(row: Row, column: ColumnConfig): string {
    if (column.key === 'is_active') {
      return row['is_active'] === true ? 'Active' : 'Inactive';
    }
    if (column.key === 'tax_type') {
      return formatValue(row['tax_type'], 'status');
    }
    if (column.key === 'rate' && row['rate'] !== null && row['rate'] !== undefined) {
      const numeric = Number(row['rate']);
      return Number.isFinite(numeric) ? `${numeric.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')}%` : '—';
    }
    return columnText(row, column);
  }

  protected statusTone(column: ColumnConfig, row: Row): string {
    const value = String(row[column.key] ?? '').toLowerCase();
    if (column.key === 'is_active') {
      return value === 'true' ? 'success' : 'neutral';
    }
    if (value === 'reviewed' || value === 'product') {
      return 'success';
    }
    if (value === 'provisional' || value === 'service') {
      return 'warning';
    }
    if (value === 'rejected') {
      return 'danger';
    }
    return 'info';
  }

  protected isSelected(row: Row): boolean {
    const id = row['id'];
    return typeof id === 'number' && this.selected().has(id);
  }

  protected toggleRow(row: Row, event: Event): void {
    event.stopPropagation();
    const id = row['id'];
    if (typeof id !== 'number') {
      return;
    }
    this.selected.update((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  protected toggleAll(event: Event): void {
    event.stopPropagation();
    if (this.allSelected()) {
      this.selected.set(new Set());
      return;
    }
    this.selected.set(
      new Set(
        this.rows()
          .map((row) => row['id'])
          .filter((id): id is number => typeof id === 'number'),
      ),
    );
  }

  protected clearSelection(): void {
    this.selected.set(new Set());
  }

  protected openView(row: Row, event?: Event): void {
    this.returnFocus = (event?.currentTarget as HTMLElement | undefined) ?? null;
    this.panelMode.set('view');
    this.selectedRow.set(row);
    this.panelError.set(null);
    this.panelOpen.set(true);
    const id = row['id'];
    if (typeof id === 'number') {
      this.resources.detail(this.entity.endpoint, id).subscribe({
        next: (record) => this.selectedRow.set(record),
        error: (error: unknown) => this.panelError.set(apiErrorMessage(error)),
      });
    }
  }

  protected openCreate(event?: Event): void {
    if (!this.canCreate()) {
      return;
    }
    this.returnFocus = (event?.currentTarget as HTMLElement | undefined) ?? null;
    this.panelMode.set('create');
    this.selectedRow.set(null);
    this.panelError.set(null);
    this.buildForm();
    this.panelOpen.set(true);
    this.focusFirstField();
  }

  protected openEdit(event?: Event): void {
    const row = this.selectedRow();
    if (!row || !this.canEdit() || !this.editable(row)) {
      return;
    }
    this.returnFocus = (event?.currentTarget as HTMLElement | undefined) ?? null;
    this.panelMode.set('edit');
    this.panelError.set(null);
    this.buildForm(row);
    this.focusFirstField();
  }

  protected editable(row: Row): boolean {
    return !(this.entity.key === 'tax-rates' && row['review_status'] === 'reviewed');
  }

  protected closePanel(): void {
    this.panelOpen.set(false);
    this.selectedRow.set(null);
    this.panelMode.set('view');
    const target = this.returnFocus;
    this.returnFocus = null;
    setTimeout(() => target?.focus(), 0);
  }

  protected save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.panelSaving.set(true);
    this.panelError.set(null);
    const body = this.form.getRawValue();
    const row = this.selectedRow();
    const request =
      this.panelMode() === 'create'
        ? this.resources.create(this.entity.endpoint, body)
        : this.resources.update(this.entity.endpoint, row?.['id'] as number, body);
    request.subscribe({
      next: () => {
        this.panelSaving.set(false);
        this.notice.set(`${this.entity.singular} ${this.panelMode() === 'create' ? 'created' : 'updated'}.`);
        this.closePanel();
        this.load();
      },
      error: (error: unknown) => {
        this.panelSaving.set(false);
        const messages = fieldErrors(error);
        this.panelError.set(messages.summary);
        for (const [key, message] of Object.entries(messages.fields)) {
          this.form.get(key)?.setErrors({ server: message });
        }
      },
    });
  }

  protected fieldError(field: FieldConfig): string | null {
    const control = this.form.get(field.key);
    if (!control?.touched) {
      return null;
    }
    if (control.hasError('server')) {
      return control.getError('server') as string;
    }
    if (control.hasError('required')) {
      return `${field.label} is required.`;
    }
    if (control.hasError('min')) {
      return `${field.label} is too low.`;
    }
    return null;
  }

  protected optionList(field: FieldConfig): SelectOption[] {
    return field.options ?? this.options()[field.key] ?? [];
  }

  protected deactivate(row: Row, event?: Event): void {
    event?.stopPropagation();
    const id = row['id'];
    if (!this.entity.canDeactivate || typeof id !== 'number' || !this.canEdit()) {
      return;
    }
    this.confirmDeactivate(1, row['code'] ?? row['name'] ?? id).subscribe((result) => {
      if (!result) {
        return;
      }
      this.resources.update(this.entity.endpoint, id, { is_active: false }).subscribe({
        next: () => {
          this.notice.set(`${this.entity.singular} deactivated.`);
          this.closePanel();
          this.load();
        },
        error: (error: unknown) => this.error.set(apiErrorMessage(error)),
      });
    });
  }

  protected bulkDeactivate(): void {
    const ids = [...this.selected()];
    if (!this.entity.canDeactivate || ids.length === 0 || !this.canEdit()) {
      return;
    }
    this.confirmDeactivate(ids.length).subscribe((result) => {
      if (!result) {
        return;
      }
      forkJoin(
        ids.map((id) => this.resources.update(this.entity.endpoint, id, { is_active: false })),
      ).subscribe({
        next: () => {
          this.notice.set(`${ids.length} ${ids.length === 1 ? 'record' : 'records'} deactivated.`);
          this.selected.set(new Set());
          this.load();
        },
        error: (error: unknown) => this.error.set(apiErrorMessage(error)),
      });
    });
  }

  protected exportCsv(selectedOnly = false): void {
    const rows = selectedOnly
      ? this.rows().filter((row) => this.isSelected(row))
      : this.rows();
    if (rows.length === 0) {
      return;
    }
    const columns = this.entity.columns;
    const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
    const lines = [
      columns.map((column) => escape(column.label)).join(','),
      ...rows.map((row) => columns.map((column) => escape(this.cell(row, column))).join(',')),
    ];
    const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${this.entity.key}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  protected trackRow(_index: number, row: Row): unknown {
    return row['id'];
  }

  protected recordLabel(row: Row | null): string {
    if (!row) {
      return '';
    }
    const label = row['legal_name'] ?? row['name'] ?? row['code'];
    return label === undefined || label === null ? `#${String(row['id'])}` : String(label);
  }

  protected detailValue(row: Row, column: ColumnConfig): string {
    if (column.key === 'rate') {
      return this.cell(row, column);
    }
    if (column.key === 'tax_type') {
      return formatValue(row['tax_type'], 'status');
    }
    return formatValue(row[column.key], column.kind);
  }

  protected displayValue(value: unknown, kind?: ColumnConfig['kind']): string {
    return formatValue(value, kind);
  }

  protected timestamp(value: unknown): string {
    if (typeof value !== 'string' || !value) {
      return '—';
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : new Intl.DateTimeFormat('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }).format(date);
  }

  protected onRowKey(event: KeyboardEvent, row: Row): void {
    const target = event.currentTarget as HTMLElement;
    if (event.key === 'Enter') {
      event.preventDefault();
      this.openView(row, event);
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      (target.nextElementSibling as HTMLElement | null)?.focus();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      (target.previousElementSibling as HTMLElement | null)?.focus();
    }
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .list(this.entity.endpoint, {
        page: this.pageIndex() + 1,
        pageSize: this.pageSize(),
        search: this.search(),
        sort: this.sortKey(),
        order: this.sortDir(),
        filters: this.filterValues(),
      })
      .subscribe({
        next: (page) => {
          this.rows.set(page.rows);
          this.count.set(page.count);
          this.loading.set(false);
          this.selected.set(new Set());
          this.announce.set(
            `${page.count} ${page.count === 1 ? 'record' : 'records'} found. Page ${this.pageIndex() + 1} of ${this.totalPages()}.`,
          );
        },
        error: (error: unknown) => {
          this.rows.set([]);
          this.count.set(0);
          this.loading.set(false);
          if (error instanceof HttpErrorResponse && error.status === 403) {
            this.error.set('You do not have permission to view these records.');
          } else {
            this.error.set(apiErrorMessage(error));
          }
        },
      });
  }

  private buildForm(row?: Row): void {
    Object.keys(this.form.controls).forEach((key) => this.form.removeControl(key));
    this.options.set({});
    for (const field of this.entity.fields) {
      const validators = field.required ? [Validators.required] : [];
      if (field.type === 'number' && field.min !== undefined) {
        validators.push(Validators.min(field.min));
      }
      const initial = initialValue(field, row);
      this.form.addControl(
        field.key,
        new FormControl(
          field.type === 'select' && initial !== null ? String(initial) : initial,
          { validators, nonNullable: false },
        ),
      );
      if (field.optionsEndpoint) {
        this.resources.options(field.optionsEndpoint, field.optionsQuery).subscribe({
          next: (options) => this.options.update((current) => ({ ...current, [field.key]: options })),
          error: () => this.options.update((current) => ({ ...current, [field.key]: [] })),
        });
      }
    }
  }

  private focusFirstField(): void {
    setTimeout(() => {
      this.host.nativeElement
        .querySelector<HTMLElement>(
          '.md-panel .md-field input:not([type="checkbox"]), .md-panel .md-field select, .md-panel .md-field textarea',
        )
        ?.focus();
    }, 0);
  }

  private confirmDeactivate(count: number, label?: unknown) {
    const subject = label
      ? `${String(label)} will be marked inactive.`
      : `${count} selected ${count === 1 ? 'record' : 'records'} will be marked inactive.`;
    return this.dialog
      .open<ConfirmDialogComponent, {
        title: string;
        message: string;
        confirmLabel: string;
      }, ConfirmResult | null>(ConfirmDialogComponent, {
        data: {
          title: `Deactivate ${count} ${count === 1 ? this.entity.singular : this.entity.label.toLowerCase()}`,
          message: `${subject} Existing documents keep their references; records are never deleted.`,
          confirmLabel: 'Deactivate',
        },
        autoFocus: 'first-tabbable',
      })
      .afterClosed();
  }
}