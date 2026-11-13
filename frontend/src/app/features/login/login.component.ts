import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { apiErrorMessage, MfaSetup, mfaChallenge } from '../../core/auth.models';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly formBuilder = inject(NonNullableFormBuilder);

  protected readonly form = this.formBuilder.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  protected readonly mfaForm = this.formBuilder.group({
    code: ['', [Validators.required, Validators.minLength(6)]],
  });

  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly mfaStep = signal<'verify' | 'enroll' | null>(null);
  protected readonly mfaSetup = signal<MfaSetup | null>(null);
  private mfaToken: string | null = null;

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    if (this.submitting()) {
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: () => {
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/';
        void this.router.navigateByUrl(returnUrl);
      },
      error: (error: HttpErrorResponse) => {
        this.submitting.set(false);
        const challenge = mfaChallenge(error);
        if (challenge) {
          this.mfaToken = challenge.token;
          this.mfaStep.set(challenge.purpose);
          this.errorMessage.set(null);
          if (challenge.purpose === 'enroll') {
            this.beginEnrolment();
          }
          return;
        }
        this.errorMessage.set(apiErrorMessage(error));
      },
    });
  }

  protected submitMfa(): void {
    if (this.mfaForm.invalid || this.submitting() || !this.mfaToken) {
      this.mfaForm.markAllAsTouched();
      return;
    }
    const code = this.mfaForm.getRawValue().code.trim();
    const request =
      this.mfaStep() === 'enroll'
        ? this.auth.confirmMfa(this.mfaToken, code)
        : this.auth.verifyMfa(this.mfaToken, code);
    this.submitting.set(true);
    this.errorMessage.set(null);
    request.subscribe({
      next: () => {
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/';
        void this.router.navigateByUrl(returnUrl);
      },
      error: (error: HttpErrorResponse) => {
        this.submitting.set(false);
        this.errorMessage.set(apiErrorMessage(error));
      },
    });
  }

  protected cancelMfa(): void {
    this.mfaStep.set(null);
    this.mfaSetup.set(null);
    this.mfaToken = null;
    this.mfaForm.reset();
    this.errorMessage.set(null);
  }

  private beginEnrolment(): void {
    if (!this.mfaToken) {
      return;
    }
    this.submitting.set(true);
    this.auth.startMfaEnrolment(this.mfaToken).subscribe({
      next: (setup) => {
        this.mfaSetup.set(setup);
        this.submitting.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.submitting.set(false);
        this.errorMessage.set(apiErrorMessage(error));
      },
    });
  }
}
