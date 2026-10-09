import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { apiPost } from '../api/client'

// Login-Formular für die Login-Seite und das Login-Panel auf der Startseite.
// idPrefix hält die Feld-IDs eindeutig, wenn das Formular neben anderen
// Formularen steht (Startseite: KI-Assistent hat bereits id="special-btn").
export default function LoginForm({ idPrefix = '', onLoggedIn }) {
    const { refreshUser } = useOutletContext()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [saving, setSaving] = useState(false)

    async function handleSubmit(e) {
        e.preventDefault()
        setSaving(true)
        setError('')
        try {
            await apiPost('/api/auth/login', { email, password })
            await refreshUser()
            onLoggedIn?.()
        } catch (err) {
            setError(err.message)
            setSaving(false)
        }
    }

    return (
        <>
            {error && <p className="form-error">{error}</p>}
            <form onSubmit={handleSubmit}>
                <div>
                    <label htmlFor={`${idPrefix}email`}>E-Mail</label>
                    <input
                        id={`${idPrefix}email`}
                        type="email"
                        autoComplete="username"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                    />
                </div>
                <div>
                    <label htmlFor={`${idPrefix}password`}>Passwort</label>
                    <input
                        id={`${idPrefix}password`}
                        type="password"
                        autoComplete="current-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                </div>
                <button
                    id={idPrefix ? undefined : 'special-btn'}
                    className={idPrefix ? 'special-btn' : undefined}
                    type="submit"
                    disabled={saving}
                >
                    Anmelden
                </button>
            </form>
        </>
    )
}
