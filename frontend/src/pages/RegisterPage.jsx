import { useState } from 'react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import { apiPost } from '../api/client'

export default function RegisterPage() {
    const { refreshUser } = useOutletContext()
    const navigate = useNavigate()
    const [values, setValues] = useState({
        first_name: '',
        last_name: '',
        short_name: '',
        email: '',
        zip: '',
        city: '',
        password: '',
        password_confirm: '',
    })
    const [error, setError] = useState('')
    const [saving, setSaving] = useState(false)

    function set(field, value) {
        setValues((v) => ({ ...v, [field]: value }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        setSaving(true)
        setError('')
        try {
            await apiPost('/api/auth/register', values)
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
            <h1 id="greetings">Registrieren</h1>
            <p className="subtitle">Erstelle ein neues Konto</p>

            {error && <p className="form-error">{error}</p>}

            <form onSubmit={handleSubmit}>
                <div>
                    <label htmlFor="first_name">Vorname</label>
                    <input
                        id="first_name"
                        type="text"
                        value={values.first_name}
                        onChange={(e) => set('first_name', e.target.value)}
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
                        required
                    />
                </div>
                <div>
                    <label htmlFor="city">Stadt</label>
                    <input
                        id="city"
                        type="text"
                        value={values.city}
                        onChange={(e) => set('city', e.target.value)}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="password">Passwort</label>
                    <input
                        id="password"
                        type="password"
                        value={values.password}
                        onChange={(e) => set('password', e.target.value)}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="password_confirm">
                        Passwort wiederholen
                    </label>
                    <input
                        id="password_confirm"
                        type="password"
                        value={values.password_confirm}
                        onChange={(e) =>
                            set('password_confirm', e.target.value)
                        }
                        required
                    />
                </div>
                <button id="special-btn" type="submit" disabled={saving}>
                    Registrieren
                </button>
            </form>
            <p className="subtitle">
                Bereits registriert? <Link to="/login">Jetzt anmelden</Link>
            </p>
        </div>
    )
}
