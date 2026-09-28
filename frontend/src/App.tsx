import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, LayoutGroup, MotionConfig, animate, motion, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from 'framer-motion'
import { Activity, AlertCircle, ArrowDownToLine, ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronDown, Clipboard, FileImage, FileText, History, Info, Menu, Plus, Search, ShieldCheck, Sparkles, UploadCloud, X } from 'lucide-react'
import { pageVariants, revealVariants, staggerItemVariants, staggerVariants } from './motion-config'
import { ScrollReveal } from './motion'
import './premium.css'

type Finding = { text: string; certainty: string; source_excerpt?: string | null; reason?: string | null; requires_review?: boolean }
type Report = { id: string; created_at: string; input_type: string; filename: string | null; status: string; summary: string | null; report: {
  summary: string; patient_information: Record<string, string | null>; administrative_information?: Finding[]; unclassified_information?: Finding[]; symptoms: Finding[]; diagnoses: Finding[]; medications: Finding[]; vitals: Record<string, string>; allergies: Finding[]; clinical_observations: Finding[]; clinical_concerns: Finding[]; lab_tests?: Finding[]; follow_up?: Finding[]; doctor_advice?: Finding[]; missing_information: string[]; potential_inconsistencies: string[]; requires_review: string[]; extraction_quality: string; disclaimer: string; document_type: string; extraction_method: string; ocr_used: boolean; ocr_confidence: number | null; ocr_status: string; ocr_engine: string | null; raw_ocr_text: string; normalized_text: string; detected_scripts: string[]; unsupported_scripts: string[]; pages_processed: number; page_processing: { page_number: number; method: string; ocr_used: boolean; ocr_status: string; ocr_confidence: number | null; chars_extracted: number }[]; readability: string; ocr_blocks: { text: string; confidence: number; bbox: number[][]; page_number: number }[]; ml_prediction: { category: string; probabilities: { category: string; probability: number }[]; confidence: number; confidence_label: string; model_name: string; model_version: string; feature_signals: string[]; disclaimer: string } | null
  analysis_provider?: string; analysis_model?: string | null; analysis_note?: string | null
} | null; processing_error: string | null }
type View = 'overview' | 'documents' | 'reports' | 'review'
const API = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/$/, '')
const pages: View[] = ['overview', 'documents', 'reports', 'review']
const pageLabels: Record<View, string> = { overview: 'Overview', documents: 'Documents', reports: 'Reports', review: 'AI Review' }
const reveal = revealVariants

