import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { API_BASE, apiDelete, apiGet, apiPost } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'

export default function MyResumesPage() {
    const confirm = useConfirm()
    const fileInputRef = useRef(null)
    const [resumes, setResumes] = useState(null)
    const [selectedId, setSelectedId] = useState(null)
    const [selectedResume, setSelectedResume] = useState(null)
    const [matchingJobs, setMatchingJobs] = useState([])
    const [message, setMessage] = useState('')
    const [error, setError] = useState('')
    const [spec, setSpec] = useState('')
    const [generating, setGenerating] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [uploadFile, setUploadFile] = useState(null)
    const [dragOver, setDragOver] = useState(false)

    const loadList = useCallback((selectId) => {
        apiGet('/api/resumes')
            .then((data) => {
                setResumes(data.resumes)
                const fallbackId = data.resumes[0]?.id ?? null
                setSelectedId(selectId ?? fallbackId)
            })
            .catch((err) => setError(err.message))
    }, [])

    useEffect(() => {
        loadList()
    }, [loadList])

    useEffect(() => {
        if (!selectedId) {
            setSelectedResume(null)
            setMatchingJobs([])
            return
        }
        apiGet(`/api/resumes/${selectedId}`)
            .then((data) => {
                setSelectedResume(data.resume)
                setMatchingJobs(data.matching_jobs)
            })
            .catch((err) => setError(err.message))
    }, [selectedId])

    async function handleGenerate(e) {
        e.preventDefault()
        if (!spec.trim()) {
            setError('Bitte beschreibe, was dein Lebenslauf enthalten soll.')
            return
        }
        setGenerating(true)
        setError('')
        setMessage('')
        try {
            const data = await apiPost('/api/resumes', { spec })
            setMessage('Dein Lebenslauf wurde erstellt:')
            setSpec('')
            loadList(data.resume.id)
        } catch (err) {
            setError(err.message)
        } finally {
            setGenerating(false)
        }
    }

    async function handleUpload(e) {
        e.preventDefault()
        if (!uploadFile) {
            setError('Bitte zuerst eine Datei auswählen.')
            return
        }
        setUploading(true)
        setError('')
        setMessage('')

        const formData = new FormData()
        formData.append('resume_file', uploadFile)

        try {
            const response = await fetch(`${API_BASE}/api/resumes/upload`, {
                method: 'POST',
                credentials: 'include',
                body: formData,
            })
            const data = await response.json()
            if (!response.ok) {
                setError(
                    data.error || 'Die Datei konnte nicht verarbeitet werden.',
                )
                return
            }
            setMessage('Dein Lebenslauf wurde hochgeladen:')
            setUploadFile(null)
            if (fileInputRef.current) fileInputRef.current.value = ''
            loadList(data.resume.id)
        } catch {
            setError(
                'Die Datei konnte nicht verarbeitet werden. Bitte später erneut versuchen.',
            )
        } finally {
            setUploading(false)
        }
    }

    async function handleDelete() {
        if (!selectedResume) return
        if (!(await confirm('Diesen Lebenslauf wirklich löschen?'))) return
        await apiDelete(`/api/resumes/${selectedResume.id}`)
        setMessage('')
        loadList()
    }

    if (error && !resumes) return <p className="form-error">{error}</p>
    if (!resumes) return <p>Lade …</p>

    const documentExt = selectedResume?.document_link
        ? selectedResume.document_link.split('.').pop().toLowerCase()
        : null

    return (
        <div className="scroll wide">
            <h1 id="greetings">Mein Lebenslauf</h1>

            {message && <p className="subtitle">{message}</p>}
            {error && <p className="form-error">{error}</p>}

            {resumes.length === 0 ? (
                <p className="subtitle">
                    Für dich wurde noch kein Lebenslauf erstellt.
                </p>
            ) : (
                <>
                    <p className="subtitle">
                        Dein aktuellster Lebenslauf ist unten eingebettet - über
                        die Auswahl erreichst du auch ältere Versionen.
                    </p>

                    <div>
                        <label htmlFor="resume_id">Version</label>
                        <select
                            id="resume_id"
                            value={selectedId ?? ''}
                            onChange={(e) =>
                                setSelectedId(Number(e.target.value))
                            }
                        >
                            {resumes.map((resume, index) => (
                                <option key={resume.id} value={resume.id}>
                                    {resume.created_at}
                                    {index === 0 ? ' (neueste)' : ''}
                                </option>
                            ))}
                        </select>
                    </div>

                    {selectedResume && (
                        <>
                            <div className="row-actions mt-5">
                                <button
                                    type="button"
                                    className="link-button"
                                    onClick={handleDelete}
                                >
                                    <i className="fa-solid fa-trash" />{' '}
                                    Lebenslauf löschen
                                </button>
                            </div>

                            {documentExt === 'pdf' ? (
                                <iframe
                                    className="pdf-embed"
                                    src={`${API_BASE}/resumes/${selectedResume.id}/file`}
                                    title="Lebenslauf PDF"
                                />
                            ) : (
                                <p>
                                    <a
                                        href={`${API_BASE}/resumes/${selectedResume.id}/file`}
                                    >
                                        Lebenslauf-Datei herunterladen (
                                        {documentExt?.toUpperCase()})
                                    </a>
                                </p>
                            )}

                            <section className="match-panel">
                                <div className="match-panel-head">
                                    <span className="icon-circle">
                                        <i className="fa-solid fa-diagram-project" />
                                    </span>
                                    <div>
                                        <h2>Passende Stellenangebote</h2>
                                        <div className="match-panel-hint">
                                            Semantische Ähnlichkeit zu diesem
                                            Lebenslauf
                                        </div>
                                    </div>
                                </div>
                                {matchingJobs.length > 0 ? (
                                    <ul className="match-list">
                                        {matchingJobs.map((m) => (
                                            <li key={m.id}>
                                                <Link
                                                    className="match-item"
                                                    to={`/jobs/${m.id}/edit`}
                                                >
                                                    <span className="match-item-top">
                                                        <span>{m.position}</span>
                                                        <span className="match-pct">
                                                            {(
                                                                m.similarity * 100
                                                            ).toFixed(1)}{' '}
                                                            %
                                                        </span>
                                                    </span>
                                                    <span className="match-bar">
                                                        <span
                                                            style={{
                                                                width: `${m.similarity * 100}%`,
                                                            }}
                                                        />
                                                    </span>
                                                    <span className="match-meta">
                                                        {m.customer_name}
                                                        {m.city
                                                            ? ` · ${m.city}`
                                                            : ''}
                                                    </span>
                                                </Link>
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <p className="match-empty">
                                        Keine passenden Stellenangebote
                                        gefunden.
                                    </p>
                                )}
                            </section>
                        </>
                    )}
                </>
            )}

            <div className="resume-actions-row">
                <details className="entity-form">
                    <summary className="subtle-btn mt-5">
                        {resumes.length > 0
                            ? 'Neuen Lebenslauf generieren'
                            : 'Lebenslauf generieren'}
                    </summary>
                    <p className="subtitle">
                        Bitte beschreibe, was dein Lebenslauf enthalten soll:
                    </p>
                    <form onSubmit={handleGenerate}>
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
                </details>

                <details className="entity-form">
                    <summary className="subtle-btn mt-5">
                        Lebenslauf hochladen
                    </summary>
                    <p className="subtitle">
                        Lade deinen bestehenden Lebenslauf als PDF-, Word-
                        (.docx) oder LibreOffice-Datei (.odt) hoch:
                    </p>
                    <form onSubmit={handleUpload}>
                        <div className="textarea-wrap">
                            <label
                                className={`dropzone${dragOver ? ' dragover' : ''}`}
                                htmlFor="resume_file_input"
                                onDragEnter={(e) => {
                                    e.preventDefault()
                                    setDragOver(true)
                                }}
                                onDragOver={(e) => {
                                    e.preventDefault()
                                    setDragOver(true)
                                }}
                                onDragLeave={(e) => {
                                    e.preventDefault()
                                    setDragOver(false)
                                }}
                                onDrop={(e) => {
                                    e.preventDefault()
                                    setDragOver(false)
                                    const file = e.dataTransfer.files?.[0]
                                    if (file && fileInputRef.current) {
                                        // Ohne die Dateiliste des versteckten <input> zu übernehmen,
                                        // würde die native "required"-Prüfung beim Absenden fehlschlagen,
                                        // da der Browser einen per Drag&Drop gesetzten React-State nicht kennt.
                                        fileInputRef.current.files =
                                            e.dataTransfer.files
                                        setUploadFile(file)
                                    }
                                }}
                            >
                                <input
                                    ref={fileInputRef}
                                    className="dropzone-input"
                                    type="file"
                                    id="resume_file_input"
                                    accept=".pdf,.docx,.odt"
                                    required
                                    onChange={(e) =>
                                        setUploadFile(
                                            e.target.files?.[0] || null,
                                        )
                                    }
                                />
                                <i className="fa-solid fa-cloud-arrow-up dropzone-icon" />
                                <span className="dropzone-text">
                                    {uploadFile?.name ||
                                        'Datei hierher ziehen oder klicken zum Auswählen'}
                                </span>
                                <span className="dropzone-hint">
                                    PDF, .docx oder .odt
                                </span>
                            </label>
                            <div
                                className={`generating-indicator${uploading ? ' visible' : ''}`}
                            >
                                <span className="spinner" />
                                Lebenslauf wird verarbeitet …
                            </div>
                        </div>
                        <button
                            className="subtle-btn"
                            type="submit"
                            disabled={uploading}
                        >
                            Hochladen
                        </button>
                    </form>
                </details>
            </div>
        </div>
    )
}
