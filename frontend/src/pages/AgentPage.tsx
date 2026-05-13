import { useState, useRef, useEffect, FormEvent } from 'react'
import type { PatientInfo, AgentMessage } from '../types/agent'
import { agentApi } from '../services/agent'
import ChatMessage from '../components/ChatMessage'
import PatientForm from '../components/PatientForm'

export default function AgentPage() {
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [input, setInput] = useState('')
  const [patient, setPatient] = useState<PatientInfo | null>(null)
  const [showForm, setShowForm] = useState(true)
  const [loading, setLoading] = useState(false)
  const [structure, setStructure] = useState<{ pdbId: string; mutations: any[] } | null>(null)
  const chatEnd = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    if (!patient) return
    agentApi.greet().then((res) => {
      const replies = res.data.reply.split('\n\nTo get started')
      setMessages([{ role: 'agent', content: replies[0] + '\n\n' + (replies[1] ? 'To get started' + replies[1] : '') }])
    }).catch(() => {})
  }, [patient])

  const handlePatientSubmit = (info: PatientInfo) => {
    setPatient(info)
    setShowForm(false)
    setMessages([{
      role: 'agent',
      content: `Patient intake complete. **${info.full_name}**, ${info.age}yo — ${info.cancer_type} (Stage ${info.cancer_stage}).\n\nType a message to begin, or click one of the suggestions below.`,
    }])
    setTimeout(() => inputRef.current?.focus(), 200)
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
      if (res.data.pdb_id && res.data.candidate_sequence) {
        setStructure({ pdbId: res.data.pdb_id, mutations: res.data.mutations || [] })
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: 'Error: design pipeline failed. Please try again.', data: { status: 'error' } },
      ])
    }
    setLoading(false)
  }

  const suggestions = [
    'Design a peptide targeting this cancer',
    'Which target protein matches this case?',
    'Run full autonomous pipeline',
  ]

  if (!patient) {
    return (
      <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="w-14 h-14 rounded-xl border border-white/20 flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl font-bold">P</span>
            </div>
            <h1 className="text-xl font-bold tracking-tight">Proteus</h1>
            <p className="text-gray-500 text-sm mt-1">Autonomous protein design workspace</p>
          </div>
          <div className="card">
            <PatientForm onSubmit={handlePatientSubmit} />
          </div>
          <p className="text-center text-[10px] text-gray-600 mt-4">
            FOR RESEARCH USE ONLY. Not a medical device.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-3">
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-3">
            <div className="w-7 h-7 rounded border border-white/20 flex items-center justify-center">
              <span className="text-xs font-bold">P</span>
            </div>
            <div>
              <h1 className="text-sm font-bold">Proteus Workspace</h1>
              <p className="text-[10px] text-gray-500">
                {patient.full_name} &middot; {patient.cancer_type} Stage {patient.cancer_stage}
                {patient.tumor_markers && ` · ${patient.tumor_markers}`}
              </p>
            </div>
          </div>
          <button onClick={() => setShowForm(!showForm)}
            className="text-[10px] text-gray-500 hover:text-white transition-colors">
            {showForm ? '× Close' : '✎ Edit'} Patient
          </button>
        </div>

        {showForm && (
          <div className="mb-3 card p-4">
            <PatientForm onSubmit={handlePatientSubmit} initial={patient} />
          </div>
        )}

        <div className="flex-1 overflow-y-auto space-y-1 pr-1 scroll-smooth">
          {messages.length === 0 && (
            <div className="text-center py-16 text-gray-600">
              <p className="text-sm">Enter a message to begin the design process</p>
              <div className="flex flex-wrap justify-center gap-2 mt-4">
                {suggestions.map((a) => (
                  <button key={a} onClick={() => { setInput(a); setTimeout(() => inputRef.current?.focus(), 50) }}
                    className="text-xs border border-[#333] hover:border-white/30 text-gray-400 hover:text-white px-3 py-1.5 rounded-full transition-all">
                    {a}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg}
              onStructureClick={(pdbId, m) => setStructure({ pdbId, mutations: m })} />
          ))}
          <div ref={chatEnd} />
        </div>

        <form onSubmit={handleSend} className="mt-3 flex items-center space-x-2">
          <input ref={inputRef} type="text" value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Proteus to design, explain, or iterate..."
            className="input-field flex-1 text-sm" disabled={loading} />
          <button type="submit" disabled={loading || !input.trim()}
            className="btn-primary px-5 disabled:opacity-30 min-w-[80px]">
            {loading ? (
              <span className="flex items-center justify-center space-x-1.5">
                <span className="animate-pulse">●</span>
                <span className="text-[11px]">Run</span>
              </span>
            ) : 'Send'}
          </button>
        </form>
      </div>

      {structure && (
        <div className="w-[340px] flex-shrink-0 hidden lg:block">
          <div className="card p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">3D Structure</span>
              <button onClick={() => setStructure(null)}
                className="text-[10px] text-gray-600 hover:text-white transition-colors">✕</button>
            </div>
            <iframe
              src={`https://embed.rcsb.org/3d/${structure.pdbId}?style=stick&color=spectrum`}
              style={{ width: '100%', height: 340, border: 'none', borderRadius: 8 }}
              title="Protein structure"
            />
            {structure.mutations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {structure.mutations.map((m: any, i: number) => (
                  <span key={i} className="text-[10px] font-mono bg-white/10 text-white/80 px-1.5 py-0.5 rounded">
                    {m.from}{m.position}{m.to}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
