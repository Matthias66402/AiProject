import { useCallback, useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import Pager from '../components/Pager'
import JobTable from '../components/JobTable'
import JobForm from '../components/JobForm'

export default function JobsPage() {
  const { user } = useOutletContext()
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(10)
  const [error, setError] = useState('')

  const isAdmin = user?.role === 'admin'
  const isCustomerUser = Boolean(user?.role === 'customer' && user?.customer_id)
  const canManageJob = isAdmin || isCustomerUser

  const load = useCallback(() => {
    apiGet(`/api/jobs?page=${page}&per_page=${perPage}`)
      .then(setData)
      .catch((err) => setError(err.message))
  }, [page, perPage])

  useEffect(() => {
    if (user === undefined) return
    load()
  }, [load, user])

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
  }

  async function handleDelete(jobId) {
    if (!window.confirm('Stelle wirklich löschen?')) return
    await apiDelete(`/api/jobs/${jobId}`)
    load()
  }

  if (error) return <p className="form-error">{error}</p>
  if (!data) return <p>Lade …</p>

  return (
    <div className="scroll full">
      <h1 id="greetings">Stellenangebote</h1>
      <p className="subtitle">Übersicht der Stellenangebote</p>

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
