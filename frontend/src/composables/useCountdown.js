import { onBeforeUnmount, ref, toValue, watch } from 'vue'

/**
 * Seconds left on a deal deadline, ticking every second. The server sends
 * awake seconds (`seconds`) and whether quiet hours pause the clock
 * (`paused`); each new value from a poll resets the count.
 */
export function useCountdown(seconds, paused) {
  const left = ref(toValue(seconds) ?? 0)
  let base = { at: Date.now(), value: left.value }
  const timer = setInterval(() => {
    if (toValue(paused)) {
      base = { at: Date.now(), value: left.value }
      return
    }
    left.value = Math.max(0, base.value - (Date.now() - base.at) / 1000)
  }, 1000)
  watch(
    () => toValue(seconds),
    (value) => {
      left.value = value ?? 0
      base = { at: Date.now(), value: left.value }
    },
  )
  onBeforeUnmount(() => clearInterval(timer))
  return left
}
