import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-access-restricted',
  imports: [RouterLink],
  template: `
    <section class="restricted" role="region" [attr.aria-label]="'Access restricted to ' + section()">
      <span class="restricted__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor">
          <rect x="5" y="10" width="14" height="10" rx="2" stroke-width="1.7" />
          <path d="M8 10V7a4 4 0 0 1 8 0v3" stroke-width="1.7" />
          <circle cx="12" cy="15" r="1.2" fill="currentColor" stroke="none" />
        </svg>
      </span>
      <h2>Access restricted</h2>
      <p>Your current account does not have permission to view {{ section() }}.</p>
      <p class="restricted__help">
        Contact your system administrator or manager if you require access.
      </p>
      <a class="restricted__button" routerLink="/">Return to dashboard</a>
    </section>
  `,
  styles: [
    `
      .restricted {
        display: flex;
        flex-direction: column;
        align-items: center;
        max-width: 34rem;
        margin: 2rem auto;
        padding: 2.5rem 2rem;
        border: 1px solid var(--tmd-line);
        border-radius: 0.9rem;
        background: #fff;
        box-shadow: 0 1px 2px rgb(16 32 56 / 6%);
        text-align: center;
      }

      .restricted__icon {
        display: grid;
        width: 3.5rem;
        height: 3.5rem;
        place-items: center;
        margin-bottom: 1rem;
        border-radius: 50%;
        background: #f2f5f9;
        color: var(--tmd-navy-soft);
      }

      h2 {
        margin: 0;
        font-size: 1.25rem;
        color: var(--tmd-navy);
      }

      p {
        margin: 0.55rem 0 0;
        font-size: 0.9rem;
        line-height: 1.55;
        color: var(--tmd-muted);
      }

      .restricted__help {
        margin-top: 0.3rem;
      }

      .restricted__button {
        margin-top: 1.4rem;
        padding: 0.55rem 1rem;
        border-radius: 0.4rem;
        background: var(--tmd-navy-soft);
        color: #fff;
        font-size: 0.85rem;
        font-weight: 600;
        text-decoration: none;
      }
    `,
  ],
})
export class AccessRestrictedComponent {
  readonly section = input('this section');
}
