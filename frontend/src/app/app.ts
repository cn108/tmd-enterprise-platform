import { Component, inject, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';

import { apiErrorMessage } from './core/auth.models';
import { AuthService } from './core/auth.service';

@Component({
  imports: [RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly user = this.auth.user;
  protected readonly signingOut = signal(false);
  protected readonly signOutError = signal<string | null>(null);

  protected signOut(): void {
    if (this.signingOut()) {
      return;
    }

    this.signingOut.set(true);
    this.signOutError.set(null);

    this.auth.logout().subscribe({
      next: () => {
        this.signingOut.set(false);
        void this.router.navigateByUrl('/login');
      },
      error: (error: unknown) => {
        // The session is still live, so staying signed in is the honest state.
        this.signingOut.set(false);
        this.signOutError.set(apiErrorMessage(error));
      },
    });
  }
}
