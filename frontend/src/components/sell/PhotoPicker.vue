<script setup>
import { computed, ref, useTemplateRef } from 'vue'
import { MAX_PHOTO_BYTES, PHOTO_TYPES, shrinkImage } from '@/utils/image'
import { useIsMobile } from '@/composables/useMediaQuery'
import BottomSheet from '@/components/ui/BottomSheet.vue'

// Photos for a listing: 3 required slots (the cover plus two) and an
// "Add photos" tile up to 5. Photo 1 is the cover.
// Reorder: drag on desktop (or focus a photo and use ← →); on phones, hold
// and drag, or open a photo's menu and choose "Make cover".
// v-model: [{ key, url, file?, id? }] — `file` for new photos, `id` for ones
// already saved on the listing.
const props = defineProps({
  modelValue: { type: Array, required: true },
  invalid: { type: Boolean, default: false },
  describedby: { type: String, default: undefined },
})
const emit = defineEmits(['update:modelValue', 'error'])

const MIN = 3
const MAX = 5
const LONG_PRESS_MS = 350

const input = useTemplateRef('input')
const photos = computed(() => props.modelValue)
const count = computed(() => photos.value.length)
const emptySlots = computed(() => Math.max(0, MIN - count.value))
const extras = computed(() => Math.max(0, count.value - MIN))
// The Add tile fills the rest of its row: 4 columns on desktop, 3 on phones.
const isMobile = useIsMobile()
const addSpan = computed(() => (isMobile.value ? 3 : 2) - extras.value)
const busy = ref(0) // photos being shrunk
const announce = ref('')

let nextKey = 0
const newKey = () => `new-${Date.now()}-${nextKey++}`

// ---- Adding ----

function pick() {
  input.value?.click()
}

async function onFiles(e) {
  const files = [...e.target.files]
  e.target.value = '' // allow picking the same file again later
  const room = MAX - count.value - busy.value
  const errors = new Set()
  if (files.length > room) errors.add(`You can add up to ${MAX} photos.`)

  const accepted = []
  for (const file of files.slice(0, Math.max(0, room))) {
    if (!PHOTO_TYPES.includes(file.type)) errors.add('Use a JPG, PNG or WebP photo.')
    else accepted.push(file)
  }
  busy.value += accepted.length
  const added = []
  for (const file of accepted) {
    const small = await shrinkImage(file)
    busy.value -= 1
    if (small.size > MAX_PHOTO_BYTES) {
      errors.add('Each photo must be 10 MB or smaller.')
      continue
    }
    added.push({ key: newKey(), url: URL.createObjectURL(small), file: small })
  }
  if (added.length) emit('update:modelValue', [...photos.value, ...added])
  emit('error', [...errors].join(' '))
}

// ---- Removing and reordering ----

function remove(i) {
  const next = [...photos.value]
  const [gone] = next.splice(i, 1)
  if (gone?.file) URL.revokeObjectURL(gone.url)
  emit('update:modelValue', next)
  emit('error', '')
  announce.value = `Photo ${i + 1} removed.`
}

function move(from, to) {
  if (to < 0 || to >= count.value || from === to) return
  const next = [...photos.value]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  emit('update:modelValue', next)
  announce.value = to === 0 ? 'Moved to position 1. It’s now the cover.' : `Moved to position ${to + 1}.`
}

function onTileKeydown(i, e) {
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    e.preventDefault()
    const to = i + (e.key === 'ArrowLeft' ? -1 : 1)
    move(i, to)
    requestAnimationFrame(() => document.querySelector(`[data-photo-index="${to}"]`)?.focus())
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    e.preventDefault()
    remove(i)
  }
}

// Desktop drag and drop.
const dragFrom = ref(null)
const dragOver = ref(null)

function onDragStart(i, e) {
  dragFrom.value = i
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(i))
}

function onDrop(i) {
  if (dragFrom.value !== null) move(dragFrom.value, i)
  dragFrom.value = dragOver.value = null
}

