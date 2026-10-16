import { useCallback, useEffect, useState } from 'react'
import {
    Link,
    useNavigate,
    useOutletContext,
    useParams,
    useSearchParams,
} from 'react-router-dom'
import { API_BASE, apiGet, apiPut } from '../api/client'
import DetailHeader from '../components/DetailHeader'
import { formatDate } from '../components/JobTable'
import MatchExplanation from '../components/MatchExplanation'
import ResumeViewerWindow from '../components/ResumeViewerWindow'
import UserForm from '../components/UserForm'

export default function UserEditPage() {
    const { user, refreshUser } = useOutletContext()
    const params = useParams()
    const navigate = useNavigate()
    // ?job=<id>: über 'Passende Kandidat:innen' einer Stelle erreicht - dann
    // zeigt die Seite die Übereinstimmung mit genau dieser Stelle.
    const [searchParams] = useSearchParams()
    const jobId = searchParams.get('job')
    // Ohne :userId = eigenes Profil (/profile, Konto-Menü -> 'Bearbeiten'):
    // für jeden eingeloggten Nutzer editierbar, Rolle nicht sichtbar.
    const isProfile = !params.userId
    const userId = params.userId ?? user?.id
    const isAdmin = user?.role === 'admin'
    const needsList = isAdmin && !isProfile

    const [listData, setListData] = useState(null)
    const [userDetail, setUserDetail] = useState(null)
    const [error, setError] = useState('')
    const [viewedResume, setViewedResume] = useState(null)
    const closeViewer = useCallback(() => setViewedResume(null), [])

    const loadList = useCallback(() => {
        // Nur Admins duerfen/brauchen die Liste (fuer Rollen-/Kunden-Dropdown
        // im Bearbeiten-Formular) - fuer die schreibgeschuetzte Kandidatenansicht
        // (z.B. ueber "Passende Kandidaten" erreicht) unnoetig.
        if (!needsList) return
        apiGet('/api/users')
            .then(setListData)
            .catch((err) => setError(err.message))
    }, [needsList])

    const loadUser = useCallback(() => {
        if (!userId) return
        setUserDetail(null)
        const query = jobId ? `?job_id=${encodeURIComponent(jobId)}` : ''
        apiGet(`/api/users/${userId}${query}`)
            .then(setUserDetail)
            .catch((err) => setError(err.message))
    }, [userId, jobId])

    useEffect(() => {
        loadList()
    }, [loadList])

    useEffect(() => {
        loadUser()
    }, [loadUser])

    async function handleSave(values) {
        await apiPut(`/api/users/${userId}`, values)
        // Kurzname im Konto-Menü aktualisieren
        if (Number(userId) === user.id) await refreshUser()
        if (isProfile) navigate(-1)
        else navigate('/users')
    }

    if (user === null)
        return <p className="form-error">Bitte melden Sie sich an.</p>
    if (error) return <p className="form-error">{error}</p>
    if (!userDetail || (needsList && !listData)) return <p>Lade …</p>

    const u = userDetail.user
    const resumes = userDetail.resumes
    const matchingJob = userDetail.matching_job
    const place = [u.zip, u.city].filter(Boolean).join(' ')
    // Eigene Lebensläufe über die Besitzer-Route (/resumes/<id>/file, auch für
    // Rolle 'user'), fremde über document_link (/tools/resume/..., nur Admin/
    // Stellenanbieter) - siehe app.py.
    const isOwn = u.id === user.id

    return (
        <div className="detail-page">
            <DetailHeader
                backTo={needsList ? '/users' : null}
                onBack={needsList ? null : () => navigate(-1)}
                backLabel={needsList ? 'Zurück zu Nutzer' : 'Zurück'}
                title={`${u.first_name} ${u.last_name}`}
                meta={
                    <>
                        <span>
                            <i className="fa-regular fa-user" /> {u.short_name}
                        </span>
                        {place && (
                            <span>
                                <i className="fa-solid fa-location-dot" />{' '}
                                {place}
                            </span>
                        )}
                        {!isProfile && (
                            <span className="status-chip planned">
                                {u.role}
                            </span>
                        )}
                    </>
                }
                actions={
                    needsList && (
                        <Link className="subtle-btn cancel" to="/users">
                            Abbrechen
                        </Link>
                    )
                }
            />

            <div className="detail-layout">
                <section className="detail-card detail-main">
                    <h2>{isProfile ? 'Meine Daten' : 'Nutzerdaten'}</h2>
                    {isProfile || isAdmin ? (
                        <UserForm
                            key={u.id}
                            roles={listData?.roles ?? []}
                            customers={listData?.customers ?? []}
                            initial={u}
                            roleOnly={!isProfile && u.id !== user.id}
                            hideRole={isProfile}
                            onSubmit={handleSave}
                            submitLabel="Speichern"
                        />
                    ) : (
                        <div className="entity-view">
                            <div>
                                <label>Name</label>
                                <p>
                                    {u.first_name} {u.last_name} (
                                    {u.short_name})
                                </p>
                            </div>
                            <div>
                                <label>E-Mail</label>
                                <p>{u.email}</p>
                            </div>
                            <div>
                                <label>Rolle</label>
                                <p>{u.role}</p>
                            </div>
                            <div>
                                <label>PLZ / Stadt</label>
                                <p>{place || '-'}</p>
                            </div>
                        </div>
                    )}
                </section>

                <aside className="detail-aside">
                    <section className="side-panel">
                        <div className="side-panel-head">
                            <span className="icon-circle">
                                <i className="fa-regular fa-file-lines" />
                            </span>
                            <div>
                                <h2>Lebensläufe</h2>
                                <div className="side-panel-hint">
                                    Hochgeladene Dokumente
                                </div>
                            </div>
                        </div>
                        {resumes.length > 0 ? (
                            <ul className="side-list">
                                {resumes.map((resume) => (
                                    <li key={resume.id} className="side-item">
                                        <button
                                            type="button"
                                            className="side-item-title resume-open-btn"
                                            onClick={() =>
                                                setViewedResume(resume)
                                            }
                                        >
                                            <i className="fa-regular fa-file-lines" />{' '}
                                            Lebenslauf vom{' '}
                                            {formatDate(resume.created_at)}
                                        </button>
                                        {resume.target_job_position && (
                                            <span className="side-item-meta">
                                                Angepasst für{' '}
                                                {resume.target_job_position}
                                            </span>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="side-empty">
                                Noch kein Lebenslauf hochgeladen.
                            </p>
                        )}
                        {viewedResume && (
                            <ResumeViewerWindow
                                resume={viewedResume}
                                fileUrl={
                                    isOwn
                                        ? undefined
                                        : API_BASE + viewedResume.document_link
                                }
                                onClose={closeViewer}
                            />
                        )}
                    </section>
                </aside>

                {matchingJob && (
                    <aside className="detail-aside">
                        <section className="match-panel">
                            <div className="match-panel-head">
                                <span className="icon-circle">
                                    <i className="fa-solid fa-diagram-project" />
                                </span>
                                <div>
                                    <h2>Passende Stelle</h2>
                                    <div className="match-panel-hint">
                                        Semantische Ähnlichkeit zum besten
                                        Lebenslauf für diese Stelle
                                    </div>
                                </div>
                            </div>
                            {matchingJob.similarity !== null ? (
                                <ul className="match-list">
                                    <li>
                                        <Link
                                            className="match-item"
                                            to={`/jobs/${matchingJob.id}/edit`}
                                        >
                                            <span className="match-item-top">
                                                <span>
                                                    {matchingJob.position}
                                                </span>
                                                <span className="match-pct">
                                                    {(
                                                        matchingJob.similarity *
                                                        100
                                                    ).toFixed(1)}{' '}
                                                    %
                                                </span>
                                            </span>
                                            <span className="match-bar">
                                                <span
                                                    style={{
                                                        width: `${matchingJob.similarity * 100}%`,
                                                    }}
                                                />
                                            </span>
                                            <span className="match-meta">
                                                {matchingJob.customer_name}
                                                {matchingJob.city
                                                    ? ` · ${matchingJob.city}`
                                                    : ''}
                                            </span>
                                        </Link>
                                        <MatchExplanation
                                            key={`${matchingJob.resume_id}-${matchingJob.id}`}
                                            jobId={matchingJob.id}
                                            resumeId={matchingJob.resume_id}
                                        />
                                    </li>
                                </ul>
                            ) : (
                                <p className="match-empty">
                                    Keine Übereinstimmung berechenbar (evtl.
                                    noch kein Embedding vorhanden).
                                </p>
                            )}
                        </section>
                    </aside>
                )}
            </div>
        </div>
    )
}