export default function App() {
  const [view, setView] = useState<View>('overview')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [style, setStyle] = useState('auto')
  const [report, setReport] = useState<Report | null>(null)
  const [sourceReportId, setSourceReportId] = useState<string | null>(null)
  const [reports, setReports] = useState<Report[]>([])
  const [reportQuery, setReportQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [toast, setToast] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const uploadRef = useRef<HTMLInputElement>(null)
  const closeSource = useCallback(() => setSourceOpen(false), [])
  const reducedMotion = useReducedMotion()

  const loadHistory = async () => {
    try { const response = await fetch(`${API}/api/reports`); if (response.ok) setReports(await response.json()) }
    catch { /* API availability is reflected in the workspace status. */ }
  }
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${API}/api/reports`, { signal: controller.signal }).then(r => r.ok ? r.json() : []).then(setReports).catch(() => {})
    return () => controller.abort()
  }, [])
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 3400); return () => window.clearTimeout(timer) }, [toast])
  useEffect(() => { const receive = (event: Event) => setToast((event as CustomEvent<string>).detail); window.addEventListener('workspace-toast', receive); return () => window.removeEventListener('workspace-toast', receive) }, [])

  const submit = async () => {
    if (!file && !text.trim()) { setError('Add clinical text or choose a document to get started.'); return }
    setBusy(true); setError(''); setReport(null)
    const body = new FormData()
    if (file) { body.append('file', file); body.append('writing_style', style) } else body.append('text', text)
    try {
      const response = await fetch(`${API}/api/reports`, { method: 'POST', body })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw Error(data.detail || 'We could not complete the review. Please try again.')
      if (!data.report || typeof data.report.summary !== 'string') throw Error('The server response did not contain a clinical report. Please retry; your document was not shown as reviewed.')
      setReport(data); setSourceReportId(file ? data.id : null); setView('review'); setToast(data.status === 'needs_review' ? 'Review saved — source verification needed.' : 'Clinical review generated and saved.'); await loadHistory()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Network error. Check your connection and try again.') }
    finally { setBusy(false) }
  }
  const openReport = async (id: string) => {
    try { const response = await fetch(`${API}/api/reports/${id}`); if (!response.ok) throw Error(); setReport(await response.json()); setSourceReportId(null); setView('review'); setError('') }
    catch { setError('Could not open this saved review. Check that the server is available.') }
  }
  const navigate = (next: View) => {
    if (next === 'review' && !report?.report) { if (reports[0]) { void openReport(reports[0].id); return } else next = 'documents' }
    setView(next); setError(''); setMenuOpen(false); if (next === 'reports') { void loadHistory(); window.setTimeout(() => document.getElementById('report-search')?.focus(), 220) }
  }

  return <MotionConfig reducedMotion="user" transition={{ type: 'spring', stiffness: 280, damping: 28 }}>
    <div className="page-bg">
      <motion.div className="frame" initial={reducedMotion ? false : { opacity: 0, scale: .99, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: .45, ease: 'easeOut' }}>
        <header className="topbar">
          <button className="brand" onClick={() => navigate('overview')} aria-label="Medcure home"><span className="brand-icon"><Activity size={19}/></span> Medcure <small>DOCUMENT REVIEW</small></button>
          <LayoutGroup><nav className={menuOpen ? 'nav-open' : ''} aria-label="Main navigation">{pages.map(key => <button key={key} className={`nav-pill ${view === key ? 'active' : ''}`} onClick={() => navigate(key)}>{key === 'overview' && <span className="grid-icon" aria-hidden="true">▦</span>}{pageLabels[key]}{view === key && <motion.i layoutId="nav-active"/>}</button>)}</nav></LayoutGroup>
          <div className="top-actions"><span className="service-state"><i/> Local workspace</span><button className="icon-button" aria-label="Search reports" onClick={() => navigate('reports')}><Search size={17}/></button><div className="profile"><span className="avatar">CD</span><div><b>Review Workspace</b><small>Local demo</small></div><ChevronDown size={14}/></div><button className="mobile-menu icon-button" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} onClick={() => setMenuOpen(v => !v)}>{menuOpen ? <X size={18}/> : <Menu size={18}/>}</button></div>
        </header>
        <main><AnimatePresence mode="wait"><motion.div key={view} variants={pageVariants} initial="hidden" animate="show" exit="exit">
          {view === 'overview' && <Overview reports={reports} openReport={openReport} navigate={navigate} />}
          {view === 'documents' && <Documents text={text} setText={setText} file={file} setFile={setFile} style={style} setStyle={setStyle} busy={busy} error={error} submit={submit} uploadRef={uploadRef}/>}
          {view === 'reports' && <HistoryPage reports={reports} error={error} openReport={openReport} query={reportQuery} setQuery={setReportQuery} />}
          {view === 'review' && report?.report && <ReportView report={report} expanded={expanded} setExpanded={setExpanded} back={() => navigate('reports')} newDoc={() => navigate('documents')} openSource={() => setSourceOpen(true)} retry={file && sourceReportId === report.id ? () => { navigate('documents'); void submit() } : undefined} />}
          {view === 'review' && !report?.report && <div className="document-view"><div className="empty-state"><b>Report details are unavailable</b><span>The saved report could not be loaded. Open it again from Reports or start a new review.</span><button className="secondary-button" onClick={() => navigate('documents')}>Start a new review</button></div></div>}
        </motion.div></AnimatePresence></main>
        <footer><span>Medcure <i>·</i> Clinical documentation support</span><span><ShieldCheck size={13}/> Synthetic information only</span></footer>
      </motion.div>
      <AnimatePresence>{sourceOpen && report?.report && <SourceViewer report={report} file={sourceReportId === report.id ? file : null} close={closeSource} />}</AnimatePresence>
      <AnimatePresence>{toast && <motion.div className="toast" role="status" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}><CheckCircle2 size={17}/>{toast}<button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={15}/></button></motion.div>}</AnimatePresence>
    </div>
  </MotionConfig>
}

function AnimatedPercent({ value }: { value: number }) {
  const progress = useMotionValue(0)
  const rounded = useTransform(progress, current => Math.round(current * 100))
  useEffect(() => { const control = animate(progress, value, { duration: .7, ease: 'easeOut' }); return () => control.stop() }, [progress, value])
  return <><motion.span>{rounded}</motion.span>%</>
}

function Overview({ reports, openReport, navigate }: { reports: Report[]; openReport: (id: string) => void; navigate: (view: View) => void }) {
  const latest = reports[0]?.report
  const reducedMotion = useReducedMotion()
  return <>
    <motion.div className="dashboard-grid" variants={{ show: { transition: { staggerChildren: .1, delayChildren: .08 } } }}>
      <motion.section className="left-column" variants={reveal}>
        <div className="eyebrow"><Sparkles size={13}/> AI CLINICAL DOCUMENT REVIEW</div><h1>Clinical clarity,<br/><em>grounded in source.</em></h1>
        <p className="intro">Turn clinical documents into structured, source-supported details that are easier to verify.</p>
        <div className="hero-actions"><button className="primary-button" onClick={() => navigate('documents')}><UploadCloud size={16}/> New analysis <ArrowRight size={15}/></button><button className="hero-secondary" onClick={() => navigate('reports')}><History size={15}/> Review history</button></div>
        <div className="metric-pair">
          <AnimatedCard className="metric-card"><div className="metric-top"><FileText/><span className="status-chip">Workspace</span></div><span>Documents reviewed</span><strong>{reports.length}</strong><small>Saved in this workspace</small></AnimatedCard>
          <AnimatedCard className="metric-card green-card"><div className="metric-top"><Activity/><span className="status-chip">Latest ML</span></div><span>Workflow label</span><strong className="metric-word">{latest?.ml_prediction?.category.replaceAll('_', ' ') || 'Awaiting data'}</strong><small>{latest?.ml_prediction ? `${Math.round(latest.ml_prediction.confidence * 100)}% model confidence` : 'No prediction yet'}</small></AnimatedCard>
        </div>
        <AnimatedCard className="recent-card"><div className="card-head"><div><b>Recent reviews</b><small>Saved reports from this workspace</small></div><button onClick={() => navigate('reports')}>View all <ArrowRight size={13}/></button></div>
          {reports.slice(0, 2).length ? reports.slice(0, 2).map(item => <button className="recent-row" key={item.id} onClick={() => openReport(item.id)}><span className="recent-file"><FileText size={16}/></span><span className="recent-title"><b>{item.filename || 'Clinical note'}</b><small>{item.summary || 'Clinical documentation review'}</small></span><span className="recent-time">{new Date(item.created_at).toLocaleDateString()}</span><ArrowRight size={15}/></button>) : <div className="empty-recent"><span className="empty-avatar"><History size={18}/></span><span><b>No reviews yet</b><small>Start with a synthetic note or document.</small></span></div>}
          <button className="appointment" onClick={() => navigate('documents')}><Plus size={17}/> Start a document review <span><ArrowRight size={16}/></span></button>
        </AnimatedCard>
      </motion.section>
      <motion.section className="anatomy-column" variants={reveal}>
        <div className="process-label"><span className="pulse-dot"/> DOCUMENT WORKFLOW <small>real results from the local API</small></div>
        <div className="anatomy-stage"><span className="hero-orb hero-orb-one"/><span className="hero-orb hero-orb-two"/><motion.div className="pipeline-image-wrap" initial={reducedMotion ? false : { opacity: 0, scale: .96, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }} whileHover={{ scale: 1.015 }} transition={{ duration: .65, ease: [.2,.7,.2,1] }}><motion.img className="pipeline-image" src="/workflow-pipeline.png" alt="Document workflow illustration: document upload, OCR, clinical extraction, ML review, and report" animate={reducedMotion ? undefined : { y: [0, -3, 0] }} transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }}/></motion.div><motion.div className="workflow-float-card" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .42 }}><span className="pulse-dot"/><span><b>Source first</b><small>Every field stays reviewable</small></span></motion.div></div>
        <div className="anatomy-caption"><span><b>5 steps</b><small>Source to structured review</small></span><span className="caption-line"/><span><b>{latest?.pages_processed || 0}</b><small>Latest pages processed</small></span></div>
      </motion.section>
      <motion.section className="right-column" variants={reveal}>
        <div className="right-pair"><AnimatedCard className="small-info-card"><div><FileImage size={16}/><span>OCR engine</span></div><b>{latest?.ocr_engine || (latest?.ocr_used ? 'Engine unavailable' : 'Ready')}</b><small>{latest?.ocr_status?.replaceAll('_', ' ') || 'Waiting for a document'}</small></AnimatedCard><AnimatedCard className="small-info-card"><div><ShieldCheck size={16}/><span>Review status</span></div><b>{reports[0]?.status.replaceAll('_', ' ') || 'Not started'}</b><small>{reports[0]?.status === 'needs_review' ? 'Manual verification suggested' : 'Local workflow state'}</small></AnimatedCard></div>
        <AnimatedCard className="status-card"><div className="card-head"><div><b>Latest review</b><small>Measured model confidence</small></div><span className="dots" aria-hidden="true">···</span></div>{latest ? <><div className="donut-wrap"><div className="donut" style={{ '--score': `${Math.round((latest.ocr_confidence ?? latest.ml_prediction?.confidence ?? 0) * 100)}%` } as React.CSSProperties}><div><b><AnimatedPercent value={latest.ocr_confidence ?? latest.ml_prediction?.confidence ?? 0}/></b><span>{latest.ocr_used ? 'OCR score' : 'model score'}</span></div></div></div><div className="legend"><span>Backend response</span><b>{latest.ocr_used ? 'OCR confidence' : 'ML confidence'}</b></div></> : <div className="no-signal"><div className="signal-ring"><Activity size={22}/></div><b>No review signal yet</b><span>Upload a document to see measured OCR and model results.</span></div>}</AnimatedCard>
        <AnimatedCard className="trend-card"><div className="card-head"><div><b>Saved review status</b><small>Most recent reports</small></div></div><div className="bar-chart">{reports.slice(0, 20).reverse().map(item => <i key={item.id} title={`${item.filename || 'Clinical note'}: ${item.status.replaceAll('_', ' ')}`} style={{ height: item.status === 'needs_review' ? '62px' : '38px', background: item.status === 'needs_review' ? '#d96863' : '#51a17b' }}/>) }{!reports.length && <span className="no-records">No saved reports yet</span>}</div><div className="chart-label"><span><i className="key-blue"/> Completed</span><span><i className="key-red"/> Needs review</span></div></AnimatedCard>
      </motion.section>
    </motion.div>
    <ScrollReveal className="privacy-note"><ShieldCheck size={14}/> Use synthetic information only. This tool organizes documentation and is not for diagnosis or treatment.</ScrollReveal>
  </>
}

function Documents({ text, setText, file, setFile, style, setStyle, busy, error, submit, uploadRef }: { text: string; setText: (value: string) => void; file: File | null; setFile: (value: File | null) => void; style: string; setStyle: (value: string) => void; busy: boolean; error: string; submit: () => Promise<void>; uploadRef: React.RefObject<HTMLInputElement | null> }) {
  const [dragging, setDragging] = useState(false)
  return <div className="document-view">
    <div className="page-title"><div className="eyebrow">WORKSPACE / DOCUMENTS</div><h1>Review a document</h1><p>Upload a PDF or image, or paste synthetic clinical text.</p></div>
    <div className="document-grid">
      <section className="input-panel"><div className="panel-title"><span className="step-badge">01</span><div><b>Source document</b><small>PDF, PNG, JPG, WEBP, TIFF, or BMP</small></div></div>
        <div className="input-switch"><button className={!file ? 'selected' : ''} onClick={() => setFile(null)}><FileText size={15}/> Paste text</button><button className={file ? 'selected' : ''} onClick={() => uploadRef.current?.click()}><UploadCloud size={15}/> Upload file</button></div>
        <AnimatePresence mode="wait" initial={false}>{file ? <motion.div key="file-selected" className={`selected-file ${busy ? 'is-processing' : ''}`} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}><FileImage size={22}/><span><b>{file.name}</b><small>{busy ? 'Request sent · waiting for backend results' : `${(file.size / 1024 / 1024).toFixed(2)} MB · selected`}</small></span><button disabled={busy} onClick={() => setFile(null)} aria-label="Remove file"><X size={17}/></button></motion.div> : <motion.div key="drop-zone" className={`drop-zone ${dragging ? 'dragging' : ''}`} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0, scale: dragging ? 1.012 : 1, borderColor: dragging ? '#47976a' : '#b7d2bf' }} exit={{ opacity: 0, y: -4 }} transition={{ duration: .18 }} onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); const dropped = e.dataTransfer.files[0]; if (dropped) setFile(dropped) }}><motion.span animate={{ y: dragging ? -2 : 0 }}><UploadCloud size={25}/></motion.span><b>Drop a document here</b><span>or choose a local PDF or image</span><button type="button" className="secondary-button" onClick={() => uploadRef.current?.click()}>Browse files</button></motion.div>}</AnimatePresence>
        {!file && <textarea aria-label="Clinical note text" value={text} onChange={e => setText(e.target.value)} placeholder={'Paste a synthetic clinical note here…\n\nExample: Patient reports fever and cough for two days. Temperature 101°F.'}/>}
        <input ref={uploadRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp" hidden onChange={e => setFile(e.target.files?.[0] || null)}/>
        {file && <label className="style-select">Writing style<select value={style} onChange={e => setStyle(e.target.value)}><option value="auto">Automatic</option><option value="printed">Printed</option><option value="handwritten">Handwritten · verify output</option></select></label>}
        <div className="panel-foot"><span>{file ? `${file.name} selected` : `${text.length} characters`} · synthetic info only</span><span><ShieldCheck size={14}/> Local API</span></div>
      </section>
      <aside className="how-panel"><div className="eyebrow">REVIEW WORKFLOW</div><div className="pipeline-image-wrap document-pipeline"><img className="pipeline-image" src="/workflow-pipeline.png" alt="Document to OCR to extraction to ML review to structured report"/></div>{[['01', 'Read source', 'Native PDF text or image OCR'], ['02', 'Structure details', 'Source-supported clinical fields'], ['03', 'Surface review items', 'Missing details and inconsistencies'], ['04', 'Classify workflow', 'Document review priority model']].map(([number, title, detail]) => <div className="workflow-item" key={number}><span>{number}</span><div><b>{title}</b><small>{detail}</small></div><Check size={15}/></div>)}<p><Info size={14}/> Handwriting recognition can be inaccurate, especially for unsupported scripts. Verify results against the source.</p></aside>
    </div>
    <AnimatePresence mode="wait">{error && <motion.div key="error" className="error-box" role="alert" initial={{ opacity: 0, x: 5 }} animate={{ opacity: 1, x: [5, -3, 2, 0] }} exit={{ opacity: 0 }} transition={{ duration: .28 }}><AlertCircle size={16}/>{error}</motion.div>}</AnimatePresence>
    <AnimatePresence mode="wait">{busy && <motion.div key="processing" className="processing" role="status" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}><span className="spin-ring"/><div><b>Backend request in progress</b><small>Waiting for the server response. No stage-by-stage progress is available yet.</small></div></motion.div>}</AnimatePresence>
    <div className="form-actions"><span><Info size={14}/> Documentation review only; not a diagnosis or treatment recommendation.</span><SlideConfirm busy={busy} disabled={!file && !text.trim()} onConfirm={submit}/></div>
  </div>
}

function SlideConfirm({ busy, disabled, onConfirm }: { busy: boolean; disabled: boolean; onConfirm: () => Promise<void> }) {
  const track = useRef<HTMLDivElement>(null)
  const [progress, setProgress] = useState(0)
  const [offset, setOffset] = useState(0)
  const active = useRef(false)
  const progressRef = useRef(0)
  const updateProgress = (value: number) => { progressRef.current = value; setProgress(value) }
  const run = () => { if (busy || disabled) return; updateProgress(1); setOffset(0); active.current = false; void onConfirm(); window.setTimeout(() => updateProgress(0), 700) }
  const move = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (!active.current || !track.current) return
    const rect = track.current.getBoundingClientRect()
    const handleWidth = event.currentTarget.getBoundingClientRect().width
    const max = Math.max(0, rect.width - handleWidth)
    const amount = Math.min(max, Math.max(0, event.clientX - rect.left - handleWidth / 2))
    setOffset(amount); updateProgress(max ? amount / max : 0)
  }
  const finish = (event: React.PointerEvent<HTMLButtonElement>) => { if (!active.current) return; move(event); active.current = false; if (progressRef.current >= .78) run(); else { updateProgress(0); setOffset(0) } }
  const cancel = () => { if (!active.current) return; active.current = false; updateProgress(0); setOffset(0) }
  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    const max = track.current ? track.current.clientWidth - 48 : 0
    if (event.key === 'ArrowRight') { event.preventDefault(); const next = Math.min(max, offset + 24); setOffset(next); updateProgress(max ? next / max : 0) }
    if (event.key === 'ArrowLeft') { event.preventDefault(); const next = Math.max(0, offset - 24); setOffset(next); updateProgress(max ? next / max : 0) }
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); run() }
  }
  return <div ref={track} className={`slide-confirm ${busy ? 'is-busy' : ''} ${disabled ? 'is-disabled' : ''}`} style={{ '--slide-progress': `${Math.round(progress * 100)}%` } as React.CSSProperties}>
    <span className="slide-copy">{busy ? 'Processing document…' : disabled ? 'Add text or choose a document' : 'Slide to analyze document'}</span>
    <motion.button type="button" className="slide-handle" aria-label="Slide to analyze document. Press Enter to start or use arrow keys to adjust." aria-valuetext={`${Math.round(progress * 100)} percent`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} role="slider" disabled={busy || disabled} onPointerDown={event => { active.current = true; event.currentTarget.setPointerCapture(event.pointerId); move(event) }} onPointerMove={move} onPointerUp={finish} onPointerCancel={cancel} onLostPointerCapture={cancel} onKeyDown={onKeyDown} animate={{ x: offset }} transition={{ type: 'spring', stiffness: 500, damping: 35 }}><ArrowRight size={17}/></motion.button>
  </div>
}

function HistoryPage({ reports, error, openReport, query, setQuery }: { reports: Report[]; error: string; openReport: (id: string) => void; query: string; setQuery: (value: string) => void }) {
  const filtered = reports.filter(item => `${item.filename || ''} ${item.summary || ''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
  return <div className="document-view"><div className="page-title"><div className="eyebrow">WORKSPACE / ARCHIVE</div><h1>Previous reviews</h1><p>Saved review results and their processing status.</p></div>{error && <div className="error-box" role="alert"><AlertCircle size={16}/>{error}</div>}<label className="history-search"><Search size={16}/><input id="report-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search saved reviews" aria-label="Search saved reviews"/></label><motion.div className="reports-list" variants={staggerVariants} initial="hidden" whileInView="show" viewport={{ once: true, amount: .08 }} layout>{filtered.length ? filtered.map(item => <motion.button className="report-row" variants={staggerItemVariants} layout key={item.id} onClick={() => openReport(item.id)} whileHover={{ x: 3 }} whileTap={{ scale: .995 }}><span className="report-icon"><FileText size={18}/></span><span className="report-row-main"><b>{item.filename || 'Clinical note'}</b><small>{item.summary || 'Clinical documentation review'}</small></span><span className="report-row-meta">{new Date(item.created_at).toLocaleString()}</span><span className={`record-status ${item.status}`}>{item.status.replaceAll('_', ' ')}</span><motion.span whileHover={{ x: 2 }}><ArrowRight size={16}/></motion.span></motion.button>) : <motion.div className="empty-state" variants={staggerItemVariants} key={query || 'empty'}><History size={28}/><b>{reports.length ? 'No matching reviews' : 'No saved reviews'}</b><span>{reports.length ? 'Try another search term.' : 'Completed reviews will appear here.'}</span></motion.div>}</motion.div></div>
}

const reportNav = [['summary', 'Summary'], ['patient', 'Patient'], ['symptoms', 'Symptoms'], ['diagnoses', 'Diagnoses'], ['medications', 'Medications'], ['vitals', 'Vitals'], ['lab-tests', 'Lab tests'], ['advice', 'Advice'], ['concerns', 'Concerns'], ['review-items', 'Review']] as const
function ReportView({ report: row, expanded, setExpanded, back, newDoc, openSource, retry }: { report: Report; expanded: boolean; setExpanded: (value: boolean) => void; back: () => void; newDoc: () => void; openSource: () => void; retry?: () => void }) {
  const data = row.report!
  const ocrStatus = data.ocr_status ?? (data.ocr_used ? 'success' : 'not_used')
  const pageProcessing = data.page_processing ?? []
  const detectedScripts = data.detected_scripts ?? []
  const unsupportedScripts = data.unsupported_scripts ?? []
  const [activeAnchor, setActiveAnchor] = useState('summary')
  const { scrollYProgress } = useScroll()
  const progress = useSpring(scrollYProgress, { stiffness: 120, damping: 24, restDelta: .001 })
  useEffect(() => {
    const observer = new IntersectionObserver(entries => { const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]; if (visible) setActiveAnchor(visible.target.id) }, { rootMargin: '-18% 0px -65% 0px', threshold: [0, .2, .5] })
    reportNav.forEach(([id]) => { const element = document.getElementById(id); if (element) observer.observe(element) })
    return () => observer.disconnect()
  }, [])
  const copy = async () => { try { await navigator.clipboard.writeText(JSON.stringify(data, null, 2)); window.dispatchEvent(new CustomEvent('workspace-toast', { detail: 'Structured report copied.' })) } catch { window.dispatchEvent(new CustomEvent('workspace-toast', { detail: 'Clipboard access is unavailable in this browser.' })) } }
  const download = () => { const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `clinical-review-${row.id.slice(0, 8)}.json`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); window.dispatchEvent(new CustomEvent('workspace-toast', { detail: 'Report download started.' })) }
  return <div className="document-view report-view"><motion.div className="report-progress" style={{ scaleX: progress }}/><div className="back-row"><button onClick={back}><ArrowLeft size={15}/> Previous reviews</button><span>REVIEW ID · {row.id.slice(0, 8).toUpperCase()}</span></div>
    <div className="page-title report-title"><div><div className="eyebrow"><CheckCircle2 size={13}/> {row.status === 'needs_review' ? 'NEEDS VERIFICATION' : 'REVIEW COMPLETE'}</div><h1>Clinical review</h1><p>{row.filename || 'Text submission'} · {new Date(row.created_at).toLocaleString()}</p></div><div className="report-actions"><button className="secondary-button" onClick={openSource}><FileText size={15}/> View source</button><button className="secondary-button" onClick={() => void copy()}><Clipboard size={15}/> Copy</button><button className="secondary-button" onClick={download}><ArrowDownToLine size={15}/> Download</button><button className="secondary-button" onClick={newDoc}><Plus size={15}/> New review</button></div></div>
    {(row.status === 'needs_review' || data.readability !== 'readable' || ocrStatus === 'partial' || ocrStatus === 'low_confidence' || data.document_type === 'handwritten' || unsupportedScripts.length > 0) && <div className="warning-banner" role="status"><AlertCircle size={17}/><div><b>Source needs verification</b><span>{unsupportedScripts.length ? `Detected ${unsupportedScripts.join(', ')} script is not supported by the configured OCR models; verify it against the original.` : data.document_type === 'handwritten' ? 'Handwriting recognition is approximate. Compare every extracted detail with the original.' : data.requires_review.length || data.missing_information.length ? 'Some details are missing or need source verification. Compare structured fields with the original document.' : 'Some content may not have been readable. Compare this review with the original document.'}</span>{retry && <button className="text-action" onClick={retry}>Retry OCR with current settings <ArrowRight size={13}/></button>}</div></div>}
    <nav className="report-sticky-nav" aria-label="Report sections">{reportNav.map(([id, label]) => <button key={id} className={activeAnchor === id ? 'selected' : ''} onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{label}{activeAnchor === id && <motion.i layoutId="report-nav-active"/>}</button>)}</nav>
    <motion.section id="summary" className="summary-panel report-reveal" variants={reveal} initial="hidden" whileInView="show" viewport={{ once: true, amount: .2 }}><Sparkles size={18}/><div><small>REVIEW SUMMARY</small><p>{data.summary}</p></div><span><Check size={14}/> Saved</span></motion.section>
    <div className="metadata-card">{[['DOCUMENT', data.document_type], ['EXTRACTION', data.extraction_method?.replaceAll('_', ' ') || 'provided text'], ['OCR ENGINE', data.ocr_engine || 'Not used'], ['AI EXTRACTION', data.analysis_provider || 'Deterministic'], ['AI MODEL', data.analysis_model || 'Source rules'], ['OCR STATUS', ocrStatus.replaceAll('_', ' ')], ['PAGES', String(data.pages_processed ?? 0)], ['OCR CONFIDENCE', data.ocr_confidence == null ? 'Not applicable' : `${Math.round(data.ocr_confidence * 100)}%`], ['READABILITY', data.readability || data.extraction_quality], ['SCRIPTS', detectedScripts.join(', ') || 'Not detected']].map(([label, value]) => <div key={label}><small>{label}</small><b>{value}</b></div>)}</div>
    {data.analysis_note && <div className="warning-banner analysis-note" role="status"><AlertCircle size={16}/><span>{data.analysis_note}</span></div>}
    {pageProcessing.length > 0 && <div className="page-metadata"><b>Page processing</b>{pageProcessing.map(page => <span key={page.page_number}>Page {page.page_number}: {page.method.replaceAll('_', ' ')} · {page.chars_extracted} chars · {page.ocr_status.replaceAll('_', ' ')}</span>)}</div>}
    <div className="disclaimer"><Info size={15}/>{data.disclaimer} Verify extracted details against the source.</div>
    {data.ml_prediction && <motion.section className="ml-panel report-reveal" variants={reveal} initial="hidden" whileInView="show" viewport={{ once: true, amount: .25 }}><div className="ml-head"><div><small>DOCUMENT WORKFLOW MODEL</small><h2>{data.ml_prediction.category.replaceAll('_', ' ')}</h2></div><span>{data.ml_prediction.confidence_label} confidence · <AnimatedPercent value={data.ml_prediction.confidence}/></span></div><div className="prob-list">{data.ml_prediction.probabilities.map(probability => <div key={probability.category}><span>{probability.category.replaceAll('_', ' ')}</span><div><motion.i initial={{ width: 0 }} whileInView={{ width: `${probability.probability * 100}%` }} viewport={{ once: true }} transition={{ duration: .65, delay: .12 }}/></div><b>{Math.round(probability.probability * 100)}%</b></div>)}</div><small>{data.ml_prediction.model_name} v{data.ml_prediction.model_version}. {data.ml_prediction.disclaimer} Scores are not calibrated clinical probabilities.</small></motion.section>}
    <motion.div className="report-sections" variants={staggerVariants} initial="hidden" whileInView="show" viewport={{ once: true, amount: .12 }}>
      <Section id="patient" title="Patient information" items={Object.entries(data.patient_information).map(([key, value]) => ({ text: `${key.replaceAll('_', ' ')}: ${value || 'Not available'}`, certainty: 'unknown' }))} empty="No patient details were found."/>
      <Section id="administrative-info" title="Administrative agreement information" items={data.administrative_information ?? []} empty="No billing, consent, or administrative terms were found."/>
      <Section id="symptoms" title="Symptoms" items={data.symptoms}/><Section id="diagnoses" title="Diagnoses" items={data.diagnoses}/><Section id="medications" title="Medications" items={data.medications}/>
      <Section id="vitals" title="Vital signs" items={Object.entries(data.vitals).map(([key, value]) => ({ text: `${key.replaceAll('_', ' ')}: ${value}`, certainty: 'unknown' }))} empty="No vital signs were found."/><Section title="Allergies" items={data.allergies}/><Section title="Lab tests" id="lab-tests" items={data.lab_tests ?? []}/><Section title="Follow-up" items={data.follow_up ?? []}/><Section id="advice" title="Doctor’s advice" items={data.doctor_advice ?? []}/><Section title="Clinical observations" items={data.clinical_observations}/><Section id="concerns" title="Clinical concerns" items={data.clinical_concerns}/><Section id="unclassified" title="Other source information · verify" items={data.unclassified_information ?? []} empty="No additional unclassified clinical statements were found."/>
    </motion.div>
    <motion.section id="review-items" className="attention-panel report-reveal" variants={reveal} initial="hidden" whileInView="show" viewport={{ once: true, amount: .2 }}><h3>Items to review</h3>{[['Missing information', data.missing_information], ['Potential inconsistencies', data.potential_inconsistencies], ['Review flags', data.requires_review]].map(([title, items]) => <div key={title as string}><b>{title as string}</b>{(items as string[]).length ? (items as string[]).map((item, index) => <p key={index}><i/>{item}</p>) : <small>None flagged.</small>}</div>)}</motion.section>
    <button className="technical-toggle" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Hide' : 'Show'} structured data <ChevronDown size={15}/></button><AnimatePresence>{expanded && <motion.pre initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>{JSON.stringify(data, null, 2)}</motion.pre>}</AnimatePresence>
  </div>
}

