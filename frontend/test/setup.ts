import "@testing-library/jest-dom/vitest";
import { toHaveNoViolations } from "jest-axe";

// jest-axe-Matcher global registrieren: `expect(el).toHaveNoViolations()`.
expect.extend(toHaveNoViolations);
