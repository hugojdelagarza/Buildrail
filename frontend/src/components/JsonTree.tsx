import styles from './JsonTree.module.css'

type JsonContainer = Record<string, unknown> | unknown[]

function isContainer(value: unknown): value is JsonContainer {
  return value !== null && typeof value === 'object'
}

function entriesOf(value: JsonContainer): [string, unknown][] {
  return Array.isArray(value)
    ? value.map((item, index) => [String(index), item])
    : Object.entries(value)
}

function childPath(path: string, key: string, isArray: boolean): string {
  return isArray ? `${path}[${key}]` : `${path}.${key}`
}

/** Every container (object/array) path within `value`, root included — used
 * by "Expand all". `maxDepth` (default unlimited) lets callers compute only
 * the shallow default-expanded set instead. */
export function collectContainerPaths(
  value: unknown,
  path: string,
  maxDepth = Number.POSITIVE_INFINITY,
  depth = 0,
): string[] {
  if (!isContainer(value) || depth > maxDepth) return []
  const isArray = Array.isArray(value)
  return [
    path,
    ...entriesOf(value).flatMap(([key, child]) =>
      collectContainerPaths(child, childPath(path, key, isArray), maxDepth, depth + 1),
    ),
  ]
}

function Primitive({ value }: { value: unknown }) {
  if (value === null) return <span className={styles.null}>null</span>
  if (typeof value === 'string') return <span className={styles.string}>&quot;{value}&quot;</span>
  if (typeof value === 'number') return <span className={styles.number}>{value}</span>
  if (typeof value === 'boolean') return <span className={styles.boolean}>{String(value)}</span>
  return <span>{String(value)}</span>
}

export interface JsonTreeProps {
  value: unknown
  path: string
  expanded: Set<string>
  onToggle: (path: string) => void
}

/** Recursive, collapsible JSON tree. Container nodes (objects/arrays) are
 * togglable buttons; primitives render as colored inline text. */
export function JsonTree({ value, path, expanded, onToggle }: JsonTreeProps) {
  if (!isContainer(value)) return <Primitive value={value} />

  const isArray = Array.isArray(value)
  const entries = entriesOf(value)
  const openBrace = isArray ? '[' : '{'
  const closeBrace = isArray ? ']' : '}'

  if (entries.length === 0) {
    return (
      <span>
        {openBrace}
        {closeBrace}
      </span>
    )
  }

  const isExpanded = expanded.has(path)

  return (
    <span className={styles.tree}>
      <button
        type="button"
        className={styles.toggle}
        aria-expanded={isExpanded}
        onClick={() => onToggle(path)}
      >
        {isExpanded ? '▾' : '▸'} {openBrace}
        {!isExpanded && (
          <span className={styles.count}>
            {' '}
            {entries.length} {isArray ? 'items' : 'keys'}
          </span>
        )}
        {!isExpanded && closeBrace}
      </button>
      {isExpanded && (
        <div className={styles.indent}>
          {entries.map(([key, child], index) => (
            <div key={key} className={styles.row}>
              {!isArray && <span className={styles.key}>&quot;{key}&quot;</span>}
              {!isArray && ': '}
              <JsonTree
                value={child}
                path={childPath(path, key, isArray)}
                expanded={expanded}
                onToggle={onToggle}
              />
              {index < entries.length - 1 ? ',' : ''}
            </div>
          ))}
          <div>{closeBrace}</div>
        </div>
      )}
    </span>
  )
}
