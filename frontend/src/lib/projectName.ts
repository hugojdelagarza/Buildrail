/** Derives a short project name from a full filesystem root path, e.g.
 * "C:\Users\dev\Projects\Buildrail" -> "Buildrail". Used so the UI can show
 * project identity without persistently displaying the full local path. */
export function projectNameFromRoot(projectRoot: string): string {
  const trimmed = projectRoot.replace(/[\\/]+$/, '')
  const segments = trimmed.split(/[\\/]/)
  return segments[segments.length - 1] || trimmed
}
