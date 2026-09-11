import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { API_BASE, apiGet, apiPut } from '../api/client'
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

    if (!isAdmin) {
        const u = userDetail.user
        return (
            <div className="scroll full">
                <h1 id="greetings">Nutzerprofil</h1>
                <p className="subtitle">Nur lesbar</p>
                <div className="entity-view">
                    <div>
                        <label>Name</label>
                        <p>
                            {u.first_name} {u.last_name} ({u.short_name})
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
                        <p>
                            {u.zip || '-'} {u.city || ''}
                        </p>
                    </div>
                    {userDetail.resumes.length > 0 && (
                        <div>
                            <label>Lebensläufe</label>
                            <ul>
                                {userDetail.resumes.map((resume) => (
                                    <li key={resume.id}>
                                        <a
                                            href={
                                                API_BASE + resume.document_link
                                            }
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            Lebenslauf vom{' '}
                                            {resume.created_at
                                                ? resume.created_at.slice(0, 10)
                                                : '-'}
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    <button
                        className="subtle-btn"
                        type="button"
                        onClick={() => navigate(-1)}
                    >
                        Zurück
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className="scroll full">
            <h1 id="greetings">Nutzer bearbeiten</h1>
            <p className="subtitle">Verwalte die registrierten Nutzer</p>

            <UserForm
                key={userDetail.user.id}
                roles={listData.roles}
                customers={listData.customers}
                initial={userDetail.user}
                resumes={userDetail.resumes}
                onSubmit={handleSave}
                submitLabel="Speichern"
                cancelTo="/users"
            />
        </div>
    )
}
