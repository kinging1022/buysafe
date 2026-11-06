// Small fetch wrapper for the Django API (same origin: Vite proxies /api in dev).
// Auth is a Django session cookie (httpOnly); POSTs carry the CSRF token.

function cookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : ''
}

async function ensureCsrf() {
  if (!cookie('csrftoken')) await fetch('/api/auth/csrf/', { credentials: 'same-origin' })
}

/**
 * Returns { ok, status, data }. Never throws: a network failure comes back as
 * status 0 so views can show a general error.
 */
export async function api(path, { method = 'GET', body } = {}) {
  try {
    if (method !== 'GET') await ensureCsrf()
    const res = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(method !== 'GET' ? { 'X-CSRFToken': cookie('csrftoken') } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
    let data = null
    try {
      data = await res.json()
    } catch {
      // empty or non-JSON body
    }
    return { ok: res.ok, status: res.status, data }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}

/**
 * Multipart upload (FormData) with progress, for forms that carry photos.
 * Same result shape as api(). onProgress receives 0–1 while the body uploads.
 */
export async function upload(path, formData, { method = 'POST', onProgress } = {}) {
  await ensureCsrf()
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open(method, `/api${path}`)
    xhr.withCredentials = true
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.setRequestHeader('X-CSRFToken', cookie('csrftoken'))
    if (onProgress) {
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      let data = null
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        // empty or non-JSON body
      }
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data })
    }
    xhr.onerror = xhr.onabort = () => resolve({ ok: false, status: 0, data: null })
    xhr.send(formData)
  })
}

/**
 * PUT raw bytes (one chunk of a resumable upload). Same result shape as api().
 * `headers` carries e.g. Content-Range.
 */
export async function putBytes(path, blob, headers = {}) {
  try {
    await ensureCsrf()
    const res = await fetch(`/api${path}`, {
      method: 'PUT',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/octet-stream',
        'X-CSRFToken': cookie('csrftoken'),
        ...headers,
      },
      body: blob,
    })
    let data = null
    try {
      data = await res.json()
    } catch {
      // empty or non-JSON body
    }
    return { ok: res.ok, status: res.status, data }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}
