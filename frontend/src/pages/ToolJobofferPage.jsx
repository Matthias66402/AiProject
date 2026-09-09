import { useEffect, useState } from 'react'
import { API_BASE, apiGet, apiPost } from '../api/client'

export default function ToolJobofferPage() {
  const [customers, setCustomers] = useState(null)
  const [customerId, setCustomerId] = useState('')
  const [spec, setSpec] = useState('')
  const [generating, setGenerating] = useState(false)
  const [message, setMessage] = useState('')
  const [fileUrl, setFileUrl] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    apiGet('/api/customers?per_page=50')
      .then((data) => setCustomers(data.customers))
      .catch((err) => setError(err.message))
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!spec.trim() || !customerId) {
      setError('Bitte zuerst einen Stellenanbieter wählen und beschreiben, was das Stellenangebot enthalten soll.')
      return
    }
    setGenerating(true)
    setError('')
    setMessage('')
    setFileUrl('')
    try {
      const data = await apiPost('/api/tools/joboffer', { customer_id: customerId, spec })
      setFileUrl(data.file_url)
      setMessage('Stellenangebot wurde erstellt und als Stelle angelegt:')
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  if (error && !customers) return <p className="form-error">{error}</p>
  if (!customers) return <p>Lade …</p>

  return (
    <div className="scroll wide">
      <h1 id="greetings">Stellenangebot generieren</h1>
      <p className="subtitle">Bitte spezifieren Sie, was das Stellenangebot enthalten soll:</p>
      {error && <p className="form-error">{error}</p>}
      {message && (
        <p className="subtitle">
          {message}{' '}
          {fileUrl && (
            <a href={API_BASE + fileUrl} target="_blank" rel="noopener noreferrer">
              Stellenangebot öffnen
            </a>
          )}
        </p>
      )}
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="customer_id">Stellenanbieter</label>
          <select id="customer_id" value={customerId} onChange={(e) => setCustomerId(e.target.value)} required>
            <option value="" disabled>
              Bitte wählen
            </option>
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.company_name}
              </option>
            ))}
          </select>
        </div>
        <div className="textarea-wrap">
          <textarea className="p-3" rows={8} value={spec} onChange={(e) => setSpec(e.target.value)} />
          <div className={`generating-indicator${generating ? ' visible' : ''}`}>
            <span className="spinner" />
            Stellenangebot wird generiert …
          </div>
        </div>
        <button className="subtle-btn" type="submit" disabled={generating}>
          Generieren
        </button>
      </form>
    </div>
  )
}
