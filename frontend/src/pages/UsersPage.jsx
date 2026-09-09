import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiGet, apiPost } from '../api/client'
import UserForm from '../components/UserForm'
import UserTable from '../components/UserTable'

export default function UsersPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  const load = useCallback(() => {
    apiGet('/api/users')
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Anders als bei Jobs/Kunden gibt es hier keine serverseitige Pagination -
  // /api/users liefert immer alle Nutzer auf einmal, daher filtert das
  // dynamische Suchfeld hier clientseitig, statt bei jedem Tastendruck neu zu
  // laden.
  const filteredUsers = useMemo(() => {
    if (!data) return []
    const term = search.trim().toLowerCase()
    if (!term) return data.users
    return data.users.filter(
      (u) =>
        `${u.first_name} ${u.last_name}`.toLowerCase().includes(term) ||
        u.short_name.toLowerCase().includes(term) ||
        u.email.toLowerCase().includes(term),
    )
  }, [data, search])

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

      <form onSubmit={(e) => e.preventDefault()} style={{ marginBottom: '16px' }}>
        <div>
          <label htmlFor="user-search">Suche (Name, Kurzname, E-Mail)</label>
          <input
            id="user-search"
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="z. B. Krull"
          />
        </div>
      </form>

      <UserTable users={filteredUsers} />

      <UserForm roles={data.roles} customers={data.customers} onSubmit={handleCreate} submitLabel="Nutzer anlegen" />
    </div>
  )
}
