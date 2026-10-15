import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// React Testing Library does not auto-clean the DOM when Vitest globals are off,
// so unmount every rendered component after each test.
afterEach(() => {
  cleanup()
})
