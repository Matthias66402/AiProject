import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { API_BASE } from '../api/client'
import { formatDate } from './JobTable'

// pdf.js ist groß (~400 kB) - erst laden, wenn ein Lebenslauf-Fenster aufgeht
const PdfViewer = lazy(() => import('./PdfViewer'))

// Mindestens so viel vom Fenster bleibt beim Verschieben im Viewport, damit
// die Titelleiste immer greifbar ist.
const KEEP_VISIBLE = 80
// Startbreite, muss zu .resume-window in static/style.css passen
const START_WIDTH = 900

// Schwebendes, an der Titelleiste verschiebbares Fenster mit einer
// Lebenslauf-Version (Stellen-Detailseite, Profil). Bewusst ohne
// abdunkelnden Hintergrund: die Seite dahinter bleibt lesbar und scrollbar,
// um z.B. mit der Stelle zu vergleichen. Größe per Ziehen an der unteren
// rechten Ecke. fileUrl: ohne Angabe die Route für eigene Lebensläufe
// (/resumes/<id>/file); für fremde (Admin/Stellenanbieter) document_link.
// title: optional statt "Lebenslauf", z.B. mit dem Namen der Person.
export default function ResumeViewerWindow({
    resume,
    fileUrl,
    title,
    onClose,
}) {
    const windowRef = useRef(null)
    const dragRef = useRef(null)
    const [pos, setPos] = useState(() => ({
        x: Math.max(16, window.innerWidth - START_WIDTH - 40),
        y: 90,
    }))
    const [dragging, setDragging] = useState(false)
    const [downloading, setDownloading] = useState(false)

    useEffect(() => {
        function onKeyDown(e) {
            if (e.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', onKeyDown)
        return () => document.removeEventListener('keydown', onKeyDown)
    }, [onClose])

    function handlePointerDown(e) {
        // Klicks auf Buttons in der Titelleiste nicht als Ziehen werten
        if (e.button !== 0 || e.target.closest('button')) return
        dragRef.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y }
        e.currentTarget.setPointerCapture(e.pointerId)
        setDragging(true)
    }

    function handlePointerMove(e) {
        if (!dragRef.current) return
        const width = windowRef.current?.offsetWidth || 0
        setPos({
            x: Math.min(
                Math.max(e.clientX - dragRef.current.dx, KEEP_VISIBLE - width),
                window.innerWidth - KEEP_VISIBLE,
            ),
            y: Math.min(
                Math.max(e.clientY - dragRef.current.dy, 0),
                window.innerHeight - 48,
            ),
        })
    }

    function handlePointerUp() {
        dragRef.current = null
        setDragging(false)
    }

    const src = fileUrl ?? `${API_BASE}/resumes/${resume.id}/file`
    const ext = resume.document_link
        ? resume.document_link.split('.').pop().toLowerCase()
        : null

    // Eigener Download-Button: Chromes PDF-Viewer blendet seinen Download-
    // Button bei schmalem Fenster aus. Per fetch + Blob, weil die API auf
    // einer anderen Origin läuft (dort ignoriert der Browser <a download>
    // und würde die Datei nur anzeigen).
    async function handleDownload() {
        setDownloading(true)
        try {
            const response = await fetch(src, { credentials: 'include' })
            if (!response.ok) throw new Error(response.statusText)
            const url = URL.createObjectURL(await response.blob())
            const link = document.createElement('a')
            link.href = url
            link.download = `Lebenslauf_${formatDate(resume.created_at)}.${ext || 'pdf'}`
            document.body.appendChild(link)
            link.click()
            link.remove()
            URL.revokeObjectURL(url)
        } catch {
            // Fallback: Datei im neuen Tab öffnen
            window.open(src, '_blank', 'noopener')
        } finally {
            setDownloading(false)
        }
    }

    // Per Portal in <body>, aus demselben Grund wie TailorDraftModal
    // (Stapelkontext von .scroll).
    return createPortal(
        <div
            ref={windowRef}
            className={`resume-window${dragging ? ' dragging' : ''}`}
            style={{ left: pos.x, top: pos.y }}
            role="dialog"
            aria-labelledby="resume-window-title"
        >
            <div
                className="resume-window-head"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
            >
                <i className="fa-solid fa-grip-vertical" />
                <h2 id="resume-window-title">
                    {title ?? 'Lebenslauf'} vom {formatDate(resume.created_at)}
                    {resume.target_job_position &&
                        ` · angepasst für ${resume.target_job_position}`}
                </h2>
                <button
                    type="button"
                    className="subtle-btn resume-window-download"
                    onClick={handleDownload}
                    disabled={downloading}
                    title="Herunterladen"
                >
                    <i className="fa-solid fa-download" />{' '}
                    {downloading ? 'Lädt …' : 'Herunterladen'}
                </button>
                <button
                    type="button"
                    className="tailor-modal-close"
                    aria-label="Schließen"
                    onClick={onClose}
                >
                    <i className="fa-solid fa-xmark" />
                </button>
            </div>
            <div className="resume-window-body">
                {ext === 'pdf' ? (
                    <Suspense
                        fallback={
                            <p className="pdf-viewer-loading">
                                <span className="spinner spinner-small" /> Lade
                                …
                            </p>
                        }
                    >
                        <PdfViewer url={src} />
                    </Suspense>
                ) : (
                    <p className="side-empty">
                        Für dieses Format gibt es keine Vorschau.{' '}
                        <a href={src}>
                            Lebenslauf-Datei herunterladen ({ext?.toUpperCase()}
                            )
                        </a>
                    </p>
                )}
            </div>
        </div>,
        document.body,
    )
}
