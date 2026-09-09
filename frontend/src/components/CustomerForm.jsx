import { useState } from 'react'

export default function CustomerForm({ initial, onSubmit, submitLabel }) {
  const [values, setValues] = useState({
    company_name: initial?.company_name || '',
    street: initial?.street || '',
    street_number: initial?.street_number || '',
    zip: initial?.zip || '',
    city: initial?.city || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function set(field, value) {
    setValues((v) => ({ ...v, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSubmit(values)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <p className="form-error">{error}</p>}
      <div>
        <label htmlFor="company_name">Firma</label>
        <input id="company_name" type="text" value={values.company_name} onChange={(e) => set('company_name', e.target.value)} required />
      </div>
      <div>
        <label htmlFor="street">Straße</label>
        <input id="street" type="text" value={values.street} onChange={(e) => set('street', e.target.value)} required />
      </div>
      <div>
        <label htmlFor="street_number">Hausnummer</label>
        <input id="street_number" type="text" value={values.street_number} onChange={(e) => set('street_number', e.target.value)} required />
      </div>
      <div>
        <label htmlFor="zip">PLZ</label>
        <input id="zip" type="text" value={values.zip} onChange={(e) => set('zip', e.target.value)} required />
      </div>
      <div>
        <label htmlFor="city">Stadt</label>
        <input id="city" type="text" value={values.city} onChange={(e) => set('city', e.target.value)} required />
      </div>
      <button className="subtle-btn" type="submit" disabled={saving}>
        {submitLabel}
      </button>
    </form>
  )
}
