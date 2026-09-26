// Only same-site paths are allowed as ?redirect= targets.
export function safeRedirect(value, fallback = '/') {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : fallback
}
