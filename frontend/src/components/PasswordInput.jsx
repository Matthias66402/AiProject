import { useState } from 'react'

// Passwortfeld mit "Auge"-Button zum Ein-/Ausblenden des Klartexts. Alle
// übrigen Props (id, value, onChange, required, autoComplete ...) gehen
// unverändert an das <input>. Wrapper ist bewusst ein <span>, weil
// "form div" (style.css) jedes <div> im Formular als Spalte stapelt.
export default function PasswordInput(props) {
    const [visible, setVisible] = useState(false)

    return (
        <span className="password-field">
            <input {...props} type={visible ? 'text' : 'password'} />
            <button
                type="button"
                className="password-toggle"
                onClick={() => setVisible((v) => !v)}
                aria-label={
                    visible ? 'Passwort verbergen' : 'Passwort anzeigen'
                }
                title={visible ? 'Passwort verbergen' : 'Passwort anzeigen'}
            >
                <i
                    className={`fa-solid ${visible ? 'fa-eye-slash' : 'fa-eye'}`}
                />
            </button>
        </span>
    )
}
