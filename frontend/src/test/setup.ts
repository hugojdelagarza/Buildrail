import '@testing-library/jest-dom/vitest'

// jsdom does not implement matchMedia; useMediaQuery (narrow-layout detection)
// needs a stub so components using it can mount in tests.
if (typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}