function SourceViewer({ report, file, close }: { report: Report; file: File | null; close: () => void }) {
  const sourceText = report.report?.raw_ocr_text || report.report?.normalized_text || 'No OCR text was stored for this report.'
  const url = useMemo(() => file ? URL.createObjectURL(file) : '', [file])
  const dialog = useRef<HTMLElement>(null)
  useEffect(() => () => { if (url) URL.revokeObjectURL(url) }, [url])
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
      if (event.key === 'Tab' && dialog.current) {
        const controls = [...dialog.current.querySelectorAll<HTMLElement>('button,[href],iframe,[tabindex]:not([tabindex="-1"])')].filter(element => !element.hasAttribute('disabled'))
        if (!controls.length) return
        const lastControl = controls[controls.length - 1]
        if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); lastControl?.focus() }
        else if (!event.shiftKey && document.activeElement === lastControl) { event.preventDefault(); controls[0].focus() }
      }
    }
    document.body.style.overflow = 'hidden'; document.addEventListener('keydown', onKey); dialog.current?.focus()
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', onKey); previous?.focus() }
  }, [close])
  return <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={close}><motion.section ref={dialog} tabIndex={-1} className="source-modal" role="dialog" aria-modal="true" aria-labelledby="source-title" initial={{ opacity: 0, y: 18, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: .99 }} onClick={event => event.stopPropagation()}><header><div><small>SOURCE VERIFICATION</small><h2 id="source-title">Original and recognized text</h2></div><button className="icon-button" aria-label="Close source view" onClick={close}><X size={17}/></button></header><div className="source-columns"><section><h3>Original document</h3>{url && file?.type.startsWith('image/') ? <img className="source-preview" src={url} alt={`Original ${file.name}`}/> : url && file?.type === 'application/pdf' ? <iframe title="Original PDF" src={url}/> : <p className="source-unavailable">The original file is not stored with saved reports. Compare the extracted text with your local source document.</p>}</section><section><h3>OCR source text</h3><pre>{sourceText}</pre><small>{report.report?.ocr_engine || 'Native PDF/text extraction'} · {report.report?.ocr_blocks?.length || 0} OCR blocks</small></section></div><div className="source-footer"><span>Source excerpts remain as recognized; no translation is generated here.</span><button className="secondary-button" onClick={close}>Close</button></div></motion.section></motion.div>
}

function AnimatedCard({ children, className }: { children: React.ReactNode; className: string }) {
  const setSpotlight = (event: React.PointerEvent<HTMLElement>) => {
    if (!event.currentTarget.matches(':hover') || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const rect = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty('--spot-x', `${event.clientX - rect.left}px`)
    event.currentTarget.style.setProperty('--spot-y', `${event.clientY - rect.top}px`)
  }
  return <motion.article className={`${className} motion-card`} onPointerMove={setSpotlight} whileHover={{ y: -2, scale: 1.006 }} whileTap={{ scale: .995 }} transition={{ duration: .18 }}>{children}</motion.article>
}
function Section({ id, title, items, empty = 'None documented.' }: { id?: string; title: string; items: Finding[]; empty?: string }) { return <motion.section id={id} className="report-section report-reveal" variants={staggerItemVariants}><div><h3>{title}</h3><span>{items.length}</span></div>{items.length ? <ul>{items.map((item, index) => <motion.li key={`${item.text}-${index}`} initial={{ opacity: 0, x: -5 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>{item.text}<small>{item.certainty}</small>{item.reason && <small className="finding-review-note">{item.reason}</small>}</motion.li>)}</ul> : <p>{empty}</p>}</motion.section> }
