import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api/client'
import UserForm from '../components/UserForm'
import UserTable from '../components/UserTable'

export default function UsersPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    apiGet('/api/users')
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleCreate(values) {
    await apiPost('/api/users', values)
    load()
  }

  if (error) return <p className="form-error">{error}</p>
  if (!data) return <p>Lade …</p>

  return (
    <div className="scroll full">
      <h1 id="greetings">Nutzer</h1>
      <p className="subtitle">Verwalte die registrierten Nutzer</p>

      <UserTable users={data.users} />

      <UserForm roles={data.roles} customers={data.customers} onSubmit={handleCreate} submitLabel="Nutzer anlegen" />
    </div>
  )
}
