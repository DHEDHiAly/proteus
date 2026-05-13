import { useState, useRef, useEffect, FormEvent } from 'react'
import type { PatientInfo, AgentMessage } from '../types/agent'
import { agentApi } from '../services/agent'
import ChatMessage from '../components/ChatMessage'
import PatientForm from '../components/PatientForm'
import PDBeViewer from '../components/PDBeViewer'

export default function AgentPage() {
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [input, setInput] = useState('')
  const [patient, setPatient] = useState<PatientInfo | null>(null)
  const [showForm, setShowForm] = useState(true)
  const [loading, setLoading] = useState(false)
  const [structure, setStructure] = useState<{ pdbId: string; mutations: any[] } | null>(null)
  const chatEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!patient) return
    agentApi.greet().then((res) => {
      setMessages([{ role: 'agent', content: res.data.reply }])
    }).catch(() => {})
  }, [patient])

  const handlePatientSubmit = (info: PatientInfo) => {
    setPatient(info)
    setShowForm(false)
  }

  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || !patient || loading) return

    const userMsg: AgentMessage = { role: 'user', content: input }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await agentApi.design(patient, input)
      setMessages(res.data.messages)
      if (res.data.pdb_id) {
        setStructure({ pdbId: res.data.pdb_id, mutations: res.data.mutations || [] })
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: 'Sorry, the design request failed. Please try again.', data: { status: 'error' } },
      ])
    }
    setLoading(false)
  }

  const quickActions = [
    'Design a peptide for this patient',
    'What target should I use?',
    'Explain the design process',
  ]

  if (!patient) {
    return (
      <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center">
        <div className="w-full max-w-lg">
          <div className="text-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-proteus-100 flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl text-proteus-700 font-bold">P</span>
            </div>
            <h1 className="text-2xl font-bold">Proteus AI Designer</h1>
            <p className="text-gray-500 text-sm mt-1">
              Enter patient information to design a targeted peptide therapy
            </p>
          </div>
          <div className="card">
            <PatientForm onSubmit={handlePatientSubmit} />
          </div>
          <p className="text-center text-xs text-gray-400 mt-4">
            FOR RESEARCH USE ONLY. Not a medical device.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-lg font-bold">Proteus AI</h1>
            <p className="text-xs text-gray-500">{patient.full_name} &middot; {patient.cancer_type} Stage {patient.cancer_stage}</p>
          </div>
          <button onClick={() => setShowForm(!showForm)} className="text-xs text-proteus-600 hover:text-proteus-700">
            {showForm ? 'Hide' : 'Edit'} Patient Info
          </button>
        </div>

        {showForm && (
          <div className="mb-4 card p-4">
            <PatientForm onSubmit={handlePatientSubmit} initial={patient} />
          </div>
        )}

        <div className="flex-1 overflow-y-auto space-y-1 px-1">
          {messages.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <p>Ask Proteus to design a peptide therapy</p>
              <div className="flex flex-wrap justify-center gap-2 mt-4">
                {quickActions.map((action) => (
                  <button
                    key={action}
                    onClick={() => { setInput(action); setTimeout(() => document.getElementById('chat-input')?.focus(), 100) }}
                    className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-3 py-1.5 rounded-full transition-colors"
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessage
              key={i}
              message={msg}
              onStructureClick={(pdbId, mutations) => setStructure({ pdbId, mutations })}
            />
          ))}
          <div ref={chatEnd} />
        </div>

        <form onSubmit={handleSend} className="mt-3 flex items-center space-x-2">
          <input
            id="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Proteus to design a peptide, explain results, or suggest a target..."
            className="input-field flex-1"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="btn-primary px-6 disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center space-x-1">
                <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                <span>Designing...</span>
              </span>
            ) : (
              'Send'
            )}
          </button>
        </form>
      </div>

      {structure && (
        <div className="w-[420px] flex-shrink-0">
          <PDBeViewer
            pdbId={structure.pdbId}
            mutations={structure.mutations}
            height={500}
          />
          <button
            onClick={() => setStructure(null)}
            className="mt-2 text-xs text-gray-500 hover:text-gray-700"
          >
            Close viewer
          </button>
        </div>
      )}
    </div>
  )
}
