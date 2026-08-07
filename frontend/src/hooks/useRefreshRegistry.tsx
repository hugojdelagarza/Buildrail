import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

type RefreshHandler = () => void

interface RefreshRegistry {
  register: (handler: RefreshHandler | null) => void
  trigger: () => void
}

const RefreshContext = createContext<RefreshRegistry | null>(null)

/**
 * Lets the currently mounted page register its own `useAsync` reload as
 * "refresh the current page" — the one thing the global `R` shortcut and the
 * command palette's "Refresh Current Page" action need, without either of
 * them knowing anything about individual pages.
 */
export function RefreshProvider({ children }: { children: React.ReactNode }) {
  const handlerRef = useRef<RefreshHandler | null>(null)
  const [registry] = useState<RefreshRegistry>(() => ({
    register: (handler) => {
      handlerRef.current = handler
    },
    trigger: () => {
      handlerRef.current?.()
    },
  }))

  return <RefreshContext.Provider value={registry}>{children}</RefreshContext.Provider>
}

/** Call from a page with its `useAsync` `reload` function (or any refresh callback). */
export function useRegisterRefresh(handler: RefreshHandler | undefined | null) {
  const registry = useContext(RefreshContext)
  useEffect(() => {
    if (!registry) return
    registry.register(handler ?? null)
    return () => registry.register(null)
  }, [registry, handler])
}

/** Call to trigger whatever the current page registered, if anything. */
export function useTriggerRefresh(): () => void {
  const registry = useContext(RefreshContext)
  return useCallback(() => registry?.trigger(), [registry])
}
