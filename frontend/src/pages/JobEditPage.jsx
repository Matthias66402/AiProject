import { useCallback, useEffect, useState } from 'react'
import {
    Link,
    useNavigate,
    useOutletContext,
    useParams,
    useSearchParams,
} from 'react-router-dom'
import DOMPurify from 'dompurify'
import { API_BASE, apiDelete, apiGet, apiPut } from '../api/client'
import DetailHeader from '../components/DetailHeader'
import JobForm from '../components/JobForm'
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

    const isAdmin = user?.role === 'admin'

    const loadJob = useCallback(() => {
        // Beim Wechsel der jobId sofort zuruecksetzen, damit waehrend des
        // Nachladens die "Lade..."-Anzeige greift statt eines veralteten,
        // aber weiterhin interaktiven Formulars fuer den vorherigen Job -
        // sonst kann ein Speichern-Klick in diesem Fenster die Werte des
        // alten Jobs (inkl. customer_id) auf die neue jobId schreiben.
        setJob(null)
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
                <section className="detail-card detail-main">
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
                                {job.document_link && documentExt !== 'pdf' && (
                                    <p>
                                        <a
                                            href={API_BASE + job.document_link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            Original-Dokument herunterladen (
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
                                                </span>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="match-empty">
                                    Keine Übereinstimmungen gefunden (evtl.
                                    noch kein Embedding vorhanden).
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