// Phones: hold, then drag over another photo and let go.
let pressTimer = null
let pressStart = null

function onPointerDown(i, e) {
  if (e.pointerType !== 'touch') return
  pressStart = { x: e.clientX, y: e.clientY }
  pressTimer = setTimeout(() => {
    dragFrom.value = i
    navigator.vibrate?.(10)
  }, LONG_PRESS_MS)
}

function onTouchMove(e) {
  const t = e.touches[0]
  if (dragFrom.value === null) {
    // Moving before the hold completes is a scroll, not a drag.
    if (pressStart && Math.hypot(t.clientX - pressStart.x, t.clientY - pressStart.y) > 8) clearTimeout(pressTimer)
    return
  }
  e.preventDefault() // dragging: don't scroll the page
  const el = document.elementFromPoint(t.clientX, t.clientY)?.closest('[data-photo-index]')
  dragOver.value = el ? Number(el.dataset.photoIndex) : null
}

function onPointerUp() {
  clearTimeout(pressTimer)
  if (dragFrom.value !== null && dragOver.value !== null) move(dragFrom.value, dragOver.value)
  if (dragFrom.value !== null) dragFrom.value = dragOver.value = null
}

// Phone menu for a photo.
const menuFor = ref(null)

function makeCover(i) {
  move(i, 0)
  menuFor.value = null
}

function removeFromMenu(i) {
  remove(i)
  menuFor.value = null
}
</script>

<template>
  <div class="pp">
    <div class="pp__grid">
      <div
        v-for="(photo, i) in photos"
        :key="photo.key"
        class="pp__tile"
        :class="{
          'pp__tile--cover': i === 0,
          'is-dragging': dragFrom === i,
          'is-target': dragOver === i && dragFrom !== i,
        }"
        :data-photo-index="i"
        tabindex="0"
        :aria-label="`Photo ${i + 1} of ${count}${i === 0 ? ', cover' : ''}. Use the left and right arrow keys to move it.`"
        draggable="true"
        @dragstart="onDragStart(i, $event)"
        @dragover.prevent="dragOver = i"
        @dragleave="dragOver === i && (dragOver = null)"
        @drop.prevent="onDrop(i)"
        @dragend="dragFrom = dragOver = null"
        @keydown="onTileKeydown(i, $event)"
        @pointerdown="onPointerDown(i, $event)"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @touchmove="onTouchMove"
        @contextmenu.prevent
      >
        <img :src="photo.url" alt="" draggable="false" />
        <span v-if="i === 0" class="pp__cover">COVER</span>
        <button type="button" class="pp__remove" :aria-label="`Remove photo ${i + 1}`" @click="remove(i)">×</button>
        <button
          type="button"
          class="pp__menu"
          :aria-label="`Photo ${i + 1} options`"
          aria-haspopup="dialog"
          @click="menuFor = i"
        >
          •••
        </button>
      </div>

      <button
        v-for="n in emptySlots"
        :key="`slot-${n}`"
        type="button"
        class="pp__slot"
        :class="{ 'pp__tile--cover': count + n === 1 }"
        :aria-label="count + n === 1 ? 'Add the cover photo' : `Add photo ${count + n}`"
        :aria-describedby="describedby"
        @click="pick"
      >
        <span class="pp__plus" aria-hidden="true">+</span>
        <span class="pp__slot-label">{{ count + n === 1 ? 'COVER' : `PHOTO ${count + n}` }}</span>
      </button>

      <button
        v-if="count < MAX"
        type="button"
        class="pp__add"
        :style="{ gridColumn: `span ${addSpan}` }"
        :disabled="busy > 0"
        :aria-describedby="describedby"
        @click="pick"
      >
        <span class="pp__plus" aria-hidden="true">+</span>
        <span class="pp__add-title">{{ busy ? 'Preparing photos…' : 'Add photos' }}</span>
        <span class="pp__add-hint">JPG or PNG, up to {{ MAX - count }} more</span>
      </button>
    </div>

    <input
      ref="input"
      class="visually-hidden"
      type="file"
      :accept="PHOTO_TYPES.join(',')"
      multiple
      tabindex="-1"
      aria-hidden="true"
      @change="onFiles"
    />
    <p class="visually-hidden" aria-live="polite">{{ announce }}</p>

    <BottomSheet :open="menuFor !== null" :title="`Photo ${(menuFor ?? 0) + 1}`" @close="menuFor = null">
      <div class="pp__sheet">
        <button v-if="menuFor > 0" type="button" class="pp__sheet-btn" data-autofocus @click="makeCover(menuFor)">
          Make cover
        </button>
        <button type="button" class="pp__sheet-btn pp__sheet-btn--danger" @click="removeFromMenu(menuFor)">
          Remove photo
        </button>
      </div>
    </BottomSheet>
  </div>
