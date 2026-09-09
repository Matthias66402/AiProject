import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams, useSearchParams } from 'react-router-dom'
import DOMPurify from 'dompurify'
import { API_BASE, apiDelete, apiGet, apiPut } from '../api/client'
import JobForm from '../components/JobForm'
import JobTable from '../components/JobTable'
import Pager from '../components/Pager'

export default function JobEditPage() {
  const { user } = useOutletContext()
  const { jobId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const fromCustomer = searchParams.get('from_customer')

  const [job, setJob] = useState(null)
  const [listData, setListData] = useState(null)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(10)
  const [error, setError] = useState('')

  const isAdmin = user?.role === 'admin'
  const isCustomerUser = Boolean(user?.role === 'customer' && user?.customer_id)

  const loadJob = useCallback(() => {
    apiGet(`/api/jobs/${jobId}`)
      .then((data) => setJob(data.job))
      .catch((err) => setError(err.message))
  }, [jobId])

  const loadList = useCallback(() => {
    const customerFilter = fromCustomer ? `&customer_id=${fromCustomer}` : ''
    apiGet(`/api/jobs?page=${page}&per_page=${perPage}${customerFilter}`)
      .then(setListData)
      .catch((err) => setError(err.message))
  }, [page, perPage, fromCustomer])

  useEffect(() => {
    if (user === undefined) return
    loadJob()
  }, [loadJob, user])

  useEffect(() => {
    if (user === undefined) return
    loadList()
  }, [loadList, user])

  async function handleSave(values) {
    await apiPut(`/api/jobs/${jobId}`, {
      position: values.position,
      customer_id: isAdmin ? values.customer_id : undefined,
      zip: values.zip,
      city: values.city,
      content: values.content,
      valid_from: values.valid_from || null,
      valid_until: values.valid_until || null,
    })
    loadJob()
    loadList()
  }

  async function handleDeleteCurrent() {
    if (!window.confirm('Stelle wirklich löschen?')) return
    await apiDelete(`/api/jobs/${jobId}`)
    navigate('/jobs')
  }

  async function handleDeleteRow(id) {
    if (!window.confirm('Stelle wirklich löschen?')) return
    await apiDelete(`/api/jobs/${id}`)
    loadList()
  }

  if (error) return <p className="form-error">{error}</p>
  if (!job || !listData) return <p>Lade …</p>

  const canManage = job.can_manage
  const documentExt = job.document_link ? job.document_link.split('.').pop().toLowerCase() : null

  return (
    <div className="scroll full">
      <h1 id="greetings">Stellenangebote</h1>
      {fromCustomer ? (
        <p className="subtitle">
          Stellenangebote von {job.customer_name} · <Link to="/jobs">alle anzeigen</Link>
        </p>
      ) : (
        <p className="subtitle">Übersicht der Stellenangebote</p>
      )}

      <details className="entity-form" open>
        <summary className="subtle-btn">{canManage ? 'Stelle bearbeiten' : 'Stelle ansehen'}</summary>
        {canManage ? (
          <>
            <JobForm
              key={job.id}
              mode="edit"
              initial={job}
              isAdmin={isAdmin}
              customers={listData.customers}
              ownCustomerName={job.customer_name}
              onSubmit={handleSave}
              submitLabel="Speichern"
            />
            <p className="subtitle">
              {fromCustomer && (
                <>
                  <a href={`${API_BASE}/customers/${job.customer_id}/edit`}>
                    <i className="fa-solid fa-arrow-left" /> Zurück zu {job.customer_name}
                  </a>{' '}
                  ·{' '}
                </>
              )}
              <Link to="/jobs">Abbrechen</Link> ·{' '}
              <button type="button" className="link-button" onClick={handleDeleteCurrent}>
                <i className="fa-solid fa-trash" /> Löschen
              </button>
            </p>
          </>
        ) : (
          <div className="entity-view">
            <div>
              <label>Position</label>
              <p>{job.position}</p>
            </div>
            <div>
              <label>Kunde</label>
              <p>{job.customer_name}</p>
            </div>
            <div>
              <label>PLZ</label>
              <p>{job.zip || '-'}</p>
            </div>
            <div>
              <label>Stadt</label>
              <p>{job.city || '-'}</p>
            </div>
            <div>
              <label>Beschreibung</label>
              {documentExt === 'pdf' ? (
                <iframe className="pdf-embed" src={API_BASE + job.document_link} title="Stellenangebot PDF" />
              ) : job.document_link ? (
                <>
                  <div className="ql-editor job-content-view" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(job.content) }} />
                  <p>
                    <a href={API_BASE + job.document_link} target="_blank" rel="noopener noreferrer">
                      Original-Dokument herunterladen ({documentExt.toUpperCase()})
                    </a>
                  </p>
                </>
              ) : (
                <div className="ql-editor job-content-view" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(job.content) }} />
              )}
            </div>
            <div>
              <label>Gültig von</label>
              <p>{job.valid_from || '-'}</p>
            </div>
            <div>
              <label>Gültig bis</label>
              <p>{job.valid_until || '-'}</p>
            </div>
            {fromCustomer && (
              <a className="subtle-btn" href={`${API_BASE}/customers/${job.customer_id}/edit`}>
                <i className="fa-solid fa-arrow-left" /> Zurück zu {job.customer_name}
              </a>
            )}
            <Link className="subtle-btn" to="/jobs">
              Schließen
            </Link>
          </div>
        )}
      </details>

      {isAdmin && (
        <div className="entity-view">
          <label>Passende Kandidaten</label>
          {job.matching_resumes.length > 0 ? (
            <ul>
              {job.matching_resumes.map((m) => (
                <li key={m.id}>
                  <a href={`${API_BASE}/users/${m.user_id}/edit`}>
                    {m.first_name} {m.last_name} ({m.short_name})
                  </a>{' '}
                  · {(m.similarity * 100).toFixed(1)}% Übereinstimmung
                </li>
              ))}
            </ul>
          ) : (
            <p>Keine Übereinstimmungen gefunden (evtl. noch kein Embedding vorhanden).</p>
          )}
        </div>
      )}

      <JobTable
        jobs={listData.jobs}
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
    </div>
  )
}
