import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormArray,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { Observable, forkJoin } from 'rxjs';

import { apiErrorMessage } from '../../core/auth.models';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { ResourceApi, fieldErrors } from './resource-api.service';
import {
  FieldConfig,
  LineConfig,
  Row,
  ResourceConfig,
  SelectOption,
  initialValue,
} from './workspace-config';

export interface RecordFormData {
  resource: ResourceConfig;
  /** Present when editing an existing record. */
  row?: Row;
  /** Present when the dialog collects the payload for a workflow action. */
  action?: { path: string; label: string; fields: FieldConfig[]; lines?: LineConfig };
}

type LineGroup = FormGroup<Record<string, FormControl>>;

/**
 * Create/edit dialog driven by the resource configuration.
 *
 * Validation mirrors what the API serializer requires; the server still runs
 * every rule and its field errors are shown beside the offending control.
 */
@Component({
  selector: 'app-record-form',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
  ],
  templateUrl: './record-form.component.html',
  styleUrl: './record-form.component.scss',
})
export class RecordFormComponent implements OnInit {
  private readonly api = inject(ResourceApi);
  private readonly dialogRef = inject(MatDialogRef<RecordFormComponent, Row | null>);
  private readonly dialogs = inject(MatDialog);

  protected readonly data: RecordFormData;
  protected readonly fields: FieldConfig[];
  protected readonly lineFields: FieldConfig[];
  protected readonly editing: boolean;
  protected readonly hasLines: boolean;

  protected readonly form = new FormGroup<Record<string, AbstractControl>>({});
  protected readonly lines = new FormArray<LineGroup>([]);
  protected readonly options = signal<Record<string, SelectOption[]>>({});
  protected readonly optionsLoading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly summary = signal<string | null>(null);
  protected readonly fieldMessages = signal<Record<string, string>>({});

  constructor() {
    this.data = inject<RecordFormData>(MAT_DIALOG_DATA);
    this.fields = this.data.action ? this.data.action.fields : (this.data.resource.fields ?? []);
    const lines = this.data.action ? this.data.action.lines : this.data.resource.lines;
    this.lineFields = lines?.fields ?? [];
    this.hasLines = lines !== undefined;
    this.editing = this.data.row !== undefined && !this.data.action;
    this.buildForm();
  }

  ngOnInit(): void {
    this.loadOptions();
  }

  protected title(): string {
    if (this.data.action) {
      return this.data.action.label;
    }
    const action = this.editing ? 'Edit' : 'New';
    return `${action} ${this.data.resource.singular}`;
  }

  protected submitLabel(): string {
    if (this.submitting()) {
      return 'Saving…';
    }
    if (this.data.action) {
      return this.data.action.label;
    }
    return this.editing ? 'Save changes' : 'Create';
  }

  protected fieldError(key: string): string | null {
    return this.fieldMessages()[key] ?? null;
  }

  protected lineError(index: number, key: string): string | null {
    return this.fieldMessages()[`lines.${index}.${key}`] ?? null;
  }

  protected addLine(): void {
    this.lines.push(this.buildLine());
  }

  protected removeLine(index: number): void {
    this.lines.removeAt(index);
  }

  protected onFile(key: string, event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    const control = this.form.get(key);
    control?.setValue(file);
    control?.markAsDirty();
  }

  protected optionList(field: FieldConfig): SelectOption[] {
    return field.options ?? this.options()[this.optionKey(field)] ?? [];
  }

  protected cancel(): void {
    if (!this.form.dirty && !this.lines.dirty) {
      this.dialogRef.close(null);
      return;
    }
    this.dialogs
      .open(ConfirmDialogComponent, {
        data: {
          title: 'Discard changes?',
          message: 'Your edits to this record have not been saved. Discard them?',
          confirmLabel: 'Discard changes',
        },
        maxWidth: '95vw',
      })
      .afterClosed()
      .subscribe((discard) => {
        if (discard) {
          this.dialogRef.close(null);
        }
      });
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    this.summary.set(null);
    this.fieldMessages.set({});
    this.form.markAllAsTouched();
    if (this.form.invalid || this.lines.invalid) {
      this.summary.set('Check the highlighted fields.');
      return;
    }

    const payload = this.payload();
    const row = this.data.row;
    let request: Observable<Row>;
    if (this.data.action) {
      if (!row || typeof row['id'] !== 'number') {
        this.summary.set('This action needs a saved record.');
        return;
      }
      request = this.api.action(
        this.data.resource.endpoint,
        row['id'],
        this.data.action.path,
        payload,
      );
    } else {
      request =
        row && typeof row['id'] === 'number'
          ? this.api.update(this.data.resource.endpoint, row['id'], payload)
          : this.api.create(this.data.resource.endpoint, payload);
    }

    this.submitting.set(true);
    request.subscribe({
      next: (saved) => {
        this.submitting.set(false);
        this.dialogRef.close(saved);
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        const parsed = fieldErrors(error);
        this.fieldMessages.set(parsed.fields);
        const summary =
          error instanceof HttpErrorResponse && error.status === 403
            ? apiErrorMessage(error)
            : parsed.summary;
        this.summary.set(summary);
        this.applyControlErrors(parsed.fields);
      },
    });
  }

