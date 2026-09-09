import { useCallback, useEffect, useState } from 'react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPut } from '../api/client'
import CustomerForm from '../components/CustomerForm'
import CustomerTable from '../components/CustomerTable'
import Pager from '../components/Pager'

export default function CustomerEditPage() {
  const { user } = useOutletContext()
  const { customerId } = useParams()

  const [customer, setCustomer] = useState(null)
  const [listData, setListData] = useState(null)
  const [jobs, setJobs] = useState(null)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(10)
  const [error, setError] = useState('')

  const isAdmin = user?.role === 'admin'
  const isCustomerUser = Boolean(user?.role === 'customer' && user?.customer_id)

  const loadCustomer = useCallback(() => {
    apiGet(`/api/customers/${customerId}`)
      .then((data) => setCustomer(data.customer))
      .catch((err) => setError(err.message))
  }, [customerId])

  const loadList = useCallback(() => {
    // 'customer'-Nutzer sehen (wie in der klassischen Ansicht) nur ihren eigenen
    // Datensatz, keine Liste aller Stellenanbieter.
    if (isCustomerUser) return
    apiGet(`/api/customers?page=${page}&per_page=${perPage}`)
      .then(setListData)
      .catch((err) => setError(err.message))
  }, [page, perPage, isCustomerUser])

  const loadJobs = useCallback(() => {
    apiGet(`/api/jobs?customer_id=${customerId}&per_page=100`)
      .then((data) => setJobs(data.jobs))
      .catch((err) => setError(err.message))
  }, [customerId])

  useEffect(() => {
    if (user === undefined) return
    loadCustomer()
  }, [loadCustomer, user])

  useEffect(() => {
    if (user === undefined) return
    loadList()
  }, [loadList, user])

  useEffect(() => {
    if (user === undefined) return
    loadJobs()
  }, [loadJobs, user])

  async function handleSave(values) {
    await apiPut(`/api/customers/${customerId}`, values)
    loadCustomer()
    loadList()
  }

  async function handleDeleteRow(id) {
    if (!window.confirm('Kunde wirklich löschen?')) return
    await apiDelete(`/api/customers/${id}`)
    loadList()
  }

  if (error) return <p className="form-error">{error}</p>
  if (!customer || !jobs || (!isCustomerUser && !listData)) return <p>Lade …</p>

  const canManage = customer.can_manage

  return (
    <div className="scroll full">
      <h1 id="greetings">{isCustomerUser ? 'Bearbeiten' : 'Kunden'}</h1>
      {isCustomerUser ? (
        <p className="subtitle">Deine Unternehmensdaten und die dazugehörigen Stellenangebote.</p>
      ) : (
        <p className="subtitle">Übersicht der registrierten Kunden</p>
      )}

      <details className="entity-form" open>
        <summary className="subtle-btn">{canManage ? 'Kunde bearbeiten' : 'Kundendaten'}</summary>
        {canManage ? (
          <>
            <CustomerForm key={customer.id} initial={customer} onSubmit={handleSave} submitLabel="Speichern" />
            <p className="subtitle">
              <Link to="/customers">Abbrechen</Link>
            </p>
          </>
        ) : (
          <div className="entity-view">
            <div>
              <label>Firma</label>
              <p>{customer.company_name}</p>
              <p>
                {customer.street} {customer.street_number}
              </p>
              <p>
                {customer.zip} {customer.city}
              </p>
            </div>
            <Link className="subtle-btn" to="/customers">
              Schließen
            </Link>
          </div>
        )}

        <div className="entity-related">
          <h2>Stellenangebote von {customer.company_name}</h2>
          <table className="user-table">
            <thead>
              <tr>
                <th>Position</th>
                <th>Gültig von</th>
                <th>Gültig bis</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={4}>Noch keine Stellenangebote für diesen Stellenanbieter.</td>
                </tr>
              )}
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.position}</td>
                  <td>{job.valid_from || '-'}</td>
                  <td>{job.valid_until || '-'}</td>
                  <td>
                    <div className="row-actions">
                      <Link to={`/jobs/${job.id}/edit?from_customer=${customer.id}`}>
                        <i className={`fa-solid ${canManage ? 'fa-pen' : 'fa-eye'}`} />{' '}
                        {canManage ? 'Bearbeiten' : 'Ansehen'}
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      {!isCustomerUser && (
        <>
          <CustomerTable
            customers={listData.customers}
            isAdmin={isAdmin}
            isCustomerUser={isCustomerUser}
            currentCustomerId={user?.customer_id}
            onDelete={handleDeleteRow}
          />
          <Pager
            page={listData.page}
            totalPages={listData.total_pages}
            perPage={listData.per_page}
            perPageOptions={listData.per_page_options}
            onPageChange={setPage}
            onPerPageChange={(value) => {
              setPerPage(value)
              setPage(1)
            }}
          />
        </>
      )}
    </div>
  )
}
