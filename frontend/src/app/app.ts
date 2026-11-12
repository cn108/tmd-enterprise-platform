import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { apiErrorMessage } from './core/auth.models';
import { AuthService } from './core/auth.service';

interface NavItem {
  label: string;
  path: string;
  icon: string;
  children?: { label: string; path: string }[];
}

@Component({
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
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
  protected readonly menuOpen = signal(false);
  protected readonly sectionTitle = signal('Dashboard');
  protected readonly activePath = signal('/');
  protected readonly navItems: NavItem[] = [
    { label: 'Dashboard', path: '/', icon: 'M3 11.5 12 4l9 7.5M5 9.8V20h5v-6h4v6h5V9.8' },
    {
      label: 'Master data',
      path: '/master-data',
      icon: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
      children: [
        { label: 'Suppliers', path: '/master-data/suppliers' },
        { label: 'Customers', path: '/master-data/customers' },
        { label: 'Products', path: '/master-data/products' },
        { label: 'Tax Rates', path: '/master-data/tax-rates' },
      ],
    },
    { label: 'Procurement', path: '/procurement', icon: 'M3 6h18l-2 10H6L4 3H2M9 20h.01M18 20h.01' },
    { label: 'Inventory', path: '/inventory', icon: 'M4 8 12 4l8 4v8l-8 4-8-4zM4 8l8 4 8-4M12 12v8' },
    { label: 'Accounting', path: '/accounting', icon: 'M5 3h14v18H5zM8 7h8M8 11h2M12 11h2M16 11h.01M8 15h2M12 15h2M16 15h.01' },
    { label: 'Invoices', path: '/invoicing', icon: 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7' },
    { label: 'Banking', path: '/banking', icon: 'M3 9 12 4l9 5M5 10v7M10 10v7M14 10v7M19 10v7M3 20h18' },
    { label: 'Projects', path: '/projects', icon: 'M3 6h7l2 2h9v11H3zM3 6v13' },
    { label: 'Services', path: '/services', icon: 'M14 6a4 4 0 0 0-5 5L4 16l4 4 5-5a4 4 0 0 0 5-5l-3 2-2-2z' },
    { label: 'Leasing', path: '/leasing', icon: 'M4 8h16v11H4zM8 8V6a4 4 0 0 1 8 0v2M9 13h6' },
    { label: 'Reports', path: '/reports', icon: 'M4 20V10M10 20V4M16 20v-7M22 20H2' },
    { label: 'Administration', path: '/administration', icon: 'M12 3 20 6v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4' },
  ];

  constructor() {
    this.router.events.pipe(filter((event) => event instanceof NavigationEnd)).subscribe(() => {
      const path = this.router.url.split('?')[0];
      const match = this.navItems.find((item) =>
        item.path === '/' ? path === '/' : path.startsWith(item.path),
      );
      this.sectionTitle.set(match?.label ?? 'Workspace');
      this.activePath.set(path);
      this.menuOpen.set(false);
    });
  }

  protected toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  protected closeMenu(): void {
    this.menuOpen.set(false);
  }

  protected isActive(path: string): boolean {
    const current = this.activePath();
    return path === '/' ? current === '/' : current.startsWith(path);
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

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
