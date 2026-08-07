import type { ResizableWidth } from '../../hooks/useResizableWidth'
import styles from './ResizeHandle.module.css'

const KEY_STEP = 16

/**
 * A draggable divider between a resizable panel and the rest of the layout.
 * Also keyboard-accessible as an ARIA slider (arrow keys step the width),
 * so resizing never depends on pointer/drag support alone.
 */
export function ResizeHandle({ resizable, label }: { resizable: ResizableWidth; label: string }) {
  return (
    <div
      className={styles.handle}
      role="slider"
      tabIndex={0}
      aria-label={label}
      aria-orientation="horizontal"
      aria-valuenow={Math.round(resizable.width)}
      aria-valuemin={resizable.min}
      aria-valuemax={resizable.max}
      onPointerDown={resizable.startDrag}
      onKeyDown={(event) => {
        if (event.key === 'ArrowLeft') {
          event.preventDefault()
          resizable.stepBy(-KEY_STEP)
        } else if (event.key === 'ArrowRight') {
          event.preventDefault()
          resizable.stepBy(KEY_STEP)
        }
      }}
    />
  )
}
