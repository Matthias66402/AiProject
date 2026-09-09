import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import CustomerForm from '../components/CustomerForm'
import CustomerTable from '../components/CustomerTable'
import Pager from '../components/Pager'

export default function CustomersPage() {
  const { user } = useOutletContext()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(10)
  const [error, setError] = useState('')

  const isAdmin = user?.role === 'admin'
  const isCustomerUser = Boolean(user?.role === 'customer' && user?.customer_id)

  const load = useCallback(() => {
    apiGet(`/api/customers?page=${page}&per_page=${perPage}`)
      .then(setData)
      .catch((err) => setError(err.message))
  }, [page, perPage])

  useEffect(() => {
    if (user === undefined) return
    // 'customer'-Nutzer mit zugeordnetem Stellenanbieter bekommen statt der Liste
    // aller Stellenanbieter direkt ihr eigenes Bearbeiten-Formular (wie /customers
    // in der klassischen Ansicht).
    if (isCustomerUser) {
      navigate(`/customers/${user.customer_id}/edit`, { replace: true })
      return
    }
    load()
  }, [load, user, isCustomerUser, navigate])

  async function handleCreate(values) {
    await apiPost('/api/customers', values)
    load()
  }

  async function handleDelete(customerId) {
    if (!window.confirm('Kunde wirklich löschen?')) return
    await apiDelete(`/api/customers/${customerId}`)
    load()
  }

  if (error) return <p className="form-error">{error}</p>
  if (!data) return <p>Lade …</p>

  return (
    <div className="scroll full">
      <h1 id="greetings">Kunden</h1>
      <p className="subtitle">Übersicht der registrierten Kunden</p>

      {isAdmin && (
        <details className="entity-form">
          <summary className="subtle-btn">+ Kunde anlegen</summary>
          <CustomerForm onSubmit={handleCreate} submitLabel="Kunde anlegen" />
        </details>
      )}

      <CustomerTable
        customers={data.customers}
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
