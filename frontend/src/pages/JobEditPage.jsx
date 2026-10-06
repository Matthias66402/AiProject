import { useCallback, useEffect, useState } from 'react'
import {
    Link,
    useNavigate,
    useOutletContext,
    useParams,
    useSearchParams,
} from 'react-router-dom'
import DOMPurify from 'dompurify'
import { API_BASE, apiDelete, apiGet, apiPost, apiPut } from '../api/client'
import DetailHeader from '../components/DetailHeader'
import JobForm from '../components/JobForm'
import TailorResumePanel from '../components/TailorResumePanel'
import { formatDate, jobStatus } from '../components/JobTable'
import { useConfirm } from '../components/ConfirmProvider'

export default function JobEditPage() {
    const { user } = useOutletContext()
    const { jobId } = useParams()
    const [searchParams] = useSearchParams()
    const navigate = useNavigate()
    const confirm = useConfirm()
    const fromCustomer = searchParams.get('from_customer')

    const [job, setJob] = useState(null)
    const [customers, setCustomers] = useState(null)
    const [error, setError] = useState('')
    // Lebenslauf-Zuschnitt (Rolle 'user'): Entwurf aus der Vorschau, Status
    // beim Übernehmen und Schlüssel zum Neuladen der Versionsliste im Panel.
    const [draft, setDraft] = useState(null)
    const [draftSaving, setDraftSaving] = useState(false)
    const [draftError, setDraftError] = useState('')
    const [savedResume, setSavedResume] = useState(null)
    const [tailorReloadKey, setTailorReloadKey] = useState(0)

    const isAdmin = user?.role === 'admin'
    const isUser = user?.role === 'user'

    const loadJob = useCallback(() => {
        // Beim Wechsel der jobId sofort zuruecksetzen, damit waehrend des
        // Nachladens die "Lade..."-Anzeige greift statt eines veralteten,
        // aber weiterhin interaktiven Formulars fuer den vorherigen Job -
        // sonst kann ein Speichern-Klick in diesem Fenster die Werte des
        // alten Jobs (inkl. customer_id) auf die neue jobId schreiben.
        setJob(null)
        setDraft(null)
        setSavedResume(null)
        apiGet(`/api/jobs/${jobId}`)
            .then((data) => setJob(data.job))
            .catch((err) => setError(err.message))
    }, [jobId])

    // Nur Admins brauchen die Stellenanbieter-Auswahl im Formular; die Liste
    // liefert der Listen-Endpunkt mit.
    const loadCustomers = useCallback(() => {
        if (!isAdmin) return
        apiGet('/api/jobs?per_page=10')
            .then((data) => setCustomers(data.customers))
            .catch((err) => setError(err.message))
    }, [isAdmin])

    useEffect(() => {
        if (user === undefined) return
        loadJob()
    }, [loadJob, user])

    useEffect(() => {
        if (user === undefined) return
        loadCustomers()
    }, [loadCustomers, user])

    async function handleSave(values) {
        await apiPut(`/api/jobs/${jobId}`, {
            position: values.position,
            customer_id: isAdmin ? values.customer_id : undefined,
            zip: values.zip,
            city: values.city,
            content: values.content,
            valid_from: values.valid_from || null,
            valid_until: values.valid_until || null,
        })
        loadJob()
    }

    function handleDraft(newDraft) {
        setDraft(newDraft)
        setDraftError('')
        setSavedResume(null)
    }

    async function handleAcceptDraft() {
        setDraftSaving(true)
        setDraftError('')
        try {
            const data = await apiPost('/api/resumes/tailor', {
                job_id: job.id,
                content: draft.draft_html,
            })
            setSavedResume(data.resume)
            setDraft(null)
            setTailorReloadKey((k) => k + 1)
        } catch (err) {
            setDraftError(err.message)
        } finally {
            setDraftSaving(false)
        }
    }

    async function handleDeleteCurrent() {
        if (!(await confirm('Stelle wirklich löschen?'))) return
        await apiDelete(`/api/jobs/${jobId}`)
        navigate(backTo)
    }

    const backTo = fromCustomer ? `/customers/${fromCustomer}/edit` : '/jobs'

    if (error) return <p className="form-error">{error}</p>
    if (!job || (isAdmin && !customers)) return <p>Lade …</p>

    const canManage = job.can_manage
    const status = jobStatus(job)
    const place = [job.zip, job.city].filter(Boolean).join(' ')
    const documentExt = job.document_link
        ? job.document_link.split('.').pop().toLowerCase()
        : null

    return (
        <div className="detail-page">
            <DetailHeader
                backTo={backTo}
                backLabel={
                    fromCustomer
                        ? `Zurück zu ${job.customer_name}`
                        : 'Zurück zu Stellenangebote'
                }
                title={job.position}
                meta={
                    <>
                        <span>
                            <i className="fa-regular fa-building" />{' '}
                            {job.customer_name}
                        </span>
                        {place && (
                            <span>
                                <i className="fa-solid fa-location-dot" />{' '}
                                {place}
                            </span>
                        )}
                        <span className={`status-chip ${status.key}`}>
                            {status.label}
                        </span>
                    </>
                }
                actions={
                    canManage && (
                        <>
                            <button
                                type="button"
                                className="danger-btn"
                                onClick={handleDeleteCurrent}
                            >
                                <i className="fa-solid fa-trash" /> Löschen
                            </button>
                            <Link className="subtle-btn cancel" to={backTo}>
                                Abbrechen
                            </Link>
                        </>
                    )
                }
            />

            <div className="detail-layout">
                <div className="detail-main detail-stack">
                    <section className="detail-card">
                        <h2>Stellendaten</h2>
                        {canManage ? (
                            <JobForm
                                key={job.id}
                                mode="edit"
                                initial={job}
                                isAdmin={isAdmin}
                                customers={customers || []}
                                ownCustomerName={job.customer_name}
                                onSubmit={handleSave}
                                submitLabel="Speichern"
                            />
                        ) : (
                            <div className="entity-view">
                                <div>
                                    <label>Beschreibung</label>
                                    {documentExt === 'pdf' ? (
                                        <iframe
                                            className="pdf-embed"
                                            src={API_BASE + job.document_link}
                                            title="Stellenangebot PDF"
                                        />
                                    ) : (
                                        <div
                                            className="ql-editor job-content-view"
                                            dangerouslySetInnerHTML={{
                                                __html: DOMPurify.sanitize(
                                                    job.content,
                                                ),
                                            }}
                                        />
                                    )}
                                    {job.document_link &&
                                        documentExt !== 'pdf' && (
                                            <p>
                                                <a
                                                    href={
                                                        API_BASE +
                                                        job.document_link
                                                    }
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                >
                                                    Original-Dokument
                                                    herunterladen (
                                                    {documentExt.toUpperCase()})
                                                </a>
                                            </p>
                                        )}
                                </div>
                                <div>
                                    <label>Gültig von</label>
                                    <p>{formatDate(job.valid_from)}</p>
                                </div>
                                <div>
                                    <label>Gültig bis</label>
                                    <p>{formatDate(job.valid_until)}</p>
                                </div>
                            </div>
                        )}
                    </section>

                    {savedResume && (
                        <section className="info-card tailor-saved">
                            <i className="fa-solid fa-circle-check" />
                            <p>
                                Dein angepasster Lebenslauf wurde als neue
                                Version gespeichert und zählt ab jetzt beim
                                Matching für diese Stelle.{' '}
                                <Link to="/resumes">Zu „Mein Lebenslauf“</Link>
                            </p>
                        </section>
                    )}

                    {draft && (
                        <TailorDraftCard
                            draft={draft}
                            saving={draftSaving}
                            error={draftError}
                            onAccept={handleAcceptDraft}
                            onDiscard={() => setDraft(null)}
                        />
                    )}
                </div>

                {isUser && (
                    <aside className="detail-aside">
                        <TailorResumePanel
                            jobId={job.id}
                            reloadKey={tailorReloadKey}
                            onDraft={handleDraft}
                        />
                    </aside>
                )}

                {canManage && (
                    <aside className="detail-aside">
                        <section className="match-panel">
                            <div className="match-panel-head">
                                <span className="icon-circle">
                                    <i className="fa-solid fa-diagram-project" />
                                </span>
                                <div>
                                    <h2>Passende Kandidat:innen</h2>
                                    <div className="match-panel-hint">
                                        Semantische Ähnlichkeit zu den
                                        hochgeladenen Lebensläufen
                                    </div>
                                </div>
                            </div>
                            {job.matching_resumes.length > 0 ? (
                                <ul className="match-list">
                                    {job.matching_resumes.map((m) => (
                                        <li key={m.id}>
                                            <Link
                                                className="match-item"
                                                to={`/users/${m.user_id}/edit`}
                                            >
                                                <span className="match-item-top">
                                                    <span>
                                                        {m.first_name}{' '}
                                                        {m.last_name}
                                                    </span>
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
                                                    {m.short_name}
                                                    {m.target_job_id && (
                                                        <span className="match-tag">
                                                            angepasst
                                                        </span>
                                                    )}
                                                </span>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="match-empty">
                                    Keine Übereinstimmungen gefunden (evtl. noch
                                    kein Embedding vorhanden).
                                </p>
                            )}
                        </section>
                        <section className="info-card">
                            <i className="fa-solid fa-wand-magic-sparkles" />
                            <p>
                                Das Matching vergleicht die Beschreibung mit
                                allen hochgeladenen Lebensläufen. Nach dem
                                Speichern wird es neu berechnet.
                            </p>
                        </section>
                    </aside>
                )}
            </div>
        </div>
    )
}

function formatPct(value) {
    return value == null ? '–' : `${(value * 100).toFixed(1)} %`
}

// Vorschau eines zugeschnittenen Lebenslaufs: Matching vorher/nachher, vom
// Prüfschritt gemeldete unbelegte Angaben und der Entwurf selbst.
function TailorDraftCard({ draft, saving, error, onAccept, onDiscard }) {
    const bars = [
        ['Vorher', draft.similarity_before],
        ['Nachher', draft.similarity_after],
    ]
    return (
        <section className="detail-card">
            <h2>Entwurf: angepasster Lebenslauf</h2>

            <div className="tailor-compare">
                {bars.map(([label, value]) => (
                    <div key={label} className="tailor-compare-row">
                        <span className="tailor-compare-label">{label}</span>
                        <span className="match-bar">
                            <span style={{ width: `${(value || 0) * 100}%` }} />
                        </span>
                        <span className="tailor-compare-pct">
                            {formatPct(value)}
                        </span>
                    </div>
                ))}
                <p className="side-panel-hint">
                    Semantische Ähnlichkeit zu dieser Stelle
                </p>
            </div>

            {draft.unsupported.length > 0 ? (
                <div className="tailor-warning">
                    <p>
                        <i className="fa-solid fa-triangle-exclamation" /> Bitte
                        prüfen - diese Angaben sind im Original nicht eindeutig
                        belegt:
                    </p>
                    <ul>
                        {draft.unsupported.map((item) => (
                            <li key={item}>{item}</li>
                        ))}
                    </ul>
                </div>
            ) : (
                <p className="tailor-ok">
                    <i className="fa-solid fa-circle-check" /> Die Prüfung hat
                    keine unbelegten Angaben gefunden.
                </p>
            )}

            <div
                className="tailor-preview"
                dangerouslySetInnerHTML={{
                    __html: DOMPurify.sanitize(draft.draft_html),
                }}
            />

            {error && <p className="form-error">{error}</p>}
            <div className="detail-actions tailor-actions">
                <button
                    type="button"
                    className="special-btn"
                    onClick={onAccept}
                    disabled={saving}
                >
                    {saving ? 'Wird gespeichert …' : 'Übernehmen'}
                </button>
                <button
                    type="button"
                    className="subtle-btn cancel"
                    onClick={onDiscard}
                    disabled={saving}
                >
                    Verwerfen
                </button>
            </div>
        </section>
    )
}
