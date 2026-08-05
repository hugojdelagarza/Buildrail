import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
}

/**
 * Runs `fetcher(signal)` on mount and whenever `deps` change, aborting any
 * in-flight request on unmount or re-run — the app's one shared pattern for
 * "call the API client, track loading/error state, cancel on unmount"
 * so individual pages never manage fetch/AbortController by hand.
 */
export function useAsync<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: React.DependencyList,
): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true })
  const [reloadToken, setReloadToken] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    const controller = new AbortController()
    setState((previous) => ({ data: previous.data, error: null, loading: true }))

    fetcherRef
      .current(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.cancelled) return
        const message = error instanceof Error ? error.message : 'Unknown error.'
        setState({ data: null, error: message, loading: false })
      })

    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadToken])

  return { ...state, reload: () => setReloadToken((token) => token + 1) }
}