  private applyControlErrors(fields: Record<string, string>): void {
    for (const [key, message] of Object.entries(fields)) {
      const lineMatch = /^lines\.(\d+)\.([A-Za-z0-9_]+)$/.exec(key);
      if (lineMatch) {
        const group = this.lines.at(Number(lineMatch[1]));
        group?.get(lineMatch[2])?.setErrors({ server: message });
        continue;
      }
      const control = this.form.get(key);
      control?.setErrors({ server: message });
    }
  }

  private buildForm(): void {
    const row = this.editing ? this.data.row : undefined;
    for (const field of this.fields) {
      const validators = field.required ? [Validators.required] : [];
      if (field.type === 'number' && field.min !== undefined) {
        validators.push(Validators.min(field.min));
      }
      this.form.addControl(
        field.key,
        new FormControl(initialValue(field, row), { validators, nonNullable: false }),
      );
    }

    if (this.hasLines) {
      this.form.addControl('lines', this.lines);
      const existing = row?.['lines'];
      if (Array.isArray(existing) && existing.length > 0) {
        for (const line of existing) {
          if (typeof line === 'object' && line !== null) {
            this.lines.push(this.buildLine(line as Row));
          }
        }
      } else {
        const minimum = this.data.action
          ? (this.data.action.lines?.minLines ?? 1)
          : (this.data.resource.lines?.minLines ?? 1);
        for (let index = 0; index < minimum; index += 1) {
          this.lines.push(this.buildLine());
        }
      }
    }
  }

  private buildLine(line?: Row): LineGroup {
    const controls: Record<string, FormControl> = {};
    for (const field of this.lineFields) {
      if (field.key === 'id') {
        continue;
      }
      const validators = field.required ? [Validators.required] : [];
      if (field.type === 'number' && field.min !== undefined) {
        validators.push(Validators.min(field.min));
      }
      controls[field.key] = new FormControl(initialValue(field, line), {
        validators,
        nonNullable: false,
      });
    }
    return new FormGroup(controls);
  }

  private loadOptions(): void {
    const lookups = new Map<string, FieldConfig>();
    for (const field of [...this.fields, ...this.lineFields]) {
      if (field.type === 'select' && field.optionsEndpoint) {
        lookups.set(this.optionKey(field), field);
      }
    }
    if (lookups.size === 0) {
      return;
    }
    this.optionsLoading.set(true);
    const requests: Record<string, ReturnType<ResourceApi['options']>> = {};
    for (const [key, field] of lookups) {
      requests[key] = this.api.options(field.optionsEndpoint ?? '', field.optionsQuery);
    }
    forkJoin(requests).subscribe({
      next: (result) => {
        this.options.set(result);
        this.optionsLoading.set(false);
      },
      error: (error: unknown) => {
        this.optionsLoading.set(false);
        this.summary.set(
          `Some choices could not be loaded: ${apiErrorMessage(error)} You can still enter the remaining fields.`,
        );
      },
    });
  }

  private optionKey(field: FieldConfig): string {
    return `${field.optionsEndpoint ?? ''}|${JSON.stringify(field.optionsQuery ?? {})}`;
  }

  private payload(): Record<string, unknown> | FormData {
    const body: Record<string, unknown> = {};
    for (const field of this.fields) {
      if (this.editing && field.readOnlyOnEdit) {
        continue;
      }
      const value = this.form.get(field.key)?.value;
      if (value === '' || value === null || value === undefined) {
        // Text columns are blank-able but not nullable in the API; related
        // records, numbers and dates are nullable.
        body[field.key] = field.type === 'text' || field.type === 'textarea' ? '' : null;
        continue;
      }
      body[field.key] = value;
    }
    if (this.hasLines) {
      body['lines'] = this.lines.controls.filter((group) => {
        return this.lineFields.some((field) => {
          const value = group.get(field.key)?.value;
          return value !== null && value !== undefined && value !== '';
        });
      }).map((group) => {
        const line: Record<string, unknown> = {};
        for (const field of this.lineFields) {
          const value = group.get(field.key)?.value;
          if (value === '' || value === undefined) {
            continue;
          }
          if (field.type === 'number' && value === null) {
            continue;
          }
          line[field.key] = value;
        }
        // Only send the identity when the API returns it; create serializers
        // accept the nested fields alone.
        return line;
      });
    }
    // A multipart request is needed only when the form carries a file.
    const hasFile = this.fields.some(
      (field) => field.type === 'file' && this.form.get(field.key)?.value instanceof File,
    );
    if (!hasFile) {
      return body;
    }
    const data = new FormData();
    for (const [key, value] of Object.entries(body)) {
      if (value === null || value === undefined || value === '') {
        continue;
      }
      if (value instanceof File) {
        data.append(key, value);
      } else if (typeof value !== 'object') {
        data.append(key, String(value));
      }
    }
    return data;
  }
}
