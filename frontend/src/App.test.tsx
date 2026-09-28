import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from './App'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('review submission', () => {
  it('shows the workflow image and disables analyze until input is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }))
    render(<App />)

    expect(screen.getByRole('heading', { name: /clinical clarity.*grounded in source/i })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /document workflow illustration/i })).toHaveAttribute('src', '/workflow-pipeline.png')
    fireEvent.click(screen.getByRole('button', { name: 'Documents' }))
    expect(await screen.findByRole('img', { name: /document to OCR/i })).toBeInTheDocument()
    const slider = await screen.findByRole('slider', { name: /slide to analyze document/i })
    expect(slider).toBeDisabled()
    fireEvent.change(screen.getByRole('textbox', { name: /clinical note text/i }), { target: { value: 'Synthetic note with fever.' } })
    expect(slider).toBeEnabled()
  })

  it('starts the real API request from the accessible slider and shows backend errors', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: false, json: async () => ({ detail: 'Synthetic test backend error.' }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Documents' }))
    fireEvent.change(await screen.findByRole('textbox', { name: /clinical note text/i }), { target: { value: 'Synthetic note with cough.' } })
    const slider = screen.getByRole('slider', { name: /slide to analyze document/i })
    fireEvent.keyDown(slider, { key: 'Enter' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Synthetic test backend error.')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [, request] = fetchMock.mock.calls[1] as [string, RequestInit]
    expect((request.body as FormData).get('text')).toBe('Synthetic note with cough.')
  })

  it('renders an older saved report that predates OCR metadata fields', async () => {
    const legacyReport = {
      id: 'legacy-1', created_at: '2026-09-28T10:00:00Z', input_type: 'text', filename: null,
      status: 'completed', summary: 'Legacy summary', processing_error: null,
      report: {
        summary: 'Synthetic legacy report summary.', patient_information: {},
        symptoms: [{ text: 'fever', certainty: 'medium' }], diagnoses: [], medications: [], vitals: {}, allergies: [],
        clinical_observations: [], clinical_concerns: [], missing_information: [], potential_inconsistencies: [],
        requires_review: [], extraction_quality: 'readable', disclaimer: 'Synthetic review.', document_type: 'text',
        extraction_method: 'provided_text', ocr_used: false, ocr_confidence: null, readability: 'readable',
        ocr_blocks: [], ml_prediction: null,
      },
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [legacyReport] })
      .mockResolvedValueOnce({ ok: true, json: async () => legacyReport })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)

    expect(await screen.findByText('Legacy summary')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'AI Review' }))
    expect(await screen.findByRole('heading', { name: 'Clinical review' })).toBeInTheDocument()
    expect(screen.getByText('Synthetic legacy report summary.')).toBeInTheDocument()
  })

  it('shows recovery UI if the server returns no report body', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'empty', report: null }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Documents' }))
    fireEvent.change(await screen.findByRole('textbox', { name: /clinical note text/i }), { target: { value: 'Synthetic note with fever.' } })
    fireEvent.keyDown(screen.getByRole('slider', { name: /slide to analyze document/i }), { key: 'Enter' })
    expect(await screen.findByRole('alert')).toHaveTextContent('did not contain a clinical report')
    expect(screen.queryByRole('heading', { name: 'Clinical review' })).not.toBeInTheDocument()
  })
})
