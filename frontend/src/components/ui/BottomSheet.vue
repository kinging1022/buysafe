<script setup>
import { nextTick, onBeforeUnmount, useTemplateRef, watch } from 'vue'

// A mobile sheet over the page: a modal dialog on paper. `full` makes it the
// full-height Filters sheet; otherwise it hugs its content (Condition).
// Escape and the backdrop close it; focus moves in and returns on close.
const props = defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, required: true },
  full: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const panel = useTemplateRef('panel')
let returnTo = null

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

function onKeydown(e) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    emit('close')
  } else if (e.key === 'Tab' && panel.value) {
    // Keep Tab inside the sheet.
    const items = [...panel.value.querySelectorAll(FOCUSABLE)].filter((el) => !el.disabled)
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
  () => props.open,
  async (open) => {
    if (open) {
      returnTo = document.activeElement
      document.body.style.overflow = 'hidden'
      await nextTick()
      const target = panel.value?.querySelector('[data-autofocus]') || panel.value?.querySelector(FOCUSABLE)
      target?.focus()
    } else {
      document.body.style.overflow = ''
      returnTo?.focus?.()
    }
  },
)

onBeforeUnmount(() => (document.body.style.overflow = ''))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="sheet-layer" @keydown="onKeydown">
      <div class="sheet-backdrop" aria-hidden="true" @click="emit('close')"></div>
      <div
        ref="panel"
        class="sheet"
        :class="{ 'sheet--full': full }"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
      >
        <div class="sheet__head">
          <span class="sheet__title">{{ title }}</span>
          <button type="button" class="sheet__close" aria-label="Close" @click="emit('close')">×</button>
        </div>
        <div class="sheet__body"><slot /></div>
        <div v-if="$slots.footer" class="sheet__foot"><slot name="footer" /></div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.sheet-layer {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.sheet-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(18, 20, 16, 0.45);
}

.sheet {
  position: relative;
  background: var(--paper);
  color: var(--ink);
  border-radius: 20px 20px 0 0;
  max-height: 85vh;
  max-height: 85dvh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 -12px 30px rgba(18, 20, 16, 0.18);
}

.sheet--full {
  height: 100vh;
  height: 100dvh;
  max-height: none;
  border-radius: 0;
}

.sheet__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px 10px 20px;
  border-bottom: 1px solid rgba(18, 20, 16, 0.12);
}

.sheet__title {
  font-size: 19px;
  font-weight: 700;
}

.sheet__close {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  font-family: var(--font-display);
  font-size: 26px;
  line-height: 1;
  color: var(--ink);
  cursor: pointer;
  border-radius: 10px;
}

.sheet__body {
  flex-grow: 1;
  overflow-y: auto;
  padding: 8px 20px 20px;
}

.sheet__foot {
  padding: 12px 20px calc(16px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid rgba(18, 20, 16, 0.12);
  background: var(--paper);
}

.sheet :is(button, a, input, select):focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}
</style>
