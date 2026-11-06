<script setup>
import { computed, ref, watch } from 'vue'
import ModalPanel from '@/components/ui/ModalPanel.vue'

// Report a problem. TODO: not designed yet; a simple form in the confirm
// dialog's style. Staff are emailed and follow up (a no-show refund is done
// from the admin for now).
const props = defineProps({
  open: { type: Boolean, required: true },
  sheet: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  error: { type: String, default: '' },
  sent: { type: Boolean, default: false },
  state: { type: String, default: '' },
})
const emit = defineEmits(['close', 'send'])

// Only an open deal still has the money in escrow.
const intro = computed(() => {
  if (props.state === 'released') return 'This deal is closed and the money was released to the seller. Tell us what happened and we’ll look into it.'
  if (props.state === 'refunded') return 'This deal is closed and the money was refunded to the buyer. Tell us what happened and we’ll look into it.'
  return 'Tell us what happened. The money stays held while we look into it.'
})

const text = ref('')
watch(
  () => props.open,
  (open) => open && (text.value = ''),
)
</script>

<template>
  <ModalPanel :open="open" :sheet="sheet" labelledby="rp-title" :width="612" padding="34px 36px" :top="160" :gap="18" @close="emit('close')">
    <div class="rp">
      <span class="rp-k">REPORT A PROBLEM</span>
      <h2 id="rp-title" class="rp-h">What went wrong?</h2>
      <template v-if="!sent">
        <span class="rp-p">{{ intro }}</span>
        <textarea v-model="text" rows="5" maxlength="1000" class="rp-text" aria-label="What went wrong?" data-autofocus></textarea>
        <p v-if="error" class="rp-error" role="alert">{{ error }}</p>
        <div class="rp-btns">
          <button type="button" class="rp-no" @click="emit('close')">Cancel</button>
          <button type="button" class="rp-yes" :disabled="busy || text.trim().length < 10" @click="emit('send', text.trim())">Send report</button>
        </div>
      </template>
      <template v-else>
        <span class="rp-p" role="status">Thanks. We’ve got your report and will get back to you in the app.</span>
        <button type="button" class="rp-yes" @click="emit('close')">Done</button>
      </template>
    </div>
  </ModalPanel>
</template>

<style scoped>
.rp {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rp-k {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: #a3361f;
}

.rp-h {
  margin: -8px 0 0;
  font-size: 34px;
  line-height: 1.05;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.rp-p {
  font-size: 15px;
  line-height: 1.55;
  color: var(--ink-2);
}

.rp-text {
  box-sizing: border-box;
  width: 100%;
  padding: 12px 14px;
  background: #ffffff;
  border: 1.5px solid rgba(18, 20, 16, 0.22);
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 16px;
  line-height: 1.5;
  color: var(--ink);
  resize: vertical;
  outline: none;
}

.rp-error {
  margin: 0;
  font-size: 14px;
  color: #a3361f;
}

.rp-btns {
  display: grid;
  grid-template-columns: 1fr 1.6fr;
  gap: 10px;
}

.rp-no,
.rp-yes {
  height: 56px;
  border-radius: 14px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

.rp-no {
  border: 1.5px solid rgba(18, 20, 16, 0.3);
  background: transparent;
  color: var(--ink);
  font-weight: 600;
}

.rp-yes {
  border: 0;
  background: var(--forest);
  color: var(--paper);
}

.rp-yes:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.rp-text:focus-visible {
  box-shadow: 0 0 0 4px rgba(245, 184, 46, 0.45);
}
</style>
