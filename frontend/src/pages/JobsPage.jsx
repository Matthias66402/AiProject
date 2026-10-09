import { useCallback, useEffect, useState } from 'react'
import { useOutletContext, useSearchParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import Pager from '../components/Pager'
import JobTable from '../components/JobTable'
import JobForm from '../components/JobForm'
import { useConfirm } from '../components/ConfirmProvider'
import { DEFAULT_DISTANCE, DEFAULT_PER_PAGE, DISTANCE_OPTIONS } from '../config'

export default function JobsPage() {
    const { user } = useOutletContext()
    const confirm = useConfirm()
    const [data, setData] = useState(null)
    const [page, setPage] = useState(1)
    const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)
    const [error, setError] = useState('')
    const [search, setSearch] = useState('')
    const [debouncedSearch, setDebouncedSearch] = useState('')
    const [stats, setStats] = useState(null)
    const isAdmin = user?.role === 'admin'
    const isCustomerUser = Boolean(
        user?.role === 'customer' && user?.customer_id,
    )
    const isJobSeeker = user?.role === 'user'
    const canManageJob = isAdmin || isCustomerUser

    // Filter 'Anzeigen' je Rolle: 'own' (customer) = nur Stellen des eigenen
    // Stellenanbieters, 'own_matching' (customer) = davon nur die mit mind.
    // einer passenden Person, 'with_candidates' (admin) = alle Stellen mit mind.
    // einer passenden Person, 'matching' (user) = nur Stellen, zu denen ein
    // eigener Lebenslauf passt. Steht in der URL (?scope=...), damit z.B. der
    // Eintrag 'Stellenangebote' im Konto-Menü direkt gefiltert öffnen kann, der
    // Hauptmenü-Reiter dagegen alle.
    const scopeOptions = isCustomerUser
        ? [
              ['own', 'Eigene Stellenangebote'],
              [
                  'own_matching',
                  'Eigene Stellenangebote mit passenden Kandidaten',
              ],
          ]
        : isAdmin
          ? [['with_candidates', 'Stellenangebote mit passenden Kandidaten']]
          : isJobSeeker
            ? [['matching', 'Passende Stellenangebote']]
            : []
    const [searchParams, setSearchParams] = useSearchParams()
    const requestedScope = searchParams.get('scope')
    const scope = scopeOptions.some(([value]) => value === requestedScope)
        ? requestedScope
        : 'all'

    // Entfernung um die eigene PLZ (nur Rolle 'user'), ebenfalls in der URL
    // (?distance=...). 'relocate' (umzugsbereit) filtert nicht.
    const requestedDistance = searchParams.get('distance')
    const distance =
        isJobSeeker &&
        DISTANCE_OPTIONS.some(([value]) => value === requestedDistance)
            ? requestedDistance
            : DEFAULT_DISTANCE

    // Einen Filter in der URL setzen, die anderen behalten; Standardwerte
    // werden entfernt, damit die URL ohne Filter sauber bleibt.
    function setFilterParam(key, value, defaultValue) {
        const next = new URLSearchParams(searchParams)
        if (value === defaultValue) next.delete(key)
        else next.set(key, value)
        setSearchParams(next)
    }

    // Dynamisches Suchfeld (sucht bisher nur in der Position): kurz entprellen,
    // statt bei jedem Tastendruck sofort neu zu laden, und dabei auf Seite 1
    // zurückspringen, da das Suchergebnis eine andere Seitenzahl haben kann.
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(search.trim())
            setPage(1)
        }, 300)
        return () => clearTimeout(timer)
    }, [search])

    // Filterwechsel (Auswahl oder Menü-Link) -> zurück auf Seite 1
    useEffect(() => {
        setPage(1)
    }, [scope, distance])

    const load = useCallback(() => {
        const params = new URLSearchParams({
            page: String(page),
            per_page: String(perPage),
        })
        if (debouncedSearch) params.set('search', debouncedSearch)
        if (scope === 'own' || scope === 'own_matching')
            params.set('customer_id', String(user.customer_id))
        if (scope === 'own_matching' || scope === 'with_candidates')
            params.set('with_candidates', '1')
        if (scope === 'matching') params.set('matching', '1')
        if (distance !== DEFAULT_DISTANCE) params.set('distance', distance)
        apiGet(`/api/jobs?${params.toString()}`)
            .then(setData)
            .catch((err) => setError(err.message))
    }, [page, perPage, debouncedSearch, scope, distance, user])

    useEffect(() => {
        if (user === undefined) return
        load()
    }, [load, user])

    // Kennzahlen separat (und nicht bei jeder Suche) laden - das Zählen der
    // Matches ist deutlich teurer als die Liste selbst. Fehler hier blenden
    // nur die Kacheln aus, die Liste bleibt nutzbar.
    const loadStats = useCallback(() => {
        apiGet('/api/jobs/stats')
            .then(setStats)
            .catch(() => setStats(null))
    }, [])

    // Abhängig vom Nutzer neu laden: welche Matches gezählt werden (alle, nur
    // eigene, keine) entscheidet der Server anhand der Session.
    useEffect(() => {
        if (user === undefined) return
        loadStats()
    }, [loadStats, user])

    async function handleCreate(values) {
        await apiPost('/api/jobs', {
            position: values.position,
            customer_id: isAdmin ? values.customer_id : undefined,
            zip: values.zip,
            city: values.city,
            content: values.content,
            valid_from: values.valid_from || null,
            valid_until: values.valid_until || null,
            document_link: values.document_link || null,
        })
        load()
        loadStats()
    }

    async function handleDelete(jobId) {
        if (!(await confirm('Stelle wirklich löschen?'))) return
        await apiDelete(`/api/jobs/${jobId}`)
        load()
        loadStats()
    }

    if (error) return <p className="form-error">{error}</p>
    if (!data) return <p>Lade …</p>

    return (
        <div className="scroll full">
            <h1 id="greetings">Stellenangebote</h1>
            <p className="subtitle">Übersicht der Stellenangebote</p>

            {stats && (
                <div className="stat-grid">
                    <div className="stat-tile">
                        <span className="icon-circle">
                            <i className="fa-solid fa-briefcase" />
                        </span>
                        <div>
                            <div className="stat-value">{stats.active_jobs}</div>
                            <div className="stat-label">
                                aktive Stellenangebote
                            </div>
                        </div>
                    </div>
                    <div className="stat-tile">
                        <span className="icon-circle">
                            <i className="fa-solid fa-building" />
                        </span>
                        <div>
                            <div className="stat-value">{stats.customers}</div>
                            <div className="stat-label">Stellenanbieter</div>
                        </div>
                    </div>
                    {stats.matches !== null && (
                        <div className="stat-tile dark">
                            <span className="icon-circle">
                                <i className="fa-solid fa-diagram-project" />
                            </span>
                            <div>
                                <div className="stat-value">{stats.matches}</div>
                                <div className="stat-label">
                                    Matches ab{' '}
                                    {Math.round(stats.min_similarity * 100)} %
                                    Ähnlichkeit
                                    {stats.matches_scope === 'own' &&
                                        ' (eigene Stellen)'}
                                    {stats.matches_scope === 'mine' &&
                                        ' (deine Lebensläufe)'}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {canManageJob && (
                <details className="entity-form">
                    <summary className="subtle-btn">Stelle anlegen</summary>
                    <JobForm
                        mode="create"
                        initial={undefined}
                        isAdmin={isAdmin}
                        customers={data.customers}
                        ownCustomerName={data.own_customer?.company_name}
                        onSubmit={handleCreate}
                        submitLabel="Speichern"
                    />
                </details>
            )}

            <form
                onSubmit={(e) => e.preventDefault()}
                className={
                    isJobSeeker
                        ? 'form-grid cols-3'
                        : scopeOptions.length
                          ? 'form-grid'
                          : undefined
                }
                style={{ marginBottom: '16px' }}
            >
                <div>
                    <label htmlFor="job-search">Suche (Position)</label>
                    <input
                        id="job-search"
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="z. B. Entwickler"
                    />
                </div>
                {scopeOptions.length > 0 && (
                    <div>
                        <label htmlFor="job-scope">Anzeigen</label>
                        <select
                            id="job-scope"
                            value={scope}
                            onChange={(e) =>
                                setFilterParam('scope', e.target.value, 'all')
                            }
                        >
                            <option value="all">Alle Stellenangebote</option>
                            {scopeOptions.map(([value, label]) => (
                                <option key={value} value={value}>
                                    {label}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
                {isJobSeeker && (
                    <div>
                        <label htmlFor="job-distance">Entfernung</label>
                        <select
                            id="job-distance"
                            value={distance}
                            disabled={!data.origin_zip}
                            onChange={(e) =>
                                setFilterParam(
                                    'distance',
                                    e.target.value,
                                    DEFAULT_DISTANCE,
                                )
                            }
                        >
                            {DISTANCE_OPTIONS.map(([value, label]) => (
                                <option key={value} value={value}>
                                    {label}
                                </option>
                            ))}
                        </select>
                        {!data.origin_zip && (
                            <span className="side-panel-hint">
                                Für die Entfernungssuche bitte unter
                                Einstellungen eine PLZ hinterlegen.
                            </span>
                        )}
                    </div>
                )}
            </form>

            <JobTable
                jobs={data.jobs}
                isAdmin={isAdmin}
                isCustomerUser={isCustomerUser}
                currentCustomerId={user?.customer_id}
                onDelete={handleDelete}
            />

            <Pager
                page={data.page}
                totalPages={data.total_pages}
                perPage={data.per_page}
                perPageOptions={data.per_page_options}
                onPageChange={setPage}
                onPerPageChange={(value) => {
                    setPerPage(value)
                    setPage(1)
                }}
            />
        </div>
    )
}
