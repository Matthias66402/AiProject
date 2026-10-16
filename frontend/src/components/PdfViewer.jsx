import { useEffect, useRef, useState } from 'react'
import { GlobalWorkerOptions, TextLayer, getDocument } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = workerUrl

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3]
// Abstand der Seiten zum Rand des Anzeigebereichs (muss zum padding von
// .pdf-viewer-pages in static/style.css passen)
const PAGE_GUTTER = 32

// Eigener PDF-Viewer auf Basis von pdf.js, damit PDFs in jedem Browser gleich
// und im App-Design aussehen - der eingebaute Viewer des Browsers richtet sich
// nach Browser/Profil-Theme und lässt sich von außen nicht gestalten.
// Je Seite ein Canvas plus unsichtbare Textebene (pdf.js TextLayer): Text ist
// markier- und kopierbar, die Browsersuche (Strg+F) findet ihn. Zoom relativ
// zur Seitenbreite (100 % = Seite füllt die Breite).
export default function PdfViewer({ url }) {
    const [pdf, setPdf] = useState(null)
    // Kopie der Bytes fürs Drucken (pdf.js übernimmt den Puffer beim Laden)
    const [pdfBlob, setPdfBlob] = useState(null)
    const [error, setError] = useState('')
    const [zoom, setZoom] = useState(1)
    const [width, setWidth] = useState(0)
    const [currentPage, setCurrentPage] = useState(1)
    const [pageInput, setPageInput] = useState('1')
    const scrollRef = useRef(null)
    const pageRefs = useRef([])

    // Laden: selbst per fetch mit Cookie, weil die API auf einer anderen
    // Origin läuft; pdf.js bekommt dann nur noch die Bytes.
    useEffect(() => {
        let cancelled = false
        let loadingTask = null
        pageRefs.current = []
        setPdf(null)
        setPdfBlob(null)
        setError('')
        setCurrentPage(1)
        fetch(url, { credentials: 'include' })
            .then((response) => {
                if (!response.ok)
                    throw new Error(
                        `PDF konnte nicht geladen werden (${response.status})`,
                    )
                return response.arrayBuffer()
            })
            .then((data) => {
                if (cancelled) return null
                setPdfBlob(
                    new Blob([data.slice(0)], { type: 'application/pdf' }),
                )
                loadingTask = getDocument({ data })
                return loadingTask.promise
            })
            .then((doc) => {
                if (doc && !cancelled) setPdf(doc)
            })
            .catch((err) => {
                if (!cancelled) setError(err.message)
            })
        return () => {
            cancelled = true
            loadingTask?.destroy()
        }
    }, [url])

    // Verfügbare Breite beobachten - das Fenster ist in der Größe veränderbar
    useEffect(() => {
        const element = scrollRef.current
        if (!element) return undefined
        const observer = new ResizeObserver(([entry]) =>
            setWidth(Math.floor(entry.contentRect.width)),
        )
        observer.observe(element)
        return () => observer.disconnect()
    }, [])

    // Seiten zeichnen, bei Größen-/Zoomänderung neu (kurz entprellt, damit
    // beim Aufziehen des Fensters nicht jeder Pixel ein Neuzeichnen auslöst).
    // Canvas und Textebene werden erst nach dem Zeichnen ausgetauscht, damit
    // die alte Darstellung bis dahin stehen bleibt (kein Flackern).
    useEffect(() => {
        if (!pdf || width <= 0) return undefined
        let cancelled = false
        const tasks = []
        const timer = setTimeout(async () => {
            const dpr = window.devicePixelRatio || 1
            const pageWidth = Math.max(width - PAGE_GUTTER, 100) * zoom
            for (let n = 1; n <= pdf.numPages; n += 1) {
                if (cancelled) return
                const page = await pdf.getPage(n)
                const wrapper = pageRefs.current[n - 1]
                if (cancelled || !wrapper) return
                const base = page.getViewport({ scale: 1 })
                const viewport = page.getViewport({
                    scale: pageWidth / base.width,
                })

                const canvas = document.createElement('canvas')
                canvas.width = Math.floor(viewport.width * dpr)
                canvas.height = Math.floor(viewport.height * dpr)
                const renderTask = page.render({
                    canvasContext: canvas.getContext('2d'),
                    viewport,
                    transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null,
                })
                const textDiv = document.createElement('div')
                textDiv.className = 'textLayer'
                const textLayer = new TextLayer({
                    textContentSource: page.streamTextContent(),
                    container: textDiv,
                    viewport,
                })
                tasks.push(renderTask, textLayer)
                try {
                    await Promise.all([renderTask.promise, textLayer.render()])
                } catch {
                    // abgebrochen (RenderingCancelledException) - ignorieren
                    return
                }
                if (cancelled) return
                wrapper.style.setProperty('--scale-factor', viewport.scale)
                wrapper.style.width = `${Math.floor(viewport.width)}px`
                wrapper.style.height = `${Math.floor(viewport.height)}px`
                wrapper.replaceChildren(canvas, textDiv)
            }
        }, 120)
        return () => {
            cancelled = true
            clearTimeout(timer)
            tasks.forEach((task) => task.cancel())
        }
    }, [pdf, width, zoom])

    useEffect(() => {
        setPageInput(String(currentPage))
    }, [currentPage])

    // Aktuelle Seite = letzte Seite, deren Oberkante oberhalb der Mitte des
    // Anzeigebereichs liegt
    function handleScroll() {
        const container = scrollRef.current
        if (!container) return
        const middle = container.scrollTop + container.clientHeight / 2
        let best = 1
        pageRefs.current.forEach((wrapper, i) => {
            if (wrapper && wrapper.offsetTop <= middle) best = i + 1
        })
        setCurrentPage(best)
    }

    function goToPage(n) {
        const wrapper = pageRefs.current[n - 1]
        if (!wrapper || !scrollRef.current) return
        scrollRef.current.scrollTo({ top: wrapper.offsetTop - 16 })
        setCurrentPage(n)
    }

    function handlePageSubmit(e) {
        e.preventDefault()
        const n = Number(pageInput)
        if (Number.isInteger(n) && n >= 1 && n <= pdf.numPages) goToPage(n)
        else setPageInput(String(currentPage))
    }

    function stepZoom(direction) {
        setZoom((z) => ZOOM_STEPS[ZOOM_STEPS.indexOf(z) + direction] ?? z)
    }

    // Drucken über ein unsichtbares iframe mit dem PDF als Blob-URL (gleiche
    // Origin) - der Browser druckt dann das Original, nicht die Canvas-Bilder.
    function handlePrint() {
        if (!pdfBlob) return
        const blobUrl = URL.createObjectURL(pdfBlob)
        const frame = document.createElement('iframe')
        frame.className = 'pdf-viewer-print-frame'
        frame.src = blobUrl
        frame.onload = () => {
            frame.contentWindow.focus()
            frame.contentWindow.print()
            // Aufräumen erst später - print() blockiert nicht in allen Browsern
            setTimeout(() => {
                frame.remove()
                URL.revokeObjectURL(blobUrl)
            }, 60000)
        }
        document.body.appendChild(frame)
    }

    const pages = pdf ? pdf.numPages : 0

    return (
        <div className="pdf-viewer">
            <div className="pdf-viewer-toolbar">
                {pages > 0 ? (
                    <form
                        className="pdf-viewer-page-nav"
                        onSubmit={handlePageSubmit}
                    >
                        Seite
                        <input
                            type="text"
                            inputMode="numeric"
                            value={pageInput}
                            onChange={(e) => setPageInput(e.target.value)}
                            onBlur={handlePageSubmit}
                            aria-label="Seite"
                        />
                        / {pages}
                    </form>
                ) : (
                    <span />
                )}
                <div className="pdf-viewer-tools">
                    <button
                        type="button"
                        onClick={() => stepZoom(-1)}
                        disabled={zoom === ZOOM_STEPS[0]}
                        aria-label="Verkleinern"
                        title="Verkleinern"
                    >
                        <i className="fa-solid fa-minus" />
                    </button>
                    <button
                        type="button"
                        className="pdf-viewer-zoom-value"
                        onClick={() => setZoom(1)}
                        title="Auf Seitenbreite"
                    >
                        {zoom === 1 ? 'Seitenbreite' : `${zoom * 100} %`}
                    </button>
                    <button
                        type="button"
                        onClick={() => stepZoom(1)}
                        disabled={zoom === ZOOM_STEPS[ZOOM_STEPS.length - 1]}
                        aria-label="Vergrößern"
                        title="Vergrößern"
                    >
                        <i className="fa-solid fa-plus" />
                    </button>
                    <span className="pdf-viewer-divider" />
                    <button
                        type="button"
                        onClick={handlePrint}
                        disabled={!pdfBlob}
                        aria-label="Drucken"
                        title="Drucken"
                    >
                        <i className="fa-solid fa-print" />
                    </button>
                </div>
            </div>
            <div
                ref={scrollRef}
                className="pdf-viewer-pages"
                onScroll={handleScroll}
            >
                {error ? (
                    <p className="form-error">{error}</p>
                ) : !pdf ? (
                    <p className="pdf-viewer-loading">
                        <span className="spinner spinner-small" /> Lade …
                    </p>
                ) : (
                    Array.from({ length: pages }, (_, i) => (
                        <div
                            key={i}
                            ref={(el) => {
                                pageRefs.current[i] = el
                            }}
                            className="pdf-viewer-page"
                        />
                    ))
                )}
            </div>
        </div>
    )
}
