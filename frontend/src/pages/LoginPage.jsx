import { useState } from 'react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import { apiPost } from '../api/client'

export default function LoginPage() {
    const { refreshUser } = useOutletContext()
    const navigate = useNavigate()
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
            navigate('/')
        } catch (err) {
            setError(err.message)
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="scroll">
            <h1 id="greetings">Anmelden</h1>
            <p className="subtitle">Melde dich mit deinen Zugangsdaten an</p>

            {error && <p className="form-error">{error}</p>}

            <form onSubmit={handleSubmit}>
                <div>
                    <label htmlFor="email">E-Mail</label>
                    <input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="password">Passwort</label>
                    <input
                        id="password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                </div>
                <button id="special-btn" type="submit" disabled={saving}>
                    Anmelden
                </button>
            </form>
            <p className="subtitle">
                Noch kein Konto? <Link to="/register">Jetzt registrieren</Link>
            </p>
        </div>
    )
}
