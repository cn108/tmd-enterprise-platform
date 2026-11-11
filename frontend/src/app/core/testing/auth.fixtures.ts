import { AuthenticatedUser } from '../auth.models';

/**
 * Shared fixture. It lives outside any `*.spec.ts` file on purpose: importing a
 * value from a spec file re-registers that file's tests in the importing suite.
 */
export const TEST_USER: AuthenticatedUser = {
  id: 1,
  email: 'ama@example.com',
  full_name: 'Ama Okafor',
  employee_ref: '',
  department: 'FIN',
  must_change_password: false,
  mfa_required: false,
  roles: [],
  permissions: [],
};
