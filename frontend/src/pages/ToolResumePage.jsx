import { useEffect, useState } from 'react'
import { API_BASE, apiGet, apiPost } from '../api/client'

export default function ToolResumePage() {
    const [users, setUsers] = useState(null)
    const [userId, setUserId] = useState('')
    const [spec, setSpec] = useState('')
    const [generating, setGenerating] = useState(false)
    const [message, setMessage] = useState('')
    const [fileUrl, setFileUrl] = useState('')
    const [error, setError] = useState('')

    useEffect(() => {
        apiGet('/api/users')
            .then((data) => setUsers(data.users))
            .catch((err) => setError(err.message))
    }, [])

    async function handleSubmit(e) {
        e.preventDefault()
        if (!spec.trim() || !userId) {
            setError(
                'Bitte zuerst einen Nutzer wählen und beschreiben, was der Lebenslauf enthalten soll.',
            )
            return
        }
        setGenerating(true)
        setError('')
        setMessage('')
        setFileUrl('')
        try {
            const data = await apiPost('/api/tools/resume', {
                user_id: userId,
                spec,
            })
            setFileUrl(data.file_url)
            setMessage('Lebenslauf wurde erstellt und dem Nutzer zugeordnet:')
        } catch (err) {
            setError(err.message)
        } finally {
            setGenerating(false)
        }
    }

    if (error && !users) return <p className="form-error">{error}</p>
    if (!users) return <p>Lade …</p>

    return (
        <div className="scroll wide">
            <h1 id="greetings">Lebenslauf generieren</h1>
            <p className="subtitle">
                Bitte spezifieren Sie, was der Lebenslauf enthalten soll:
            </p>
            {error && <p className="form-error">{error}</p>}
            {message && (
                <p className="subtitle">
                    {message}{' '}
                    {fileUrl && (
                        <a
                            href={API_BASE + fileUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            Lebenslauf öffnen
                        </a>
                    )}
                </p>
            )}
            <form onSubmit={handleSubmit}>
                <div>
                    <label htmlFor="user_id">Nutzer</label>
                    <select
                        id="user_id"
                        value={userId}
                        onChange={(e) => setUserId(e.target.value)}
                        required
                    >
                        <option value="" disabled>
                            Bitte wählen
                        </option>
                        {users.map((user) => (
                            <option key={user.id} value={user.id}>
                                {user.first_name} {user.last_name} (
                                {user.short_name})
                            </option>
                        ))}
                    </select>
                </div>
                <div className="textarea-wrap">
                    <textarea
                        className="p-3"
                        rows={8}
                        value={spec}
                        onChange={(e) => setSpec(e.target.value)}
                    />
                    <div
                        className={`generating-indicator${generating ? ' visible' : ''}`}
                    >
                        <span className="spinner" />
                        Lebenslauf wird generiert …
                    </div>
                </div>
                <button
                    className="subtle-btn"
                    type="submit"
                    disabled={generating}
                >
                    Generieren
                </button>
            </form>
        </div>
    )
}
