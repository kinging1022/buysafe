import { nextTick, onBeforeUnmount, watch } from 'vue'

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

/**
 * Modal behaviour for a dialog or sheet: while `isOpen()` is true the page
 * behind doesn't scroll, focus moves into `panel` ([data-autofocus] first) and
 * Tab stays inside it; Escape calls `close`. Focus returns to where it was.
 * Bind the returned `onKeydown` on the layer that wraps the panel.
 */
export function useModal(panel, isOpen, close) {
  let returnTo = null
  let opened = false

  function onKeydown(e) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      close()
    } else if (e.key === 'Tab' && panel.value) {
      const items = [...panel.value.querySelectorAll(FOCUSABLE)].filter((el) => !el.disabled && el.offsetParent !== null)
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }

  watch(
    isOpen,
    async (open) => {
      if (open) {
        opened = true
        returnTo = document.activeElement
        document.body.style.overflow = 'hidden'
        await nextTick()
        const target = panel.value?.querySelector('[data-autofocus]') || panel.value?.querySelector(FOCUSABLE)
        target?.focus()
      } else if (opened) {
        opened = false
        document.body.style.overflow = ''
        returnTo?.focus?.()
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => opened && (document.body.style.overflow = ''))

  return { onKeydown }
}
