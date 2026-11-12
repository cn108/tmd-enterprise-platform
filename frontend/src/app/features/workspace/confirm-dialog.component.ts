import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

export interface ConfirmData {
  title: string;
  message: string;
  confirmLabel: string;
  reason?: { label: string; required: boolean };
}

export interface ConfirmResult {
  reason: string;
}

/**
 * Confirmation for a state-changing action. It only collects a decision and an
 * optional reason; the backend performs the transition and can still refuse it.
 */
@Component({
  selector: 'app-confirm-dialog',
  imports: [
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>
      <p class="message">{{ data.message }}</p>
      @if (data.reason; as reason) {
        <mat-form-field appearance="outline" class="reason">
          <mat-label>{{ reason.label }}</mat-label>
          <textarea
            matInput
            rows="2"
            name="reason"
            [ngModel]="text()"
            (ngModelChange)="text.set($event)"
          ></textarea>
          @if (reason.required && text().trim().length === 0) {
            <mat-hint>{{ reason.label }} is required.</mat-hint>
          }
        </mat-form-field>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="cancel()">Cancel</button>
      <button
        mat-flat-button
        type="button"
        (click)="confirm()"
        [disabled]="data.reason?.required === true && text().trim().length === 0"
      >
        {{ data.confirmLabel }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .message {
      margin: 0;
      max-width: 34rem;
      color: var(--tmd-ink);
    }

    .reason {
      display: block;
      margin-top: 1rem;
      min-width: min(30rem, 70vw);
    }
  `,
})
export class ConfirmDialogComponent {
  private readonly dialogRef = inject(MatDialogRef<ConfirmDialogComponent, ConfirmResult | null>);
  protected readonly data: ConfirmData;
  protected readonly text = signal('');

  constructor() {
    this.data = inject<ConfirmData>(MAT_DIALOG_DATA);
  }

  protected cancel(): void {
    this.dialogRef.close(null);
  }

  protected confirm(): void {
    this.dialogRef.close({ reason: this.text().trim() });
  }
}
