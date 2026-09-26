<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import { CONDITIONS } from '@/config/listing'
import { useIsMobile } from '@/composables/useMediaQuery'
import BottomSheet from '@/components/ui/BottomSheet.vue'

// Condition: a custom listbox (sell-5-condition-dropdown-open-desktop), each
// option with its one-line meaning. On phones the same options open in a
// bottom sheet. The chosen option's meaning shows under the field.
const props = defineProps({
  modelValue: { type: String, default: '' },
  id: { type: String, required: true },
  labelledby: { type: String, required: true },
  invalid: { type: Boolean, default: false },
  describedby: { type: String, default: undefined },
})
const emit = defineEmits(['update:modelValue'])

const isMobile = useIsMobile()
const open = ref(false)
const active = ref(0)
const root = useTemplateRef('root')
const trigger = useTemplateRef('trigger')
const listbox = useTemplateRef('listbox')

const selected = computed(() => CONDITIONS.find((c) => c.key === props.modelValue))
const optionId = (i) => `${props.id}-opt-${i}`

async function openList() {
  active.value = Math.max(0, CONDITIONS.findIndex((c) => c.key === props.modelValue))
  open.value = true
  if (!isMobile.value) {
    await nextTick()
    listbox.value?.focus()
  }
}

function close({ focusTrigger = true } = {}) {
  open.value = false
  if (focusTrigger) trigger.value?.focus()
}

function choose(i) {
  emit('update:modelValue', CONDITIONS[i].key)
  close()
}

function onTriggerKeydown(e) {
  if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
    e.preventDefault()
    openList()
  }
}

function onListKeydown(e) {
  const last = CONDITIONS.length - 1
  const moves = { ArrowDown: active.value + 1, ArrowUp: active.value - 1, Home: 0, End: last }
  if (e.key in moves) {
    e.preventDefault()
    active.value = Math.min(last, Math.max(0, moves[e.key]))
    document.getElementById(optionId(active.value))?.scrollIntoView({ block: 'nearest' })
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    choose(active.value)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    close()
  } else if (e.key === 'Tab') {
    close({ focusTrigger: false })
  }
}

// Clicking outside closes the desktop list.
function onDocPointer(e) {
  if (open.value && !isMobile.value && root.value && !root.value.contains(e.target)) close({ focusTrigger: false })
}
onMounted(() => document.addEventListener('pointerdown', onDocPointer))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointer))
</script>

<template>
  <div ref="root" class="cond">
    <button
      :id="id"
      ref="trigger"
      type="button"
      class="cond__trigger"
      :class="{ 'is-open': open && !isMobile, 'is-error': invalid, 'is-empty': !selected }"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-labelledby="`${labelledby} ${id}`"
      :aria-describedby="describedby"
      :aria-invalid="invalid || undefined"
      @click="open ? close() : openList()"
      @keydown="onTriggerKeydown"
    >
      <span>{{ selected ? selected.label : 'Choose condition' }}</span>
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#121410" stroke-width="1.8" aria-hidden="true"><path d="M3 5l4 4 4-4"></path></svg>
    </button>

    <div
      v-if="open && !isMobile"
      ref="listbox"
      class="cond__list"
      role="listbox"
      tabindex="-1"
      :aria-labelledby="labelledby"
      :aria-activedescendant="optionId(active)"
      @keydown="onListKeydown"
    >
      <div
        v-for="(c, i) in CONDITIONS"
        :id="optionId(i)"
        :key="c.key"
        role="option"
        class="cond__opt"
        :class="{ 'is-active': i === active }"
        :aria-selected="c.key === modelValue"
        @click="choose(i)"
        @pointermove="active = i"
      >
        <span class="cond__opt-label">{{ c.label }}</span>
        <span class="cond__opt-meaning">{{ c.meaning }}</span>
      </div>
    </div>

    <BottomSheet :open="open && isMobile" title="Condition" @close="close()">
      <div role="listbox" :aria-labelledby="labelledby" class="cond__sheet">
        <button
          v-for="(c, i) in CONDITIONS"
          :key="c.key"
          type="button"
          role="option"
          class="cond__opt cond__opt--sheet"
          :aria-selected="c.key === modelValue"
          :data-autofocus="c.key === modelValue || (!modelValue && i === 0) ? '' : undefined"
          @click="choose(i)"
        >
          <span class="cond__opt-label">{{ c.label }}</span>
          <span class="cond__opt-meaning">{{ c.meaning }}</span>
        </button>
      </div>
    </BottomSheet>
  </div>
</template>

<style scoped>
.cond {
  position: relative;
}

.cond__trigger {
  width: 100%;
  height: 56px;
  box-sizing: border-box;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 400;
  color: var(--ink);
  text-align: left;
  cursor: pointer;
}

.cond__trigger.is-empty {
  color: #8c8e85;
}

.cond__trigger.is-error {
  border-color: var(--loss);
}

.cond__trigger.is-open,
.cond__trigger:focus-visible {
  border: 2px solid var(--ink);
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
  outline: none;
}

.cond__list {
  position: absolute;
  top: calc(100% + 12px);
  left: 0;
  right: 0;
  z-index: 5;
  background: #ffffff;
  border: 1.5px solid var(--ink);
  border-radius: 14px;
  padding: 6px;
  box-shadow: 0 24px 50px rgba(18, 20, 16, 0.18);
  display: flex;
  flex-direction: column;
  outline: none;
}

.cond__opt {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 14px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  min-height: 44px;
  box-sizing: border-box;
  cursor: pointer;
  font-family: var(--font-display);
}

.cond__opt[aria-selected='true'] {
  background: var(--paper-deep);
}

/* Keyboard/hover position, distinct from the selected fill. */
.cond__list:focus-visible .cond__opt.is-active,
.cond__opt.is-active:hover {
  box-shadow: inset 0 0 0 2px var(--ink);
}

.cond__opt-label {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}

.cond__opt-meaning {
  font-size: 13px;
  color: var(--muted);
}

.cond__sheet {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 8px;
}

.cond__opt--sheet {
  width: 100%;
}

@media (max-width: 767px) {
  .cond__trigger {
    height: 54px;
    padding: 0 14px;
  }
}
</style>
