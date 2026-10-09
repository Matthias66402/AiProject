import { useState } from 'react'
import { Link } from 'react-router-dom'
import { API_BASE } from '../api/client'
import PasswordInput from './PasswordInput'

export default function UserForm({
    roles,
    customers,
    initial,
    resumes,
    onSubmit,
    submitLabel,
    cancelTo,
    // Fremder Nutzer-Eintrag: nur Rolle (inkl. Stellenanbieter) änderbar,
    // Stammdaten schreibgeschützt, kein Passwortfeld.
    roleOnly = false,
    // Eigenes Profil (Konto-Menü -> 'Bearbeiten'): Rolle und Stellenanbieter
    // weder sichtbar noch änderbar, werden auch nicht mitgeschickt.
    hideRole = false,
}) {
    const isEdit = Boolean(initial)
    const [values, setValues] = useState({
        first_name: initial?.first_name || '',
        last_name: initial?.last_name || '',
        short_name: initial?.short_name || '',
        email: initial?.email || '',
        zip: initial?.zip || '',
        city: initial?.city || '',
        role: initial?.role || 'user',
        customer_id: initial?.customer_id || '',
        password: '',
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
            if (hideRole) {
                const { role, customer_id, ...rest } = values
                await onSubmit(rest)
            } else {
                await onSubmit(values)
            }
        } catch (err) {
            setError(err.message)
        } finally {
            setSaving(false)
        }
    }

    return (
        <form onSubmit={handleSubmit}>
            {error && <p className="form-error">{error}</p>}
            <div className="form-grid">
                <div>
                    <label htmlFor="first_name">Vorname</label>
                    <input
                        id="first_name"
                        type="text"
                        value={values.first_name}
                        onChange={(e) => set('first_name', e.target.value)}
                        readOnly={roleOnly}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="last_name">Nachname</label>
                    <input
                        id="last_name"
                        type="text"
                        value={values.last_name}
                        onChange={(e) => set('last_name', e.target.value)}
                        readOnly={roleOnly}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="short_name">Kurzname</label>
                    <input
                        id="short_name"
                        type="text"
                        value={values.short_name}
                        onChange={(e) => set('short_name', e.target.value)}
                        readOnly={roleOnly}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="email">E-Mail</label>
                    <input
                        id="email"
                        type="email"
                        value={values.email}
                        onChange={(e) => set('email', e.target.value)}
                        readOnly={roleOnly}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="zip">PLZ</label>
                    <input
                        id="zip"
                        type="text"
                        value={values.zip}
                        onChange={(e) => set('zip', e.target.value)}
                        readOnly={roleOnly}
                    />
                </div>
                <div>
                    <label htmlFor="city">Stadt</label>
                    <input
                        id="city"
                        type="text"
                        value={values.city}
                        onChange={(e) => set('city', e.target.value)}
                        readOnly={roleOnly}
                    />
                </div>
                {!hideRole && (
                    <div>
                        <label htmlFor="role">Rolle</label>
                        <select
                            id="role"
                            value={values.role}
                            onChange={(e) => set('role', e.target.value)}
                        >
                            {roles.map((role) => (
                                <option key={role} value={role}>
                                    {role}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
                {!hideRole && values.role === 'customer' && (
                    <div>
                        <label htmlFor="customer_id">Stellenanbieter</label>
                        <select
                            id="customer_id"
                            value={values.customer_id}
                            onChange={(e) => set('customer_id', e.target.value)}
                        >
                            <option value="">
                                Kein Stellenanbieter zugeordnet
                            </option>
                            {customers.map((customer) => (
                                <option key={customer.id} value={customer.id}>
                                    {customer.company_name}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
            </div>
            {isEdit && resumes && resumes.length > 0 && (
                <div>
                    <label>Lebensläufe</label>
                    <ul>
                        {resumes.map((resume) => (
                            <li key={resume.id}>
                                <a
                                    href={API_BASE + resume.document_link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    Lebenslauf vom{' '}
                                    {resume.created_at
                                        ? resume.created_at.slice(0, 10)
                                        : '-'}
                                </a>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            {!roleOnly && (
                <div>
                    <label htmlFor="password">
                        {isEdit ? 'Neues Passwort (optional)' : 'Passwort'}
                    </label>
                    <PasswordInput
                        id="password"
                        value={values.password}
                        onChange={(e) => set('password', e.target.value)}
                        required={!isEdit}
                    />
                </div>
            )}
            <div className="form-actions">
                <button
                    className={isEdit ? 'subtle-btn' : 'special-btn'}
                    type="submit"
                    disabled={saving}
                >
                    {submitLabel}
                </button>
                {cancelTo && (
                    <Link
                        className="subtle-btn cancel cancel-link"
                        to={cancelTo}
                    >
                        <i className="fa-solid fa-xmark" /> Abbrechen
                    </Link>
                )}
            </div>
        </form>
    )
}
