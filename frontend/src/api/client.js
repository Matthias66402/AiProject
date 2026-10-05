// ?? statt ||: ein leerer Wert ("") bleibt erhalten und ergibt relative Pfade (gleiche
// Origin, z.B. hinter einem Reverse-Proxy); nur ein fehlender Wert fällt auf localhost zurück.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5003'

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: isFormData ? undefined : { 'Content-Type': 'application/json' },
    ...options,
  })

  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    const error = new Error((data && data.error) || `Anfrage fehlgeschlagen (${response.status})`)
    error.status = response.status
    error.data = data
    throw error
  }
  return data
}

export const apiGet = (path) => request(path)
export const apiPost = (path, body) =>
  request(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body) })
export const apiPut = (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body) })
export const apiDelete = (path) => request(path, { method: 'DELETE' })
