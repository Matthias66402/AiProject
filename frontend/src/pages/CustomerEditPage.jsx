import { useCallback, useEffect, useState } from 'react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPut } from '../api/client'
import CustomerForm from '../components/CustomerForm'
import DetailHeader from '../components/DetailHeader'
import { formatDate, jobStatus } from '../components/JobTable'
import Pager from '../components/Pager'
import { useConfirm } from '../components/ConfirmProvider'
import { SIDE_PANEL_PER_PAGE } from '../config'

export default function CustomerEditPage() {
    const { user } = useOutletContext()
    const { customerId } = useParams()
    const confirm = useConfirm()

    const [customer, setCustomer] = useState(null)
    const [jobsData, setJobsData] = useState(null)
    const [jobsPage, setJobsPage] = useState(1)
    const [search, setSearch] = useState('')
    const [debouncedSearch, setDebouncedSearch] = useState('')
    const [error, setError] = useState('')

    // 'customer'-Nutzer sehen nur ihren eigenen Datensatz, ohne Rückweg in
    // die Liste aller Stellenanbieter.
    const isCustomerUser = Boolean(
        user?.role === 'customer' && user?.customer_id,
    )

    const loadCustomer = useCallback(() => {
        apiGet(`/api/customers/${customerId}`)
            .then((data) => setCustomer(data.customer))
            .catch((err) => setError(err.message))
    }, [customerId])

    // Suche in den Stellen des Anbieters (wie in JobsPage.jsx entprellt, mit
    // Rücksprung auf Seite 1).
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(search.trim())
            setJobsPage(1)
        }, 300)
        return () => clearTimeout(timer)
    }, [search])

    // Beim Wechsel des Anbieters Suche und Seite zurücksetzen.
    useEffect(() => {
        setSearch('')
        setDebouncedSearch('')
        setJobsPage(1)
    }, [customerId])

    const loadJobs = useCallback(() => {
        const params = new URLSearchParams({
            customer_id: customerId,
            page: String(jobsPage),
            per_page: String(SIDE_PANEL_PER_PAGE),
        })
        if (debouncedSearch) params.set('search', debouncedSearch)
        apiGet(`/api/jobs?${params.toString()}`)
            .then(setJobsData)
            .catch((err) => setError(err.message))
    }, [customerId, jobsPage, debouncedSearch])

    useEffect(() => {
        if (user === undefined) return
        loadCustomer()
    }, [loadCustomer, user])

    useEffect(() => {
        if (user === undefined) return
        loadJobs()
    }, [loadJobs, user])

    async function handleSave(values) {
        await apiPut(`/api/customers/${customerId}`, values)
        loadCustomer()
    }

    async function handleDeleteJob(jobId) {
        if (!(await confirm('Stelle wirklich löschen?'))) return
        await apiDelete(`/api/jobs/${jobId}`)
        loadJobs()
    }

    if (error) return <p className="form-error">{error}</p>
    if (!customer || !jobsData) return <p>Lade …</p>

    const canManage = customer.can_manage
    const jobs = jobsData.jobs
    const total = jobsData.total
    const address = [
        [customer.street, customer.street_number].filter(Boolean).join(' '),
        [customer.zip, customer.city].filter(Boolean).join(' '),
    ]
        .filter(Boolean)
        .join(', ')

    return (
        <div className="detail-page">
            <DetailHeader
                backTo={isCustomerUser ? null : '/customers'}
                backLabel="Zurück zu Stellenanbieter"
                title={customer.company_name}
                meta={
                    address && (
                        <span>
                            <i className="fa-solid fa-location-dot" />{' '}
                            {address}
                        </span>
                    )
                }
                actions={
                    canManage &&
                    !isCustomerUser && (
                        <Link className="subtle-btn cancel" to="/customers">
                            Abbrechen
                        </Link>
                    )
                }
            />

            <div className="detail-layout">
                <section className="detail-card detail-main">
                    <h2>Unternehmensdaten</h2>
                    {canManage ? (
                        <CustomerForm
                            key={customer.id}
                            initial={customer}
                            onSubmit={handleSave}
                            submitLabel="Speichern"
                        />
                    ) : (
                        <div className="entity-view">
                            <div>
                                <label>Unternehmen</label>
                                <p>{customer.company_name}</p>
                            </div>
                            <div>
                                <label>Adresse</label>
                                <p>{address || '-'}</p>
                            </div>
                        </div>
                    )}
                </section>

                <aside className="detail-aside">
                    <section className="side-panel">
                        <div className="side-panel-head">
                            <span className="icon-circle">
                                <i className="fa-solid fa-briefcase" />
                            </span>
                            <div>
                                <h2>Stellenangebote</h2>
                                <div className="side-panel-hint">
                                    {total === 1 ? '1 Stelle' : `${total} Stellen`}
                                    {debouncedSearch
                                        ? ` zu „${debouncedSearch}“`
                                        : ` von ${customer.company_name}`}
                                </div>
                            </div>
                        </div>
                        <form
                            className="side-search"
                            onSubmit={(e) => e.preventDefault()}
                        >
                            <label htmlFor="customer-job-search">
                                Suche (Position)
                            </label>
                            <input
                                id="customer-job-search"
                                type="text"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="z. B. Referent"
                            />
                        </form>
                        {jobs.length > 0 ? (
                            <ul className="side-list">
                                {jobs.map((job) => {
                                    const status = jobStatus(job)
                                    return (
                                        <li
                                            key={job.id}
                                            className={`side-item${job.match_count > 0 ? ' has-match' : ''}`}
                                        >
                                            <div className="side-item-top">
                                                <Link
                                                    className="side-item-title"
                                                    to={`/jobs/${job.id}/edit?from_customer=${customer.id}`}
                                                >
                                                    {job.position}
                                                </Link>
                                                <span
                                                    className={`status-chip ${status.key}`}
                                                >
                                                    {status.label}
                                                </span>
                                            </div>
                                            {/* match_count: nur Rolle 'customer' bei eigenen Stellen (api/jobs.py) */}
                                            {job.match_count > 0 && (
                                                <Link
                                                    className="my-match-chip"
                                                    to={`/jobs/${job.id}/edit?from_customer=${customer.id}`}
                                                    title="Stellensuchende, deren Lebenslauf zu dieser Stelle passt - Details auf der Stellenseite"
                                                >
                                                    <i className="fa-solid fa-diagram-project" />{' '}
                                                    {job.match_count === 1
                                                        ? '1 passende:r Kandidat:in'
                                                        : `${job.match_count} passende Kandidat:innen`}
                                                </Link>
                                            )}
                                            <div className="side-item-meta">
                                                <span>
                                                    Gültig bis{' '}
                                                    {formatDate(job.valid_until)}
                                                </span>
                                                {canManage && (
                                                    <button
                                                        type="button"
                                                        className="link-button"
                                                        onClick={() =>
                                                            handleDeleteJob(
                                                                job.id,
                                                            )
                                                        }
                                                    >
                                                        <i className="fa-solid fa-trash" />{' '}
                                                        Löschen
                                                    </button>
                                                )}
                                            </div>
                                        </li>
                                    )
                                })}
                            </ul>
                        ) : (
                            <p className="side-empty">
                                {debouncedSearch
                                    ? 'Keine Stelle passt zur Suche.'
                                    : 'Noch keine Stellenangebote für diesen Stellenanbieter.'}
                            </p>
                        )}
                        {jobsData.total_pages > 1 && (
                            <Pager
                                page={jobsData.page}
                                totalPages={jobsData.total_pages}
                                onPageChange={setJobsPage}
                            />
                        )}
                    </section>
                </aside>
            </div>
        </div>
    )
}
