import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import DOMPurify from 'dompurify'
import { apiDelete, apiGet, apiGetBlob, apiPost } from '../api/client'
import { formatDate } from './JobTable'

// created_at kommt als UTC ohne Zeitzone aus der DB (CURRENT_TIMESTAMP in
// Etc/UTC) - erst mit 'Z' rechnet der Browser korrekt in Ortszeit um.
function formatDateTime(iso) {
    const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
    return date.toLocaleString('de-DE', {
        dateStyle: 'medium',
        timeStyle: 'short',
    })
}

// Seitenspalte der Stellen-Detailseite für Rolle 'user', unter "Lebenslauf
// anpassen": erstellt per KI ein Motivationsschreiben aus der dort gewählten
// Lebenslauf-Version und dieser Stelle. Jedes neue Schreiben wird gespeichert
// und erscheint in der Liste darunter; ein Klick öffnet es im Popup (PDF-
// Download, Verwerfen = löschen).
export default function CoverLetterPanel({ jobId, jobPosition, resume }) {
    const [letters, setLetters] = useState(null)
    const [openLetter, setOpenLetter] = useState(null)
    // true, solange das geöffnete Schreiben gerade frisch erstellt wurde
    const [isNew, setIsNew] = useState(false)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')

    useEffect(() => {
        apiGet(`/api/resumes/cover-letters?job_id=${jobId}`)
            .then((data) => setLetters(data.cover_letters))
            .catch((err) => setError(err.message))
    }, [jobId])

    async function handleCreate() {
        setBusy(true)
        setError('')
        try {
            const data = await apiPost('/api/resumes/cover-letters', {
                resume_id: resume.id,
                job_id: jobId,
            })
            setLetters((prev) => [data.cover_letter, ...(prev || [])])
            setOpenLetter(data.cover_letter)
            setIsNew(true)
        } catch (err) {
            setError(err.message)
        } finally {
            setBusy(false)
        }
    }

    function handleOpen(letter) {
        setOpenLetter(letter)
        setIsNew(false)
    }

    async function handleDelete(letter) {
        await apiDelete(`/api/resumes/cover-letters/${letter.id}`)
        setLetters((prev) => prev.filter((l) => l.id !== letter.id))
        setOpenLetter(null)
    }

    return (
        <section className="side-panel">
            <div className="side-panel-head">
                <span className="icon-circle">
                    <i className="fa-solid fa-envelope-open-text" />
                </span>
                <div>
                    <h2>Motivationsschreiben</h2>
                    <div className="side-panel-hint">
                        Aus deinem Lebenslauf für diese Stelle
                    </div>
                </div>
            </div>

            {error && <p className="form-error">{error}</p>}

            {resume ? (
                <div className="tailor-controls">
                    <p className="side-panel-hint">
                        Grundlage: Lebenslauf vom{' '}
                        {formatDate(resume.created_at)}
                        {resume.target_job_position &&
                            ` (angepasst für ${resume.target_job_position})`}{' '}
                        - auswählbar unter „Lebenslauf anpassen“.
                    </p>
                    <button
                        type="button"
                        className="special-btn"
                        onClick={handleCreate}
                        disabled={busy}
                    >
                        {busy ? (
                            <>
                                <span className="spinner spinner-small" /> Wird
                                geschrieben …
                            </>
                        ) : (
                            'Motivationsschreiben erstellen'
                        )}
                    </button>
                    <p className="side-panel-hint">
                        Die KI nutzt nur Angaben aus deinem Lebenslauf. Jedes
                        neue Schreiben wird gespeichert.
                    </p>
                </div>
            ) : (
                <p className="side-empty">
                    Wähle oben einen Lebenslauf als Grundlage.
                </p>
            )}

            {letters?.length > 0 && (
                <div className="cover-letter-saved">
                    <span className="tailor-fit-label">
                        Gespeicherte Motivationsschreiben
                    </span>
                    <ul className="side-list">
                        {letters.map((letter) => (
                            <li key={letter.id}>
                                <button
                                    type="button"
                                    className="side-item cover-letter-item"
                                    onClick={() => handleOpen(letter)}
                                >
                                    <span className="side-item-title">
                                        <i className="fa-regular fa-file-lines" />{' '}
                                        {formatDateTime(letter.created_at)}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {openLetter && (
                <CoverLetterModal
                    letter={openLetter}
                    filename={`Motivationsschreiben_${jobPosition}`}
                    isNew={isNew}
                    onDelete={() => handleDelete(openLetter)}
                    onClose={() => setOpenLetter(null)}
                />
            )}
        </section>
    )
}

// Popup mit dem Motivationsschreiben, Aufbau wie TailorDraftModal in
// JobEditPage. Das Schreiben ist schon gespeichert - X/Escape/Schließen
// behalten es, "Verwerfen" bzw. "Löschen" fragt nach und löscht es.
function CoverLetterModal({ letter, filename, isNew, onDelete, onClose }) {
    const [askDelete, setAskDelete] = useState(false)
    // null oder 'download'/'delete' - laufende Aktion sperrt alle Buttons
    const [working, setWorking] = useState(null)
    const [error, setError] = useState('')
    const dialogRef = useRef(null)
    const deleteLabel = isNew ? 'Verwerfen' : 'Löschen'

    function requestClose() {
        if (!working) onClose()
    }

    useEffect(() => {
        function onKeyDown(e) {
            if (e.key === 'Escape') requestClose()
        }
        document.addEventListener('keydown', onKeyDown)
        return () => document.removeEventListener('keydown', onKeyDown)
    })

    useEffect(() => {
        const previous = document.body.style.overflow
        document.body.style.overflow = 'hidden'
        dialogRef.current?.focus()
        return () => {
            document.body.style.overflow = previous
        }
    }, [])

    async function run(name, action) {
        setWorking(name)
        setError('')
        try {
            await action()
        } catch (err) {
            setError(err.message)
        } finally {
            setWorking(null)
        }
    }

    function handleDownload() {
        return run('download', async () => {
            const blob = await apiGetBlob(
                `/api/resumes/cover-letters/${letter.id}/pdf`,
            )
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = `${filename.replace(/[^\w-]+/g, '_')}.pdf`
            document.body.appendChild(link)
            link.click()
            link.remove()
            URL.revokeObjectURL(url)
        })
    }

    return createPortal(
        <div className="confirm-overlay tailor-overlay">
            <div
                ref={dialogRef}
                className="tailor-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="cover-letter-title"
                tabIndex={-1}
            >
                <div className="tailor-modal-head">
                    <h2 id="cover-letter-title">
                        Motivationsschreiben vom{' '}
                        {formatDateTime(letter.created_at)}
                    </h2>
                    <button
                        type="button"
                        className="tailor-modal-close"
                        aria-label="Schließen"
                        onClick={requestClose}
                        disabled={Boolean(working)}
                    >
                        <i className="fa-solid fa-xmark" />
                    </button>
                </div>
                <div className="tailor-modal-body">
                    <div
                        className="tailor-preview cover-letter-preview"
                        dangerouslySetInnerHTML={{
                            __html: DOMPurify.sanitize(letter.content),
                        }}
                    />
                </div>
                <div className="tailor-modal-foot">
                    {error && <p className="form-error">{error}</p>}
                    {askDelete ? (
                        <>
                            <span className="tailor-modal-ask">
                                {`Motivationsschreiben ${deleteLabel.toLowerCase()}?`}
                            </span>
                            <button
                                type="button"
                                className="subtle-btn"
                                onClick={() => setAskDelete(false)}
                                disabled={Boolean(working)}
                                autoFocus
                            >
                                Abbrechen
                            </button>
                            <button
                                type="button"
                                className="subtle-btn cancel"
                                onClick={() => run('delete', onDelete)}
                                disabled={Boolean(working)}
                            >
                                {deleteLabel}
                            </button>
                        </>
                    ) : (
                        <>
                            <button
                                type="button"
                                className="subtle-btn cancel"
                                onClick={() => setAskDelete(true)}
                                disabled={Boolean(working)}
                            >
                                {deleteLabel}
                            </button>
                            <button
                                type="button"
                                className="subtle-btn"
                                onClick={requestClose}
                                disabled={Boolean(working)}
                            >
                                Schließen
                            </button>
                            <button
                                type="button"
                                className="special-btn"
                                onClick={handleDownload}
                                disabled={Boolean(working)}
                            >
                                <i className="fa-solid fa-file-pdf" />{' '}
                                {working === 'download'
                                    ? 'PDF wird erstellt …'
                                    : 'Als PDF herunterladen'}
                            </button>
                        </>
                    )}
                </div>
            </div>
        </div>,
        document.body,
    )
}
