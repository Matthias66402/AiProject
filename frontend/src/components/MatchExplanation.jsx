import { useState } from 'react'
import { apiGet } from '../api/client'

// "Warum passt das?" unter einem Treffer (Stellen-Detailseite, Meine
// Lebensläufe): lädt die KI-Begründung erst beim ersten Aufklappen
// (GET /api/jobs/<jobId>/match-explanation/<resumeId>, serverseitig
// zwischengespeichert) und behält sie danach für erneutes Aufklappen.
export default function MatchExplanation({ jobId, resumeId }) {
    const [open, setOpen] = useState(false)
    const [explanation, setExplanation] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    async function toggle() {
        const next = !open
        setOpen(next)
        if (!next || explanation || loading) return
        setLoading(true)
        setError('')
        try {
            setExplanation(
                await apiGet(
                    `/api/jobs/${jobId}/match-explanation/${resumeId}`,
                ),
            )
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="match-explain">
            <button
                type="button"
                className="link-button match-explain-toggle"
                onClick={toggle}
                aria-expanded={open}
            >
                <i
                    className={`fa-solid ${open ? 'fa-chevron-up' : 'fa-circle-question'}`}
                />{' '}
                {open ? 'Begründung ausblenden' : 'Warum passt das?'}
            </button>
            {open && (
                <div className="match-explain-body">
                    {loading && (
                        <p className="match-explain-summary">
                            <span className="spinner spinner-small" />{' '}
                            Begründung wird erstellt …
                        </p>
                    )}
                    {error && <p className="form-error">{error}</p>}
                    {explanation && (
                        <>
                            <p className="match-explain-summary">
                                {explanation.summary}
                            </p>
                            {explanation.matches.length > 0 && (
                                <>
                                    <span className="match-explain-label">
                                        Passt
                                    </span>
                                    <ul className="match-explain-list ok">
                                        {explanation.matches.map((item) => (
                                            <li key={item}>{item}</li>
                                        ))}
                                    </ul>
                                </>
                            )}
                            {explanation.gaps.length > 0 && (
                                <>
                                    <span className="match-explain-label">
                                        Fehlt
                                    </span>
                                    <ul className="match-explain-list gap">
                                        {explanation.gaps.map((item) => (
                                            <li key={item}>{item}</li>
                                        ))}
                                    </ul>
                                </>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    )
}
