import { useEffect, useState } from 'react'

/** Tracks a CSS media query's match state, updating live on viewport changes. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const mql = window.matchMedia(query)
    function onChange() {
      setMatches(mql.matches)
    }
    onChange()
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])

  return matches
}
