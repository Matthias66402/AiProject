import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiGet, apiPut } from '../api/client'
import UserForm from '../components/UserForm'

export default function UserEditPage() {
    const { userId } = useParams()
    const navigate = useNavigate()
    const [listData, setListData] = useState(null)
    const [userDetail, setUserDetail] = useState(null)
    const [error, setError] = useState('')

    const loadList = useCallback(() => {
        apiGet('/api/users')
            .then(setListData)
            .catch((err) => setError(err.message))
    }, [])

    const loadUser = useCallback(() => {
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
    if (!listData || !userDetail) return <p>Lade …</p>

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
