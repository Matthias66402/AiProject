import { useState } from 'react'
import { API_BASE } from '../api/client'
import JobUploadDropzone from './JobUploadDropzone'
import RichTextEditor from './RichTextEditor'

export default function JobForm({
    mode,
    initial,
    isAdmin,
    customers,
    ownCustomerName,
    onSubmit,
    submitLabel,
}) {
    const [values, setValues] = useState({
        position: initial?.position || '',
        customer_id: initial?.customer_id || '',
        zip: initial?.zip || '',
        city: initial?.city || '',
        content: initial?.content || '',
        valid_from: initial?.valid_from || '',
        valid_until: initial?.valid_until || '',
        document_link: initial?.document_link || '',
    })
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState('')

    function set(field, value) {
        setValues((v) => ({ ...v, [field]: value }))
    }

    function handleExtracted(data) {
        setValues((v) => ({
            ...v,
            position: data.position || v.position,
            zip: data.zip || v.zip,
            city: data.city || v.city,
            content: data.content || v.content,
            document_link: data.document_link || v.document_link,
        }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        if (!values.content) {
            setError('Bitte eine Beschreibung eingeben.')
            return
        }
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
            {mode === 'create' && (
                <JobUploadDropzone onExtracted={handleExtracted} />
            )}
            {error && <p className="form-error">{error}</p>}
            <div>
                <label htmlFor="position">Position</label>
                <input
                    id="position"
                    type="text"
                    value={values.position}
                    onChange={(e) => set('position', e.target.value)}
                    required
                />
            </div>
            <div>
                <label htmlFor="customer_id">Kunde</label>
                {isAdmin ? (
                    <select
                        id="customer_id"
                        value={values.customer_id}
                        onChange={(e) => set('customer_id', e.target.value)}
                        required
                    >
                        <option value="" disabled>
                            Bitte wählen
                        </option>
                        {customers.map((c) => (
                            <option key={c.id} value={c.id}>
                                {c.company_name}
                            </option>
                        ))}
                    </select>
                ) : (
                    <p>{ownCustomerName || '-'}</p>
                )}
            </div>
            <div>
                <label htmlFor="zip">PLZ</label>
                <input
                    id="zip"
                    type="text"
                    value={values.zip}
                    onChange={(e) => set('zip', e.target.value)}
                />
            </div>
            <div>
                <label htmlFor="city">Stadt</label>
                <input
                    id="city"
                    type="text"
                    value={values.city}
                    onChange={(e) => set('city', e.target.value)}
                />
            </div>
            {values.document_link && (
                <div>
                    <label>Dokument</label>
                    <p>
                        <a
                            href={API_BASE + values.document_link}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            Dokument öffnen
                        </a>
                    </p>
                </div>
            )}
            <div>
                <label htmlFor="content">Beschreibung</label>
                <RichTextEditor
                    value={values.content}
                    onChange={(html) => set('content', html)}
                />
            </div>
            <div>
                <label htmlFor="valid_from">Gültig von</label>
                <input
                    id="valid_from"
                    type="date"
                    value={values.valid_from || ''}
                    onChange={(e) => set('valid_from', e.target.value)}
                />
            </div>
            <div>
                <label htmlFor="valid_until">Gültig bis</label>
                <input
                    id="valid_until"
                    type="date"
                    value={values.valid_until || ''}
                    onChange={(e) => set('valid_until', e.target.value)}
                />
            </div>
            <button className="subtle-btn" type="submit" disabled={saving}>
                {submitLabel}
            </button>
        </form>
    )
}
