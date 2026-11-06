<script setup>
import { useTemplateRef } from 'vue'
import { useModal } from '@/composables/useModal'

// The app's dialogs (Make an offer, Pay into escrow, Confirm receipt): a
// centred dialog on desktop, a bottom sheet with a handle on mobile. Values
// from design/detail-buyer-2-offer-open-*, pay-* and deal-08-*. The slot
// supplies the heading; pass its id as `labelledby`. `width` is the outer
// width (content + padding); `top` is the gap above the dialog.
const props = defineProps({
  open: { type: Boolean, required: true },
  labelledby: { type: String, required: true },
  sheet: { type: Boolean, default: false },
  width: { type: Number, default: 632 },
  padding: { type: String, default: '36px' },
  top: { type: Number, default: 150 },
  gap: { type: Number, default: 22 },
  role: { type: String, default: 'dialog' },
})
const emit = defineEmits(['close'])

const panel = useTemplateRef('panel')
const { onKeydown } = useModal(panel, () => props.open, () => emit('close'))
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="mp-layer"
      :class="{ 'mp-layer--sheet': sheet }"
      :style="sheet ? undefined : { paddingTop: `${top}px` }"
      @keydown="onKeydown"
    >
      <div class="mp-backdrop" aria-hidden="true" @click="emit('close')"></div>
      <div
        ref="panel"
        class="mp"
        :class="sheet ? 'mp--sheet' : 'mp--dialog'"
        :style="sheet ? undefined : { width: `${width}px`, padding, gap: `${gap}px` }"
        :role="role"
        aria-modal="true"
        :aria-labelledby="labelledby"
      >
        <span v-if="sheet" class="mp__handle" aria-hidden="true"></span>
        <slot />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mp-layer {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 150px 16px 32px;
  overflow-y: auto;
  box-sizing: border-box;
}

.mp-layer--sheet {
  flex-direction: column;
  justify-content: flex-end;
  align-items: stretch;
  padding: 0;
  overflow: hidden;
}

.mp-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(13, 20, 16, 0.62);
}

.mp {
  position: relative;
  box-sizing: border-box;
  background: var(--paper);
  color: var(--ink);
  display: flex;
  flex-direction: column;
}

/* 560px of content plus the padding, as the reference (content-box). */
.mp--dialog {
  width: 632px;
  max-width: 100%;
  border-radius: 22px;
  padding: 36px;
  gap: 22px;
  box-shadow: 0 40px 80px rgba(0, 0, 0, 0.35);
}

.mp--sheet {
  border-radius: 22px 22px 0 0;
  padding: 12px 20px calc(28px + env(safe-area-inset-bottom, 0px));
  gap: 18px;
  max-height: 92vh;
  max-height: 92dvh;
  overflow-y: auto;
}

.mp__handle {
  align-self: center;
  flex-shrink: 0;
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: rgba(18, 20, 16, 0.25);
}

@media (max-height: 820px) {
  .mp-layer:not(.mp-layer--sheet) {
    padding-top: 48px !important;
  }
}

.mp :deep(:is(button, a, input, textarea):focus-visible) {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}
</style>
