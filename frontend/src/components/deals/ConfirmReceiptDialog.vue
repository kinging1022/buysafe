<script setup>
import { ref, watch } from 'vue'
import { naira } from '@/utils/format'
import { shortTitle } from '@/utils/deals'
import ModalPanel from '@/components/ui/ModalPanel.vue'

// "Are you sure?" before the money is released (design/deal-08-*): a dialog
// on desktop, a sheet on mobile. The checkbox is required.
const props = defineProps({
  open: { type: Boolean, required: true },
  sheet: { type: Boolean, default: false },
  deal: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['close', 'confirm', 'report'])

const checked = ref(false)
watch(
  () => props.open,
  () => (checked.value = false),
)
</script>

<template>
  <ModalPanel
    :open="open"
    :sheet="sheet"
    role="alertdialog"
    labelledby="cf-title"
    :width="612"
    padding="34px 36px"
    :top="220"
    :gap="20"
    @close="emit('close')"
  >
    <div class="cf" :class="{ 'cf--m': sheet }">
      <span class="cf-k">THIS CAN’T BE UNDONE</span>
      <h2 id="cf-title" class="cf-h">Do you have the {{ shortTitle(deal.listing.title) }}, and is it as described?</h2>
      <span v-if="!sheet" class="cf-p num">Confirming releases <strong>{{ naira(deal.amount) }}</strong> from escrow to {{ deal.seller_first_name }}. If anything’s wrong, don’t confirm. <button type="button" class="cf-inline" @click="emit('report')">Report a problem</button> instead and the money stays held.</span>
      <span v-else class="cf-p num">Confirming releases <strong>{{ naira(deal.amount) }}</strong> to {{ deal.seller_first_name }}. If anything’s wrong, <button type="button" class="cf-inline" @click="emit('report')">report a problem</button> instead.</span>
      <label class="cf-check">
        <input v-model="checked" type="checkbox" data-autofocus />
        <span>{{ sheet ? 'I have it in my hands and I’ve checked it.' : 'I have the item in my hands and I’ve checked it.' }}</span>
      </label>
      <p v-if="error" class="cf-error" role="alert">{{ error }}</p>
      <div v-if="!sheet" class="cf-btns">
        <button type="button" class="cf-no" @click="emit('close')">Not yet</button>
        <button type="button" class="cf-yes num" :disabled="!checked || busy" @click="emit('confirm')">Yes, release {{ naira(deal.amount) }}</button>
      </div>
      <template v-else>
        <button type="button" class="cf-yes num" :disabled="!checked || busy" @click="emit('confirm')">Yes, release {{ naira(deal.amount) }}</button>
        <button type="button" class="cf-no cf-no--m" @click="emit('close')">Not yet</button>
      </template>
    </div>
  </ModalPanel>
</template>

<style scoped>
.cf {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cf--m {
  gap: 14px;
}

.cf-k {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: #a3361f;
}

.cf-h {
  margin: -8px 0 0;
  font-size: 38px;
  line-height: 1.02;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.cf-p {
  font-size: 16px;
  line-height: 1.55;
  color: var(--ink-2);
}

.cf-p strong {
  color: var(--ink);
}

.cf-inline {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.cf-check {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  background: #ffffff;
  border-radius: 12px;
  font-size: 15px;
  line-height: 1.45;
  cursor: pointer;
}

.cf-check input {
  width: 22px;
  height: 22px;
  margin: 0;
  accent-color: var(--forest);
  flex-shrink: 0;
}

.cf-error {
  margin: 0;
  font-size: 14px;
  color: #a3361f;
}

.cf-btns {
  display: grid;
  grid-template-columns: 1fr 1.6fr;
  gap: 10px;
}

.cf-no {
  height: 58px;
  border: 1.5px solid rgba(18, 20, 16, 0.3);
  background: transparent;
  border-radius: 14px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
}

.cf-yes {
  height: 58px;
  border: 0;
  background: var(--forest);
  color: var(--paper);
  border-radius: 14px;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
}

.cf-yes:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cf--m .cf-k {
  font-size: 10px;
  letter-spacing: 0.12em;
}

.cf--m .cf-h {
  margin-top: -6px;
  font-size: 28px;
  line-height: 1.05;
}

.cf--m .cf-p {
  font-size: 14px;
  line-height: 1.5;
}

.cf--m .cf-check {
  gap: 10px;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.4;
}

.cf--m .cf-yes {
  height: 56px;
  font-size: 16px;
}

.cf-no--m {
  height: 48px;
  border: 0;
  font-size: 15px;
}
</style>
