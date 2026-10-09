import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { apiGet, apiPost } from '../api/client'
import LoginForm from '../components/LoginForm'

export default function HomePage() {
    const { user } = useOutletContext()
    const [models, setModels] = useState(null)
    const [model, setModel] = useState('')
    const [question, setQuestion] = useState('')
    const [answer, setAnswer] = useState('Die KI wartet auf deine Frage ...')
    const [asking, setAsking] = useState(false)
    const [error, setError] = useState('')

    useEffect(() => {
        apiGet('/api/assistant')
            .then((data) => {
                setModels(data.models)
                setModel(data.default_model)
            })
            .catch((err) => setError(err.message))
    }, [])

    async function handleSubmit(e) {
        e.preventDefault()
        setAsking(true)
        setError('')
        setAnswer('')
        try {
            const data = await apiPost('/api/assistant/ask', {
                question,
                model,
            })
            setAnswer(data.answer)
            setModel(data.model)
        } catch (err) {
            setError(err.message)
        } finally {
            setAsking(false)
        }
    }

    return (
        // Ausgeloggt zwei eigenständige Karten nebeneinander (Layout-Regeln wie
        // bei den Detailseiten): links der KI-Assistent, rechts der Login - auf
        // schmalen Bildschirmen rutscht der Login darunter. Eingeloggt bleibt
        // es eine Karte in voller Breite.
        <div className="detail-layout">
            <div
                className="scroll full"
                style={{ flex: '999 1 560px', minWidth: 0 }}
            >
                <h1 id="greetings"><span className="wand">🪄</span> KI-Assistent</h1>
                <p className="subtitle">Wie kann ich Dir helfen?</p>
                {/* Karte in voller Breite wie die übrigen Seiten, das Formular
                    selbst bleibt schmal - eine einzeilige Frage über 1200px
                    liest sich schlecht. */}
                <div style={{ maxWidth: 640 }}>
                    {error && <p className="form-error">{error}</p>}
                    <form onSubmit={handleSubmit}>
                        <div>
                            <label htmlFor="name-input">Deine Frage</label>
                            <input
                                id="name-input"
                                type="text"
                                value={question}
                                onChange={(e) => setQuestion(e.target.value)}
                                placeholder="Was möchtest du wissen?"
                            />
                        </div>
                        <div>
                            <label htmlFor="wizard-select">
                                Welches KI-Modell?
                            </label>
                            <select
                                id="wizard-select"
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                disabled={!models}
                            >
                                {models &&
                                    Object.entries(models).map(
                                        ([modelId, label]) => (
                                            <option
                                                key={modelId}
                                                value={modelId}
                                            >
                                                {label}
                                            </option>
                                        ),
                                    )}
                            </select>
                        </div>
                        <button
                            id="special-btn"
                            type="submit"
                            disabled={asking || !question.trim()}
                        >
                            ✨ Anfrage
                        </button>
                    </form>
                    <div className="answer-wrap">
                        <p id="answer">{answer}</p>
                        <div
                            className={`generating-indicator${asking ? ' visible' : ''}`}
                        >
                            <span className="spinner" />
                        </div>
                    </div>
                </div>
            </div>
            {user === null && (
                <div
                    className="scroll"
                    style={{ flex: '1 1 340px', minWidth: 0 }}
                >
                    <div className="side-panel-head">
                        <span className="icon-circle">
                            <i className="fa-solid fa-right-to-bracket" />
                        </span>
                        <div>
                            <h2>Anmelden</h2>
                            <div className="side-panel-hint">
                                Für Lebenslauf-Matching und eigene
                                Stellenangebote
                            </div>
                        </div>
                    </div>
                    <LoginForm idPrefix="home-login-" />
                    <p className="side-panel-hint">
                        Noch kein Konto?{' '}
                        <Link to="/register">Jetzt registrieren</Link>
                    </p>
                </div>
            )}
        </div>
    )
}
