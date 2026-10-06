import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../api/client'
import { formatDate } from './JobTable'

// Längere Positionsnamen in der Versionsauswahl kürzen, damit die Auswahl in
// die schmale Seitenspalte passt (voller Text steht im title-Attribut).
const MAX_POSITION_CHARS = 28

function resumeLabel(resume) {
    const date = formatDate(resume.created_at)
    if (!resume.target_job_position) return date
    const position = resume.target_job_position
    const short =
        position.length > MAX_POSITION_CHARS
            ? `${position.slice(0, MAX_POSITION_CHARS).trimEnd()}…`
            : position
    return `${date} · angepasst für ${short}`
}

function resumeTitle(resume) {
    const date = formatDate(resume.created_at)
    return resume.target_job_position
        ? `${date} · angepasst für ${resume.target_job_position}`
        : date
}

// Seitenspalte der Stellen-Detailseite für Rolle 'user': eigene Lebenslauf-
// Version wählen und per KI auf diese Stelle zuschneiden lassen. Der Entwurf
// selbst (Vorschau, Übernehmen/Verwerfen) wird in JobEditPage angezeigt.
export default function TailorResumePanel({ jobId, reloadKey, onDraft }) {
    const [resumes, setResumes] = useState(null)
    const [resumeId, setResumeId] = useState('')
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')

    useEffect(() => {
        apiGet('/api/resumes')
            .then((data) => {
                setResumes(data.resumes)
                // Vorbelegt: neueste allgemeine Version (Liste ist neueste zuerst).
                const base =
                    data.resumes.find((r) => !r.target_job_id) ||
                    data.resumes[0]
                setResumeId(base ? String(base.id) : '')
            })
            .catch((err) => setError(err.message))
    }, [reloadKey])

    async function handleTailor() {
        setBusy(true)
        setError('')
        try {
            const draft = await apiPost('/api/resumes/tailor/preview', {
                resume_id: Number(resumeId),
                job_id: jobId,
            })
            onDraft(draft)
        } catch (err) {
            setError(err.message)
        } finally {
            setBusy(false)
        }
    }

    const tailoredForJob = resumes?.find((r) => r.target_job_id === jobId)
    const selectedResume = resumes?.find((r) => String(r.id) === resumeId)

    return (
        <section className="side-panel">
            <div className="side-panel-head">
                <span className="icon-circle">
                    <i className="fa-solid fa-wand-magic-sparkles" />
                </span>
                <div>
                    <h2>Lebenslauf anpassen</h2>
                    <div className="side-panel-hint">
                        Auf diese Stelle zugeschnitten - ohne etwas zu erfinden
                    </div>
                </div>
            </div>

            {error && <p className="form-error">{error}</p>}

            {resumes === null ? (
                <p className="side-empty">Lade …</p>
            ) : resumes.length === 0 ? (
                <p className="side-empty">
                    Du hast noch keinen Lebenslauf.{' '}
                    <Link to="/resumes">Lebenslauf hochladen</Link>
                </p>
            ) : (
                <div className="tailor-controls">
                    {tailoredForJob && (
                        <p className="side-empty">
                            <i className="fa-solid fa-circle-check" /> Bereits
                            angepasst am {formatDate(tailoredForJob.created_at)}{' '}
                            · <Link to="/resumes">ansehen</Link>
                        </p>
                    )}
                    <label htmlFor="tailor-resume">Ausgangsversion</label>
                    <select
                        id="tailor-resume"
                        title={
                            selectedResume ? resumeTitle(selectedResume) : ''
                        }
                        value={resumeId}
                        onChange={(e) => setResumeId(e.target.value)}
                        disabled={busy}
                    >
                        {resumes.map((r) => (
                            <option
                                key={r.id}
                                value={r.id}
                                title={resumeTitle(r)}
                            >
                                {resumeLabel(r)}
                            </option>
                        ))}
                    </select>
                    <button
                        type="button"
                        className="special-btn"
                        onClick={handleTailor}
                        disabled={busy || !resumeId}
                    >
                        {busy ? (
                            <>
                                <span className="spinner spinner-small" />{' '}
                                Entwurf wird erstellt …
                            </>
                        ) : (
                            'Für diese Stelle anpassen'
                        )}
                    </button>
                    <p className="side-panel-hint">
                        Die KI formuliert um, sortiert und gewichtet deine
                        Angaben neu. Gespeichert wird erst nach deiner Freigabe.
                    </p>
                </div>
            )}
        </section>
    )
}
