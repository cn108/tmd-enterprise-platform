import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { of, throwError } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth.service';
import { TEST_USER } from '../../core/testing/auth.fixtures';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let login: ReturnType<typeof vi.fn>;
  let navigateByUrl: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    login = vi.fn(() => of(TEST_USER));
    navigateByUrl = vi.fn().mockResolvedValue(true);

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: { login } },
        { provide: Router, useValue: { navigateByUrl } },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap({}) } },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    fixture.detectChanges();
  });

  function fill(email: string, password: string): void {
    const element = fixture.nativeElement as HTMLElement;
    const emailInput = element.querySelector('input[type=email]') as HTMLInputElement;
    const passwordInput = element.querySelector('input[type=password]') as HTMLInputElement;

    emailInput.value = email;
    emailInput.dispatchEvent(new Event('input'));
    passwordInput.value = password;
    passwordInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function submit(): void {
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('does not call the API when the form is invalid', () => {
    submit();

    expect(login).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('.field__error')).not.toBeNull();
  });

  it('signs in and navigates to the intended destination', async () => {
    fill('ama@example.com', 'secret');
    submit();
    await fixture.whenStable();

    expect(login).toHaveBeenCalledWith('ama@example.com', 'secret');
    expect(navigateByUrl).toHaveBeenCalledWith('/');
  });

  it('shows the server message when credentials are rejected', () => {
    login.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 401,
            error: {
              error: {
                code: 'invalid_credentials',
                message: 'Email or password is incorrect.',
                details: null,
                request_id: 'req-1',
              },
            },
          }),
      ),
    );

    fill('ama@example.com', 'wrong-password');
    submit();

    const alert = fixture.nativeElement.querySelector('[role=alert]') as HTMLElement;
    expect(alert.textContent).toContain('Email or password is incorrect.');
    expect(navigateByUrl).not.toHaveBeenCalled();
  });

  it('re-enables the form after a failure so the user can retry', () => {
    login.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 503, error: null })),
    );

    fill('ama@example.com', 'secret');
    submit();

    const button = fixture.nativeElement.querySelector('button[type=submit]') as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });
});
