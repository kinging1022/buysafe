// Shrinks a photo in the browser before upload: max 2000px on the long edge,
// camera rotation applied, re-encoded as JPEG. The server re-encodes again and
// strips all metadata, so this only saves the seller's data and time.
const MAX_EDGE = 2000
const QUALITY = 0.85

export const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024

export async function shrinkImage(file) {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))
    const width = Math.round(bitmap.width * scale)
    const height = Math.round(bitmap.height * scale)
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#ffffff' // transparent PNGs become white, not black
    ctx.fillRect(0, 0, width, height)
    ctx.drawImage(bitmap, 0, 0, width, height)
    bitmap.close?.()
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY))
    if (!blob || blob.size >= file.size) return file // keep the original if it's already smaller
    return new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' })
  } catch {
    return file // older browsers: send as-is; the server still checks and shrinks it
  }
}
