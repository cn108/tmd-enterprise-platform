import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { Subject, debounceTime } from 'rxjs';

import { apiErrorMessage } from '../../core/auth.models';
import { AuthService } from '../../core/auth.service';
import { AccessRestrictedComponent } from '../../shared/access-restricted/access-restricted.component';
import { ConfirmDialogComponent, ConfirmResult } from './confirm-dialog.component';
import { RecordDetailComponent } from './record-detail.component';
import { RecordFormComponent, RecordFormData } from './record-form.component';
import { ResourceApi } from './resource-api.service';
import {
  ActionConfig,
  ColumnConfig,
  MODULES,
  ModuleKey,
  Row,
  ResourceConfig,
  columnText,
  formatValue,
} from './workspace-config';

@Component({
  selector: 'app-workspace',
  imports: [
    AccessRestrictedComponent,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatPaginatorModule,
    MatProgressBarModule,
    MatSelectModule,
  ],
  templateUrl: './workspace.component.html',
  styleUrl: './workspace.scss',
})
export class WorkspaceComponent {
  private readonly api = inject(ResourceApi);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly route = inject(ActivatedRoute);

  private readonly key = this.route.snapshot.data['module'] as ModuleKey;
  private readonly search$ = new Subject<void>();

  private readonly query = this.route.snapshot.queryParamMap;
  private readonly requestedTab =
    this.query.get('tab') ?? (this.route.snapshot.data['tab'] as string | undefined);
  protected readonly config = MODULES[this.key];
  protected readonly activeTab = signal(
    this.config.tabs.some((tab) => tab.id === this.requestedTab)
      ? this.requestedTab!
      : this.config.tabs[0].id,
  );
  protected readonly rows = signal<Row[]>([]);
  protected readonly count = signal(0);
  protected readonly loading = signal(true);
  protected readonly accessDenied = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly search = signal('');
  protected readonly sortKey = signal<string | null>(null);
  protected readonly sortDir = signal<'asc' | 'desc'>('asc');
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(25);
  protected readonly busy = signal(false);
  protected readonly filterValues = signal<Record<string, string>>(
    Object.fromEntries(
      this.config.tabs
        .find((tab) => tab.id === this.activeTab())
        ?.filters?.map((filter) => [filter.key, this.query.get(filter.key) ?? ''])
        .filter(([, value]) => value) ?? [],
    ),
  );
  private readonly requestedRecord = this.query.get('record');
  private deepLinkHandled = false;

  protected readonly resource = computed<ResourceConfig>(
    () => this.config.tabs.find((tab) => tab.id === this.activeTab()) ?? this.config.tabs[0],
  );

  protected readonly permissions = computed(() => this.auth.user()?.permissions ?? []);

  /** Admits the module only when the user holds at least one of its view permissions. */
  protected readonly moduleViewDenied = computed(() => {
    const required = this.config.viewPermissions;
    return Boolean(
      required?.length && !required.some((permission) => this.permissions().includes(permission)),
    );
  });

  /** Server ordering is only sent where the endpoint supports `ordering`. */
  private readonly ordering = computed<string | undefined>(() => {
    if (this.resource().serverSort === false) {
      return undefined;
    }
    const key = this.sortKey();
    if (!key) {
      return undefined;
    }
    return this.sortDir() === 'asc' ? key : `-${key}`;
  });

  /** Actions the signed-in user may not perform, shown once rather than as dead buttons. */
  protected readonly blockedActions = computed(() =>
    (this.resource().actions ?? []).filter((action) => !this.allowed(action.permission)),
  );

  protected readonly hasWriteControls = computed(() => {
    const resource = this.resource();
    return Boolean(
      resource.create ||
        resource.edit ||
        resource.deactivate ||
        (resource.actions ?? []).length,
    );
  });

  protected readonly canPerformAnyWrite = computed(() => {
    const resource = this.resource();
    return Boolean(
      (resource.create && this.allowed(resource.permission)) ||
        (resource.edit &&
          this.allowed(resource.editPermission ?? resource.permission)) ||
        (resource.deactivate && this.allowed(resource.editPermission ?? resource.permission)) ||
        (resource.actions ?? []).some((action) => this.allowed(action.permission)),
    );
  });

  protected readonly hasRestrictedWrite = computed(() => {
    const resource = this.resource();
    return Boolean(
      (resource.create && !this.allowed(resource.permission)) ||
        (resource.edit &&
          !this.allowed(resource.editPermission ?? resource.permission)) ||
        this.blockedActions().length > 0,
    );
  });

  protected readonly accessLabel = computed<string | null>(() => {
    if (!this.hasWriteControls()) {
      return null;
    }
    if (!this.canPerformAnyWrite()) {
      return 'View only';
    }
    return this.hasRestrictedWrite() ? 'Limited actions' : null;
  });

  protected readonly accessTooltip = computed(() => {
    if (this.accessLabel() === 'View only') {
      return 'You can view this section. Changes are restricted to authorised personnel.';
    }
    return 'Some actions in this section are restricted for your account.';
  });

