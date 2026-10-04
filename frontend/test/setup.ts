import "@testing-library/jest-dom/vitest";
import { toHaveNoViolations } from "jest-axe";
import { vi } from "vitest";

// jest-axe-Matcher global registrieren: `expect(el).toHaveNoViolations()`.
expect.extend(toHaveNoViolations);

// Most component/page tests render operational UI directly instead of mounting the
// production RootLayout. Since the frontend shell and contract review components now
// consume useAuth(), provide a conservative authenticated default for tests. Individual
// test files can still override this module with their own vi.mock when they need a
// specific role, organization or authentication state.
const defaultMembership = {
  organization_id: "org-test",
  organization_slug: "test-klinik",
  organization_name: "Test Klinik",
  role: "admin" as const,
  hospital_id: null,
  department_id: null,
  is_default: true,
};

const defaultAccount = {
  id: "user-test",
  email: "admin@example.test",
  display_name: "Test Admin",
  is_active: true,
  is_developer: false,
  last_login_at: null,
  memberships: [defaultMembership],
};

vi.mock("@/components/auth/AuthProvider", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({
    account: defaultAccount,
    membership: defaultMembership,
    memberships: [defaultMembership],
    organizationSlug: defaultMembership.organization_slug,
    loading: false,
    role: defaultMembership.role,
    refresh: vi.fn().mockResolvedValue(defaultAccount),
    selectOrganization: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}));
