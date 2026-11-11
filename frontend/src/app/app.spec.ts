import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from './app';
import { AuthenticatedUser } from './core/auth.models';
import { AuthService } from './core/auth.service';
import { TEST_USER } from './core/testing/auth.fixtures';

describe('App shell', () => {
  const userSignal = signal<AuthenticatedUser | null>(null);
  const logout = vi.fn(() => of(void 0));

  beforeEach(async () => {
    userSignal.set(null);
    logout.mockClear();

    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: { user: userSignal.asReadonly(), logout },
        },
      ],
    }).compileComponents();
  });

  it('renders the platform brand', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('h1') as HTMLElement;
    expect(heading.textContent).toContain('TMD Platform');
  });

  it('hides the session controls when nobody is signed in', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.session')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Secure area');
  });

  it('shows the signed-in user and signs out on request', () => {
    // The shell navigates after logout; stub the router so the test does not
    // depend on a route table it does not need.
    vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);

    userSignal.set(TEST_USER);
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.session__name').textContent).toContain(
      'Ama Okafor',
    );

    const button = fixture.nativeElement.querySelector('.session__signout') as HTMLButtonElement;
    button.click();

    expect(logout).toHaveBeenCalledOnce();
  });
});