  protected readonly createTooltip = computed(
    () => `You do not have permission to create ${this.resource().label.toLowerCase()}.`,
  );

  constructor() {
    this.search$
      .pipe(debounceTime(300), takeUntilDestroyed())
      .subscribe(() => {
        if (this.resource().serverSearch) {
          this.pageIndex.set(0);
          this.load();
        }
      });
    if (this.moduleViewDenied()) {
      this.loading.set(false);
      this.accessDenied.set(true);
      return;
    }
    this.load();
  }

  protected allowed(permission?: string): boolean {
    if (!permission) {
      return true;
    }
    return this.permissions().includes(permission);
  }

  protected selectTab(id: string): void {
    if (this.moduleViewDenied()) {
      return;
    }
    if (id === this.activeTab()) {
      return;
    }
    this.activeTab.set(id);
    this.search.set('');
    this.sortKey.set(null);
    this.filterValues.set({});
    this.pageIndex.set(0);
    this.notice.set(null);
    this.accessDenied.set(false);
    this.deepLinkHandled = true;
    this.load();
  }

  protected onSearch(value: string): void {
    this.search.set(value);
    this.search$.next();
  }

  protected onPage(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.load();
  }

  protected setFilter(key: string, value: string): void {
    this.filterValues.update((current) => ({ ...current, [key]: value }));
    this.pageIndex.set(0);
    this.load();
  }

