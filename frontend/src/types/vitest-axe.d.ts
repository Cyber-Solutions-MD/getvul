// Type augmentation for vitest-axe matchers under Vitest 4.
// vitest-axe@0.1 ships type augmentation against the legacy `Vi` namespace; Vitest 4
// moved the `Assertion` interface to the `@vitest/expect` module. This file
// re-augments both the module and the legacy namespace so
// `expect(container).toHaveNoViolations()` typechecks across vitest versions.

import 'vitest';
import type { AxeMatchers } from 'vitest-axe/matchers';

declare module '@vitest/expect' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface Assertion<T = unknown> extends AxeMatchers {}
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}

declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface Assertion<T = unknown> extends AxeMatchers {}
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
