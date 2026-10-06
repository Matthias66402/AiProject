import { useCallback, useEffect, useState } from 'react'
import {
    Link,
    useNavigate,
    useOutletContext,
    useParams,
} from 'react-router-dom'
import { API_BASE, apiGet, apiPut } from '../api/client'
import DetailHeader from '../components/DetailHeader'
import { formatDate } from '../components/JobTable'
import UserForm from '../components/UserForm'

export default function UserEditPage() {
    const { user } = useOutletContext()
    const { userId } = useParams()
    const navigate = useNavigate()
    const isAdmin = user?.role === 'admin'

    const [listData, setListData] = useState(null)
    const [userDetail, setUserDetail] = useState(null)
    const [error, setError] = useState('')

    const loadList = useCallback(() => {
        // Nur Admins duerfen/brauchen die Liste (fuer Rollen-/Kunden-Dropdown
        // im Bearbeiten-Formular) - fuer die schreibgeschuetzte Kandidatenansicht
        // (z.B. ueber "Passende Kandidaten" erreicht) unnoetig.
        if (!isAdmin) return
        apiGet('/api/users')
            .then(setListData)
            .catch((err) => setError(err.message))
    }, [isAdmin])

    const loadUser = useCallback(() => {
        setUserDetail(null)
        apiGet(`/api/users/${userId}`)
            .then(setUserDetail)
            .catch((err) => setError(err.message))
    }, [userId])

    useEffect(() => {
        loadList()
    }, [loadList])

    useEffect(() => {
        loadUser()
    }, [loadUser])

    async function handleSave(values) {
        await apiPut(`/api/users/${userId}`, values)
        navigate('/users')
    }

    if (error) return <p className="form-error">{error}</p>
    if (!userDetail || (isAdmin && !listData)) return <p>Lade …</p>

    const u = userDetail.user
    const resumes = userDetail.resumes
    const place = [u.zip, u.city].filter(Boolean).join(' ')

    return (
        <div className="detail-page">
            <DetailHeader
                backTo={isAdmin ? '/users' : null}
                onBack={isAdmin ? null : () => navigate(-1)}
                backLabel={isAdmin ? 'Zurück zu Nutzer' : 'Zurück'}
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
                        <span className="status-chip planned">{u.role}</span>
                    </>
                }
                actions={
                    isAdmin && (
                        <Link className="subtle-btn cancel" to="/users">
                            Abbrechen
                        </Link>
                    )
                }
            />

            <div className="detail-layout">
                <section className="detail-card detail-main">
                    <h2>Nutzerdaten</h2>
                    {isAdmin ? (
                        <UserForm
                            key={u.id}
                            roles={listData.roles}
                            customers={listData.customers}
                            initial={u}
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
                                        <a
                                            className="side-item-title"
                                            href={
                                                API_BASE + resume.document_link
                                            }
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            <i className="fa-regular fa-file-lines" />{' '}
                                            Lebenslauf vom{' '}
                                            {formatDate(resume.created_at)}
                                        </a>
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
                    </section>
                </aside>
            </div>
        </div>
    )
}
