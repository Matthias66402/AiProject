import { useState } from 'react'
import { API_BASE } from '../api/client'

export default function JobUploadDropzone({ onExtracted }) {
  const [fileName, setFileName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)

  async function processFile(file) {
    if (!file) return
    setFileName(file.name)
    setError('')
    setBusy(true)

    const formData = new FormData()
    formData.append('job_file', file)

    try {
      const response = await fetch(`${API_BASE}/jobs/extract-upload`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })
      const data = await response.json()
      if (!response.ok) {
        setError(data.error || 'Die Datei konnte nicht verarbeitet werden.')
        return
      }
      onExtracted(data)
    } catch {
      setError('Die Datei konnte nicht verarbeitet werden. Bitte später erneut versuchen.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="textarea-wrap">
      <label
        className={`dropzone${dragOver ? ' dragover' : ''}`}
        htmlFor="job_file_input"
        onDragEnter={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={(e) => {
          e.preventDefault()
          setDragOver(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          const file = e.dataTransfer.files?.[0]
          if (file) processFile(file)
        }}
      >
        <input
          className="dropzone-input"
          type="file"
          id="job_file_input"
          accept=".pdf,.docx,.odt"
          onChange={(e) => processFile(e.target.files?.[0])}
        />
        <i className="fa-solid fa-cloud-arrow-up dropzone-icon" />
        <span className="dropzone-text">
          {fileName || 'Stellenangebot-Dokument hierher ziehen oder klicken zum Auswählen'}
        </span>
        <span className="dropzone-hint">PDF, .docx oder .odt · befüllt Position, PLZ, Stadt und Beschreibung automatisch</span>
      </label>
      <div className={`generating-indicator${busy ? ' visible' : ''}`}>
        <span className="spinner" />
        Dokument wird verarbeitet …
      </div>
      {error && <p className="form-error">{error}</p>}
    </div>
  )
}
