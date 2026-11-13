import { HttpClient } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';

import { apiErrorMessage } from '../../core/auth.models';
import { AuthService } from '../../core/auth.service';
import { AccessRestrictedComponent } from '../../shared/access-restricted/access-restricted.component';
import { fieldErrors } from '../workspace/resource-api.service';
import { Row } from '../workspace/workspace-config';

interface Role {
  id: number;
  name: string;
  permission_codenames: string[];
  member_count: number;
}

interface PermissionRow {
  id: number;
  codename: string;
  name: string;
  app_label: string;
}

interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  employee_ref: string;
  department: number | null;
  department_code: string | null;
  is_active: boolean;
  must_change_password: boolean;
  mfa_required: boolean;
  role_names: string[];
  permissions: string[];
}

interface UserDraft {
  id: number | null;
  email: string;
  full_name: string;
  employee_ref: string;
  department: number | null;
  roles: string[];
  is_active: boolean;
  must_change_password: boolean;
  mfa_required: boolean;
  password: string;
}

interface RoleDraft {
  id: number | null;
  name: string;
  permissions: string[];
}

type Tab = 'users' | 'roles';

@Component({
  selector: 'app-administration',
  imports: [
    AccessRestrictedComponent,
    FormsModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
  ],
  templateUrl: './administration.component.html',
  styleUrl: './administration.component.scss',
})
export class AdministrationComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  protected readonly tab = signal<Tab>('users');
  protected readonly users = signal<AdminUser[]>([]);
  protected readonly roles = signal<Role[]>([]);
  protected readonly permissions = signal<PermissionRow[]>([]);
  protected readonly departments = signal<Row[]>([]);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly acknowledgePrivileged = signal(false);

  protected userDraft = signal<UserDraft | null>(null);
  protected roleDraft = signal<RoleDraft | null>(null);

  protected readonly canViewUsers = computed(() => this.has('identity.view_user'));
  protected readonly canViewRoles = computed(() => this.has('auth.view_group'));
  protected readonly canManageUsers = computed(
    () => this.has('identity.add_user') || this.has('identity.change_user'),
  );
  protected readonly canManageRoles = computed(
    () => this.has('auth.add_group') || this.has('auth.change_group'),
  );

  protected readonly permissionGroups = computed(() => {
    const groups = new Map<string, PermissionRow[]>();
    for (const permission of this.permissions()) {
      const list = groups.get(permission.app_label) ?? [];
      list.push(permission);
      groups.set(permission.app_label, list);
    }
    return [...groups.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([app, items]) => ({
        app,
        items: [...items].sort((left, right) => left.codename.localeCompare(right.codename)),
      }));
  });

  ngOnInit(): void {
    if (this.canViewUsers()) {
      this.loadUsers();
    }
    if (this.canViewRoles()) {
      this.loadRoles();
      this.loadPermissions();
    }
    this.loadDepartments();
  }

  protected has(permission: string): boolean {
    return (this.auth.user()?.permissions ?? []).includes(permission);
  }

  protected tabAvailable(tab: Tab): boolean {
    return tab === 'users' ? this.canViewUsers() : this.canViewRoles();
  }

  protected selectTab(tab: Tab): void {
    this.tab.set(tab);
    this.cancel();
    this.error.set(null);
    this.notice.set(null);
  }

  protected newUser(): void {
    this.roleDraft.set(null);
    this.userDraft.set({
      id: null,
      email: '',
      full_name: '',
      employee_ref: '',
      department: null,
      roles: [],
      is_active: true,
      must_change_password: true,
      mfa_required: false,
      password: '',
    });
  }

  protected editUser(user: AdminUser): void {
    this.roleDraft.set(null);
    this.userDraft.set({
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      employee_ref: user.employee_ref,
      department: user.department,
      roles: [...user.role_names],
      is_active: user.is_active,
      must_change_password: user.must_change_password,
      mfa_required: user.mfa_required,
      password: '',
    });
  }

  protected saveUser(): void {
    const draft = this.userDraft();
    if (!draft) {
      return;
    }
    if (!draft.email.trim() || !draft.full_name.trim()) {
      this.error.set('Email and full name are required.');
      return;
    }
    if (!draft.id && draft.password.length < 8) {
      this.error.set('Set an initial password of at least 8 characters.');
      return;
    }
    const body: Record<string, unknown> = {
      email: draft.email.trim(),
      full_name: draft.full_name.trim(),
      employee_ref: draft.employee_ref,
      department: draft.department,
      roles: draft.roles,
      is_active: draft.is_active,
      must_change_password: draft.must_change_password,
      mfa_required: draft.mfa_required,
    };
    if (draft.password) {
      body['password'] = draft.password;
    }
    this.save(
      draft.id ? `/api/v1/access/users/${draft.id}/` : '/api/v1/access/users/',
      draft.id ? 'patch' : 'post',
      body,
      draft.id ? 'User updated.' : 'User created.',
      () => this.loadUsers(),
    );
  }

  protected newRole(): void {
    this.userDraft.set(null);
    this.acknowledgePrivileged.set(false);
    this.roleDraft.set({ id: null, name: '', permissions: [] });
  }

  protected editRole(role: Role): void {
    this.userDraft.set(null);
    this.acknowledgePrivileged.set(false);
    this.roleDraft.set({
      id: role.id,
      name: role.name,
      permissions: [...role.permission_codenames],
    });
  }

  protected togglePermission(codename: string, checked: boolean): void {
    this.acknowledgePrivileged.set(false);
    this.roleDraft.update((draft) => {
      if (!draft) {
        return draft;
      }
      const permissions = checked
        ? [...new Set([...draft.permissions, codename])]
        : draft.permissions.filter((item) => item !== codename);
      return { ...draft, permissions };
    });
  }

  protected includesPermission(codename: string): boolean {
    return this.roleDraft()?.permissions.includes(codename) ?? false;
  }

  protected isPrivileged(codename: string): boolean {
    const name = codename.split('.').pop() ?? '';
    return (
      ['post_', 'approve_', 'record_', 'allocate_', 'cancel_'].some((prefix) =>
        name.startsWith(prefix),
      ) || codename === 'invoicing.manage_invoicesettings'
    );
  }

  protected hasPrivilegedSelection(): boolean {
    return (this.roleDraft()?.permissions ?? []).some((item) => this.isPrivileged(item));
  }

  protected saveRole(): void {
    const draft = this.roleDraft();
    if (!draft) {
      return;
    }
    if (!draft.name.trim()) {
      this.error.set('A role needs a name.');
      return;
    }
    this.save(
      draft.id ? `/api/v1/access/roles/${draft.id}/` : '/api/v1/access/roles/',
      draft.id ? 'patch' : 'post',
      {
        name: draft.name.trim(),
        permissions: draft.permissions,
        acknowledge_privileged: this.acknowledgePrivileged(),
      },
      draft.id ? 'Role updated.' : 'Role created.',
      () => this.loadRoles(),
    );
  }

  protected cancel(): void {
    this.userDraft.set(null);
    this.roleDraft.set(null);
    this.error.set(null);
  }

  private loadUsers(): void {
    this.loading.set(true);
    this.http.get<unknown>('/api/v1/access/users/?page_size=100').subscribe({
      next: (body) => {
        this.users.set(this.rows(body) as unknown as AdminUser[]);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error));
      },
    });
  }

  private loadRoles(): void {
    this.http.get<unknown>('/api/v1/access/roles/?page_size=100').subscribe({
      next: (body) => this.roles.set(this.rows(body) as unknown as Role[]),
      error: (error: unknown) => this.error.set(apiErrorMessage(error)),
    });
  }

  private loadPermissions(): void {
    this.http.get<unknown>('/api/v1/access/permissions/').subscribe({
      next: (body) => this.permissions.set(this.rows(body) as unknown as PermissionRow[]),
      error: (error: unknown) => this.error.set(apiErrorMessage(error)),
    });
  }

  private loadDepartments(): void {
    this.http.get<unknown>('/api/v1/departments/?page_size=100').subscribe({
      next: (body) => this.departments.set(this.rows(body)),
      error: () => this.departments.set([]),
    });
  }

  private rows(body: unknown): Row[] {
    if (Array.isArray(body)) {
      return body as Row[];
    }
    if (body && typeof body === 'object') {
      const results = (body as Row)['results'];
      if (Array.isArray(results)) {
        return results as Row[];
      }
    }
    return [];
  }

  private save(
    url: string,
    method: 'post' | 'patch',
    body: Record<string, unknown>,
    success: string,
    reload: () => void,
  ): void {
    this.saving.set(true);
    this.error.set(null);
    const request =
      method === 'post' ? this.http.post<Row>(url, body) : this.http.patch<Row>(url, body);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.notice.set(success);
        this.userDraft.set(null);
        this.roleDraft.set(null);
        reload();
      },
      error: (error: unknown) => {
        this.saving.set(false);
        const parsed = fieldErrors(error);
        const details = Object.values(parsed.fields).filter(Boolean);
        this.error.set(details[0] ?? parsed.summary);
      },
    });
  }
}