  protected sortBy(column: ColumnConfig): void {
    if (this.resource().serverSort === false) {
      return;
    }
    if (this.sortKey() === column.key) {
      this.sortDir.set(this.sortDir() === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortKey.set(column.key);
      this.sortDir.set('asc');
    }
    this.pageIndex.set(0);
    this.load();
  }

  protected ariaSort(column: ColumnConfig): 'ascending' | 'descending' | 'none' {
    if (this.sortKey() !== column.key) {
      return 'none';
    }
    return this.sortDir() === 'asc' ? 'ascending' : 'descending';
  }

  protected reload(): void {
    this.load();
  }

  protected clearSearch(): void {
    this.search.set('');
    this.pageIndex.set(0);
    this.load();
  }

  protected cell(row: Row, column: ColumnConfig): string {
    return columnText(row, column);
  }

  protected create(): void {
    const resource = this.resource();
    if (!resource.create || !this.allowed(resource.permission)) {
      return;
    }
    this.openForm({ resource });
  }

  protected edit(row: Row): void {
    const resource = this.resource();
    if (
      !resource.edit ||
      !this.canEdit(row) ||
      !this.allowed(resource.editPermission ?? resource.permission)
    ) {
      return;
    }
    this.openForm({ resource, row });
  }

  protected canEdit(row: Row): boolean {
    const statuses = this.resource().editableStatuses;
    if (!statuses) {
      return true;
    }
    return typeof row['status'] === 'string' && statuses.includes(row['status']);
  }

  protected view(row: Row): void {
    if (this.resource().detailFromRow) {
      this.openDetail(row);
      return;
    }
    const id = row['id'];
    if (typeof id !== 'number') {
      this.openDetail(row);
      return;
    }
    this.api.detail(this.resource().endpoint, id).subscribe({
      next: (record) => this.openDetail(record),
      error: (error: unknown) => this.error.set(apiErrorMessage(error)),
    });
  }

  protected download(row: Row): void {
    const direct = row['download_path'];
    if (typeof direct === 'string' && direct) {
      window.open(direct, '_blank', 'noopener');
      return;
    }
    const path = this.resource().downloadPath;
    const id = row['id'];
    if (!path || typeof id !== 'number') {
      return;
    }
    window.open(`${this.resource().endpoint}${id}/${path}/`, '_blank', 'noopener');
  }

  protected preview(row: Row): void {
    const path = this.resource().previewPath;
    const id = row['id'];
    if (!path || typeof id !== 'number') {
      return;
    }
    window.open(`${this.resource().endpoint}${id}/${path}/`, '_blank', 'noopener');
  }

  protected deactivate(row: Row): void {
    const resource = this.resource();
    const id = row['id'];
    if (
      !resource.deactivate ||
      typeof id !== 'number' ||
      !this.allowed(resource.editPermission ?? resource.permission)
    ) {
      return;
    }
    const label = formatValue(row['code'] ?? row['number'] ?? id);
    this.confirm({
      title: `Deactivate ${resource.singular}`,
      message: `${label} will be marked inactive. Existing documents keep their reference; records are never deleted.`,
      confirmLabel: 'Deactivate',
    }).subscribe((result) => {
      if (!result) {
        return;
      }
      this.busy.set(true);
      this.api.update(resource.endpoint, id, { is_active: false }).subscribe({
        next: () => {
          this.busy.set(false);
          this.notice.set(`${label} deactivated.`);
          this.load();
        },
        error: (error: unknown) => {
          this.busy.set(false);
          this.error.set(apiErrorMessage(error));
        },
      });
    });
  }

  protected runAction(row: Row, action: ActionConfig): void {
    if (!this.allowed(action.permission)) {
      return;
    }
    const id = row['id'];
    if (typeof id !== 'number') {
      return;
    }
    if (action.fields || action.lines) {
      this.dialog
        .open<RecordFormComponent, RecordFormData, Row | null>(RecordFormComponent, {
          data: {
            resource: this.resource(),
            row,
            action: {
              path: action.path,
              label: action.label,
              fields: action.fields ?? [],
              lines: action.lines,
            },
          },
          width: '56rem',
          maxWidth: '95vw',
          autoFocus: 'first-tabbable',
          disableClose: true,
        })
        .afterClosed()
        .subscribe((saved) => {
          if (!saved) {
            return;
          }
          this.notice.set(action.success);
          this.load();
        });
      return;
    }
    this.confirm({
      title: action.label,
      message: action.confirm,
      confirmLabel: action.label,
      reason: action.reason,
    }).subscribe((result) => {
      if (!result) {
        return;
      }
      const body = action.reason
        ? { [action.reason.key ?? 'reason']: result.reason }
        : {};
      this.busy.set(true);
      this.api.action(this.resource().endpoint, id, action.path, body).subscribe({
        next: (response) => {
          this.busy.set(false);
          const recorded = response['approvals_recorded'];
          const required = response['approvals_required'];
          if (
            typeof recorded === 'number' &&
            typeof required === 'number' &&
            recorded < required
          ) {
            this.notice.set(
              `Approval recorded (${recorded} of ${required}). Another independent approver is required.`,
            );
          } else {
            this.notice.set(action.success);
          }
          this.load();
        },
        error: (error: unknown) => {
          this.busy.set(false);
          this.error.set(apiErrorMessage(error));
        },
      });
    });
  }

  protected actionsFor(row: Row): ActionConfig[] {
    const status = row['status'];
    return (this.resource().actions ?? []).filter(
      (action) =>
        this.allowed(action.permission) &&
        (action.statuses === undefined ||
          (typeof status === 'string' && action.statuses.includes(status))),
    );
  }

  protected hasActions(): boolean {
    return (this.resource().actions ?? []).some((action) => this.allowed(action.permission));
  }

  private load(): void {
    const resource = this.resource();
    this.loading.set(true);
    this.error.set(null);
    this.accessDenied.set(false);
    this.api
      .list(resource.endpoint, {
        page: this.pageIndex() + 1,
        pageSize: this.pageSize(),
        search: resource.serverSearch ? this.search() : '',
        ordering: this.ordering(),
        filters: this.filterValues(),
      })
      .subscribe({
        next: (page) => {
          this.rows.set(page.rows);
          this.count.set(page.count);
          this.loading.set(false);
          this.openRequestedRecord();
        },
        error: (error: unknown) => {
          this.rows.set([]);
          this.count.set(0);
          this.loading.set(false);
          if (error instanceof HttpErrorResponse && error.status === 403) {
            this.accessDenied.set(true);
            return;
          }
          this.error.set(apiErrorMessage(error));
        },
      });
  }

  /** Applies dashboard deep links once: create dialog, record detail or list filter. */
  private openRequestedRecord(): void {
    if (this.deepLinkHandled) {
      return;
    }
    this.deepLinkHandled = true;
    if (this.query.get('new') === '1' && this.resource().create) {
      if (this.allowed(this.resource().permission)) {
        this.openForm({ resource: this.resource() });
      }
      return;
    }
    if (!this.requestedRecord) {
      return;
    }
    const id = Number(this.requestedRecord);
    if (!Number.isInteger(id) || id <= 0) {
      return;
    }
    this.api.detail(this.resource().endpoint, id).subscribe({
      next: (record) => this.openDetail(record),
      error: (error: unknown) => this.error.set(apiErrorMessage(error)),
    });
  }

  private openForm(data: RecordFormData): void {
    this.dialog
      .open<RecordFormComponent, RecordFormData, Row | null>(RecordFormComponent, {
        data,
        width: '56rem',
        maxWidth: '95vw',
        autoFocus: 'first-tabbable',
        // Cancel and Escape go through the form's own unsaved-changes check.
        disableClose: true,
      })
      .afterClosed()
      .subscribe((saved) => {
        if (!saved) {
          return;
        }
        const action = data.row ? 'updated' : 'created';
        this.notice.set(`${data.resource.singular} ${action}.`);
        this.load();
      });
  }

  private openDetail(row: Row): void {
    this.dialog.open<RecordDetailComponent, { resource: ResourceConfig; row: Row }>(
      RecordDetailComponent,
      { data: { resource: this.resource(), row }, maxWidth: '95vw' },
    );
  }

  private confirm(data: {
    title: string;
    message: string;
    confirmLabel: string;
    reason?: { label: string; required: boolean };
  }) {
    return this.dialog
      .open<ConfirmDialogComponent, typeof data, ConfirmResult | null>(ConfirmDialogComponent, {
        data,
        maxWidth: '95vw',
      })
      .afterClosed();
  }
}
