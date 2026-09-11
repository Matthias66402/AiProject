import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api/client'

export default function HomePage() {
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
        <div style={{ maxWidth: 560, margin: '0 auto' }}>
            <h1 id="greetings"><span className="wand">🪄</span> KI-Assistent</h1>
            <p className="subtitle">Wie kann ich Dir helfen?</p>
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
                    <label htmlFor="wizard-select">Welches KI-Modell?</label>
                    <select
                        id="wizard-select"
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        disabled={!models}
                    >
                        {models &&
                            Object.entries(models).map(([modelId, label]) => (
                                <option key={modelId} value={modelId}>
                                    {label}
                                </option>
                            ))}
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
    )
}
