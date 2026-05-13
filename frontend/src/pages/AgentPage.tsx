import { useState, useRef, useEffect, FormEvent } from 'react';
import type { PatientInfo, AgentMessage } from '../types/agent';
import { agentApi } from '../services/agent';
import ChatMessage from '../components/ChatMessage';
import PatientForm from '../components/PatientForm';
import FileUpload from '../components/FileUpload';
import GLViewer from '../components/GLViewer';

type PageMode = 'landing' | 'workspace';

export default function AgentPage() {
  const [mode, setMode] = useState<PageMode>('landing');
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [input, setInput] = useState('');
  const [patient, setPatient] = useState<PatientInfo | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [structure, setStructure] = useState<{ pdbId: string; mutations: any[]; sequence?: string; seed?: string } | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const enterWorkspace = (info: PatientInfo) => {
    setPatient(info);
    setMode('workspace');
    setShowForm(false);
    setMessages([{
      role: 'agent',
      content: `Patient intake complete. **${info.full_name}**, ${info.age}yo — ${info.cancer_type} (Stage ${info.cancer_stage}).\n\nI'm ready to design a peptide therapy. Type a message to begin, or click a suggestion below.`,
    }]);
    setTimeout(() => inputRef.current?.focus(), 200);
  };

  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || !patient || loading) return;
    const userMsg: AgentMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await agentApi.design(patient, input);
      setMessages(res.data.messages);
      const last = res.data.messages[res.data.messages.length - 1];
      if (last?.data?.pdb_id) {
        setStructure({
          pdbId: last.data.pdb_id,
          mutations: res.data.mutations || [],
          sequence: last.data.sequence,
          seed: last.data.seed,
        });
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: 'Pipeline error. Please try again.', data: { status: 'error' } },
      ]);
    }
    setLoading(false);
  };

  if (mode === 'landing') {
    return (
      <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center">
        <div className="w-full max-w-2xl space-y-6">
          <div className="text-center">
            <div className="w-14 h-14 mx-auto mb-4">
              <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
                <defs><linearGradient id="dl" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#fff"/><stop offset="50%" stop-color="#666"/><stop offset="100%" stop-color="#fff"/>
                </linearGradient></defs>
                <g stroke="url(#dl)" strokeWidth="2.5" strokeLinecap="round" fill="none">
                  <path d="M30 15 Q50 25 70 15 Q50 5 30 15" opacity=".9"/>
                  <path d="M30 35 Q50 45 70 35 Q50 25 30 35" opacity=".7"/>
                  <path d="M30 55 Q50 65 70 55 Q50 45 30 55" opacity=".5"/>
                  <path d="M30 75 Q50 85 70 75 Q50 65 30 75" opacity=".3"/>
                  <line x1="30" y1="15" x2="30" y2="75" opacity=".6"/>
                  <line x1="70" y1="15" x2="70" y2="75" opacity=".6"/>
                </g>
              </svg>
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Proteus</h1>
            <p className="text-gray-500 text-sm mt-1 max-w-md mx-auto">
              Autonomous protein design workspace. Describe your target — or upload a PDB —
              and Proteus generates, folds, and evaluates candidate proteins using MCMC.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-[#111] border border-[#222] rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Quick Start</h2>
                <span className="flex items-center space-x-1 text-[9px] text-gray-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500/50 animate-pulse" />
                  <span>Ready</span>
                </span>
              </div>
              <PatientForm onSubmit={enterWorkspace} />
            </div>
            <div className="space-y-3">
              <div className="bg-[#111] border border-[#222] rounded-xl p-5">
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">Upload Target</h2>
                <FileUpload
                  onPDBUpload={(pdbId) => setStructure({ pdbId, mutations: [] })}
                  onSequenceInput={(seq) => {
                    enterWorkspace({
                      full_name: 'Demo', age: 50, cancer_type: 'Custom Target',
                      cancer_stage: 'IV', tumor_markers: '', previous_treatments: '',
                      brain_metastasis: false, notes: `Custom sequence: ${seq}`,
                    });
                  }}
                />
              </div>
              <div className="bg-[#111] border border-[#222] rounded-xl p-5">
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">
                  Universal Targets
                  <span className="text-gray-600 font-normal normal-case ml-1">— click to start</span>
                </h2>
                <div className="space-y-1.5 text-xs">
                  {[
                    { name: 'EGFRvIII', pdb: '3gp1', type: 'Receptor Tyrosine Kinase', domain: 'Oncology' },
                    { name: 'PD-L1', pdb: '4zqk', type: 'Immune Checkpoint', domain: 'Immunology' },
                    { name: 'KRAS G12C', pdb: '6OIM', type: 'GTPase Oncoprotein', domain: 'Oncology' },
                    { name: '3CL Protease', pdb: '6LU7', type: 'Viral Cysteine Protease', domain: 'Virology' },
                  ].map((t) => (
                    <button
                      key={t.name}
                      onClick={() => enterWorkspace({
                        full_name: 'Demo', age: 50, cancer_type: t.domain,
                        cancer_stage: 'IV', tumor_markers: t.name,
                        previous_treatments: '', brain_metastasis: false, notes: '',
                      })}
                      className="group w-full text-left px-3 py-2.5 rounded-lg border border-[#222] hover:border-white/30 hover:bg-white/[0.02] transition-all duration-200 hover:translate-x-0.5"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-white group-hover:text-white transition-colors">{t.name}</div>
                          <div className="text-gray-500 text-[10px] mt-0.5">{t.type}</div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[9px] text-gray-600 font-mono">{t.pdb}</span>
                          <span className="text-[9px] text-gray-700 border border-[#222] px-1.5 py-0.5 rounded">{t.domain}</span>
                          <span className="text-gray-700 group-hover:text-white transition-colors text-[10px]">→</span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {structure && (
            <div className="bg-[#111] border border-[#222] rounded-xl p-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Structure Preview</span>
                <button onClick={() => setStructure(null)} className="text-[10px] text-gray-600 hover:text-white transition-colors">✕</button>
              </div>
              <GLViewer pdbId={structure.pdbId} mutations={structure.mutations} height={300} />
            </div>
          )}

          <p className="text-center text-[10px] text-gray-600">
            FOR RESEARCH USE ONLY. Not a medical device.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-3">
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-3">
            <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-6 h-6">
              <defs><linearGradient id="wl" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#fff"/><stop offset="50%" stop-color="#666"/><stop offset="100%" stop-color="#fff"/>
              </linearGradient></defs>
              <g stroke="url(#wl)" strokeWidth="2.5" strokeLinecap="round" fill="none">
                <path d="M30 15 Q50 25 70 15 Q50 5 30 15" opacity=".9"/>
                <path d="M30 35 Q50 45 70 35 Q50 25 30 35" opacity=".7"/>
                <path d="M30 55 Q50 65 70 55 Q50 45 30 55" opacity=".5"/>
                <path d="M30 75 Q50 85 70 75 Q50 65 30 75" opacity=".3"/>
                <line x1="30" y1="15" x2="30" y2="75" opacity=".6"/>
                <line x1="70" y1="15" x2="70" y2="75" opacity=".6"/>
              </g>
            </svg>
            <div>
              <h1 className="text-sm font-bold">Proteus Workspace</h1>
              <p className="text-[10px] text-gray-500">
                {patient?.full_name} &middot; {patient?.cancer_type} Stage {patient?.cancer_stage}
                {patient?.tumor_markers && ` · ${patient.tumor_markers}`}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button onClick={() => setShowUpload(!showUpload)}
              className="text-[10px] text-gray-500 hover:text-white transition-colors">
              Upload
            </button>
            <button onClick={() => setShowForm(!showForm)}
              className="text-[10px] text-gray-500 hover:text-white transition-colors">
              {showForm ? 'Close' : 'Edit'} Patient
            </button>
            <button onClick={() => { setMode('landing'); setMessages([]); setStructure(null); }}
              className="text-[10px] text-gray-600 hover:text-white transition-colors">
              Exit
            </button>
          </div>
        </div>

        {showUpload && (
          <div className="mb-3">
            <FileUpload
              onPDBUpload={(pdbId) => setStructure({ pdbId, mutations: [] })}
              onSequenceInput={(seq) => setInput(`Use sequence as seed: ${seq}`)}
            />
          </div>
        )}

        {showForm && (
          <div className="mb-3 card p-4">
            <PatientForm onSubmit={(info) => { setPatient(info); setShowForm(false); }} initial={patient!} />
          </div>
        )}

        <div className="flex-1 overflow-y-auto space-y-1 pr-1 scroll-smooth">
          {messages.length === 0 && (
            <div className="text-center py-16 text-gray-600">
              <p className="text-sm">Enter a message to begin design</p>
              <div className="flex flex-wrap justify-center gap-2 mt-4">
                {[
                  'Design a peptide for this patient',
                  'Explain the design process',
                  'Which target protein matches this case?',
                ].map((a) => (
                  <button key={a} onClick={() => { setInput(a); setTimeout(() => inputRef.current?.focus(), 50); }}
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
              <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
                {structure.pdbId}
              </span>
              <button onClick={() => setStructure(null)}
                className="text-[10px] text-gray-600 hover:text-white transition-colors">✕</button>
            </div>
            <GLViewer
              pdbId={structure.pdbId}
              mutations={structure.mutations}
              sequence={structure.sequence}
              seed={structure.seed}
              height={340}
            />
          </div>
        </div>
      )}
    </div>
  );
}