</template>

<style scoped>
.pp__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-auto-rows: 140px;
  gap: 12px;
}

.pp__tile,
.pp__slot {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  min-width: 0;
}

.pp__tile {
  background: #e4dbc6;
  cursor: grab;
  touch-action: manipulation;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

.pp__tile--cover {
  grid-column: span 2;
  grid-row: span 2;
}

.pp__tile img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
}

.pp__tile.is-dragging {
  opacity: 0.5;
}

.pp__tile.is-target {
  box-shadow: inset 0 0 0 3px var(--accent);
}

.pp__tile:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(245, 184, 46, 0.45);
}

.pp__cover {
  position: absolute;
  left: 12px;
  top: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--accent);
  color: var(--ink);
}

.pp__remove,
.pp__menu {
  position: absolute;
  right: 8px;
  top: 8px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 0;
  padding: 0;
  background: rgba(18, 20, 16, 0.75);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}

.pp__tile--cover .pp__remove {
  right: 10px;
  top: 10px;
  width: 36px;
  height: 36px;
  font-size: 18px;
}

/* 44px touch targets on the small round buttons. */
.pp__remove::after,
.pp__menu::after {
  content: '';
  position: absolute;
  inset: -7px;
}

.pp__menu {
  display: none;
  font-size: 10px;
  letter-spacing: 0.05em;
}

.pp__slot,
.pp__add {
  border: 2px dashed rgba(18, 20, 16, 0.35);
  background: #ffffff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--ink);
  font-family: var(--font-display);
  cursor: pointer;
}

.pp__add {
  border-radius: 14px;
}

.pp__add:disabled {
  cursor: progress;
}

.pp__plus {
  font-size: 30px;
  font-weight: 400;
  line-height: 1;
}

.pp__slot-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
}

.pp__add-title {
  font-size: 16px;
  font-weight: 700;
}

.pp__add-hint {
  font-size: 13px;
  color: var(--muted);
}

.pp__slot:focus-visible,
.pp__add:focus-visible,
.pp__remove:focus-visible,
.pp__menu:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}

.pp__sheet {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}

.pp__sheet-btn {
  height: 52px;
  border: 1.5px solid rgba(18, 20, 16, 0.2);
  border-radius: 12px;
  background: #ffffff;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
}

.pp__sheet-btn--danger {
  color: var(--loss);
}

@media (max-width: 767px) {
  .pp__grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    grid-auto-rows: 104px;
    gap: 8px;
  }

  .pp__tile,
  .pp__slot,
  .pp__add {
    border-radius: 12px;
  }

  .pp__cover {
    left: 8px;
    top: 8px;
    font-size: 10px;
    letter-spacing: 0.1em;
    padding: 5px 8px;
  }

  /* Phones use the photo menu instead of the × (Make cover, Remove). */
  .pp__remove {
    display: none;
  }

  .pp__menu {
    display: block;
  }

  .pp__add {
    flex-direction: row;
  }

  .pp__plus {
    font-size: 26px;
  }

  .pp__add-hint {
    display: none;
  }
}
</style>
