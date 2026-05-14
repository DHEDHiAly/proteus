import { useState, useRef, useEffect, FormEvent, useCallback } from 'react';
import type { PatientInfo, AgentMessage } from '../types/agent';
import { agentApi } from '../services/agent';
import PatientForm from '../components/PatientForm';
import FileUpload from '../components/FileUpload';
import WidgetContainer from '../components/WidgetContainer';
import ProgressWidget from '../components/ProgressWidget';
import ResultsPanel from '../components/ResultsPanel';
import CommandPalette, { useCommandPalette } from '../components/CommandPalette';

type Candidate = {
  rank: number; sequence: string; binding_score: number;
  stability_score: number; solubility_score: number; total_energy?: number;
  num_mutations_from_seed?: number;
};

export default function AgentPage() {
  const [mode, setMode] = useState<'landing' | 'workspace'>('landing');
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [input, setInput] = useState('');
  const [patient, setPatient] = useState<PatientInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | undefined>();
  const [isRunning, setIsRunning] = useState(false);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [seed, setSeed] = useState<string | undefined>();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeViewerPdb, setActiveViewerPdb] = useState<string>('6LU7');
  const [activeViewerMuts, setActiveViewerMuts] = useState<any[]>([]);
  const [showPatientForm, setShowPatientForm] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [hoveredTarget, setHoveredTarget] = useState<number | null>(null);
  const [comparisonMode, setComparisonMode] = useState(false);
  const [compareRun, setCompareRun] = useState<any>(null);

  const chatEnd = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { isOpen: paletteOpen, setIsOpen: setPaletteOpen } = useCommandPalette();

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const enterWorkspace = useCallback((info: PatientInfo) => {
    setError(null); setPatient(info); setMode('workspace'); setShowPatientForm(false);
    setMessages([{
      role: 'agent',
      content: `Clinical intake recorded.\n\n**Patient:** ${info.full_name || 'Unnamed'}, ${info.age || '—'} years\n**Condition:** ${info.cancer_type}\n${info.tumor_markers ? `**Markers:** ${info.tumor_markers}\n` : ''}${info.previous_treatments ? `**Prior treatment:** ${info.previous_treatments}\n` : ''}${info.brain_metastasis ? '**CNS involvement:** Yes\n' : ''}\nReady to design. What should I target?`,
    }]);
    setTimeout(() => inputRef.current?.focus(), 300);
  }, []);

  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || !patient || loading) return;
    setError(null);
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    setInput('');
    setLoading(true);
    setIsRunning(true);

    try {
      const res = await agentApi.design(patient, input);
      setMessages(res.data.messages);
      setIsRunning(false);
      if (res.data.run_id) setCurrentRunId(res.data.run_id);
      if (res.data.candidate_sequence) {
        setCandidates((prev) => {
          const ranked = (res.data.messages
            .filter((m) => m.data?.status === 'round_complete' || m.data?.status === 'complete')
            .flatMap((m) => m.data?.rounds || [])
            .map((r: any, i: number) => ({
              rank: i + 1, sequence: r.sequence || '',
              binding_score: r.binding_score || 0, stability_score: r.stability_score || 0,
              solubility_score: r.solubility_score || 0, total_energy: r.total_energy,
            })) as Candidate[]);
          return ranked.length > 0 ? ranked : prev;
        });
        const last = res.data.messages[res.data.messages.length - 1];
        if (last?.data?.pdb_id) {
          setActiveViewerPdb(last.data.pdb_id);
          setActiveViewerMuts(res.data.mutations || []);
          setSeed(last.data.seed || res.data.candidate_sequence);
        }
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Request failed';
      setError(detail);
      setMessages((prev) => [...prev, { role: 'agent', content: `Error: ${detail}`, data: { status: 'error' } }]);
      setIsRunning(false);
    }
    setLoading(false);
  };

  const handleExport = (seq: string, format: string) => {
    const blob = new Blob([seq], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `proteus-${seq.slice(0, 6)}.${format.toLowerCase()}`;
    a.click();
  };

  const paletteCommands = [
    { id: 'new-run', label: 'New design run', category: 'Run', action: () => { setMode('landing'); setMessages([]); setCandidates([]); } },
    { id: 'compare', label: 'Toggle comparison mode', category: 'View', action: () => setComparisonMode((p) => !p) },
    { id: 'export-all', label: 'Export all candidates as FASTA', category: 'Export', action: () => candidates.forEach((c) => handleExport(c.sequence, 'fasta')) },
    { id: 'toggle-sidebar', label: 'Toggle chat sidebar', category: 'View', action: () => setSidebarOpen((p) => !p) },
    { id: 'upload', label: 'Upload PDB / sequence', category: 'File', action: () => setShowUpload((p) => !p) },
  ];

  if (mode === 'landing') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-black">
        <div className="w-full max-w-3xl space-y-6 animate-fade-in">
          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-4">
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
            <h1 className="text-3xl font-bold tracking-tight">Proteus</h1>
            <p className="text-gray-500 text-sm mt-2 max-w-lg mx-auto leading-relaxed">
              Describe a condition and Proteus researches the target, then designs, folds, and evaluates
              candidate protein therapeutics — autonomously.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="md:col-span-3 bg-[#111] border border-[#222] rounded-xl p-5 animate-slide-up">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Describe Patient</h2>
                <span className="flex items-center space-x-1.5 text-[9px] text-gray-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500/60 animate-pulse" />
                  <span>Ready</span>
                </span>
              </div>
              <p className="text-[11px] text-gray-600 mb-3 leading-relaxed">Start with the clinical presentation. Genetic details can be added after.</p>
              <PatientForm onSubmit={enterWorkspace} />
            </div>
            <div className="md:col-span-2 space-y-3">
              <div className="bg-[#111] border border-[#222] rounded-xl p-5 animate-slide-up" style={{animationDelay:'80ms'}}>
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">Upload Target</h2>
                <p className="text-[10px] text-gray-600 mb-2">Upload any PDB file or enter a PDB ID to design against any target.</p>
                <FileUpload
                  onPDBUpload={(pdbId) => setActiveViewerPdb(pdbId)}
                  onSequenceInput={(seq) => enterWorkspace({
                    full_name: 'Researcher', age: 0, cancer_type: 'Custom sequence uploaded',
                    cancer_stage: '', tumor_markers: '', previous_treatments: '',
                    brain_metastasis: false, notes: `Custom seed: ${seq}`,
                  })}
                />
              </div>
              <div className="bg-[#111] border border-[#222] rounded-xl p-5 animate-slide-up" style={{animationDelay:'160ms'}}>
                <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Example Targets</h2>
                <p className="text-[10px] text-gray-600 mb-2">Click any to try a demo. You can design <span className="text-white/60">against any PDB target</span>.</p>
                <div className="space-y-1.5 text-xs">
                  {[
                    { name: 'EGFRvIII', pdb: '3gp1', tag: 'Receptor' },
                    { name: 'PD-L1', pdb: '4zqk', tag: 'Checkpoint' },
                    { name: 'KRAS G12C', pdb: '6OIM', tag: 'Oncoprotein' },
                    { name: '3CL Protease', pdb: '6LU7', tag: 'Viral' },
                  ].map((t, idx) => (
                    <button key={t.name}
                      onMouseEnter={() => setHoveredTarget(idx)}
                      onMouseLeave={() => setHoveredTarget(null)}
                      onClick={() => enterWorkspace({ full_name: 'Demo', age: 55, cancer_type: t.name, cancer_stage: 'IV', tumor_markers: t.name, previous_treatments: '', brain_metastasis: false, notes: '' })}
                      className={`group w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-all duration-200 ${hoveredTarget === idx ? 'border-white/30 bg-white/[0.03] translate-x-0.5' : 'border-[#222]'}`}>
                      <div>
                        <div className="font-medium text-white text-[12px]">{t.name}</div>
                        <div className="text-gray-600 text-[9px]">{t.pdb} — {t.tag}</div>
                      </div>
                      <span className={`text-[10px] transition-all duration-200 ${hoveredTarget === idx ? 'text-white' : 'text-gray-700'}`}>→</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <p className="text-center text-[10px] text-gray-600">FOR RESEARCH USE ONLY. Not a medical device.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-black text-white overflow-hidden">
      {/* Top Nav */}
      <nav className="flex items-center justify-between px-4 h-11 border-b border-[#1a1a1a] flex-shrink-0">
        <div className="flex items-center space-x-3">
          <button onClick={() => setSidebarOpen((p) => !p)}
            className="w-7 h-7 flex items-center justify-center rounded hover:bg-white/10 text-gray-500 hover:text-white transition-colors text-xs"
            aria-label="Toggle sidebar">☰</button>
          <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-5 h-5">
            <defs><linearGradient id="nl" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#fff"/><stop offset="50%" stop-color="#666"/><stop offset="100%" stop-color="#fff"/>
            </linearGradient></defs>
            <g stroke="url(#nl)" strokeWidth="2.5" strokeLinecap="round" fill="none">
              <path d="M30 15 Q50 25 70 15 Q50 5 30 15" opacity=".9"/>
              <path d="M30 35 Q50 45 70 35 Q50 25 30 35" opacity=".7"/>
              <path d="M30 55 Q50 65 70 55 Q50 45 30 55" opacity=".5"/>
              <path d="M30 75 Q50 85 70 75 Q50 65 30 75" opacity=".3"/>
              <line x1="30" y1="15" x2="30" y2="75" opacity=".6"/>
              <line x1="70" y1="15" x2="70" y2="75" opacity=".6"/>
            </g>
          </svg>
          <span className="text-sm font-bold tracking-tight">Proteus</span>
          {patient && (
            <span className="text-[10px] text-gray-600 ml-2 hidden sm:inline">
              {patient.cancer_type} {patient.tumor_markers && `· ${patient.tumor_markers}`}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <span className={`flex items-center space-x-1 text-[10px] px-2 py-0.5 rounded-full ${
            isRunning ? 'bg-green-900/30 text-green-400 border border-green-900/50' :
            candidates.length > 0 ? 'bg-white/5 text-gray-400 border border-[#222]' :
            'text-gray-600'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-green-400 animate-pulse' : candidates.length > 0 ? 'bg-gray-500' : 'bg-gray-700'}`} />
            {isRunning ? 'Running' : candidates.length > 0 ? 'Complete' : 'Ready'}
          </span>
          <button onClick={() => setComparisonMode((p) => !p)}
            className={`text-[10px] px-2 py-1 rounded border transition-all ${
              comparisonMode ? 'border-white/40 bg-white/10 text-white' : 'border-[#222] text-gray-500 hover:text-white hover:border-[#444]'
            }`}>⇄ Compare</button>
          <button onClick={() => setShowUpload((p) => !p)}
            className="text-[10px] px-2 py-1 rounded border border-[#222] text-gray-500 hover:text-white hover:border-[#444] transition-all">Upload</button>
          <button onClick={() => setMode('landing')}
            className="text-[10px] text-gray-600 hover:text-white transition-colors">Exit</button>
        </div>
      </nav>

      {/* Main 3-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat sidebar */}
        {sidebarOpen && (
          <aside className="w-[280px] flex-shrink-0 border-r border-[#1a1a1a] flex flex-col bg-[#050505]">
            <div className="flex-1 overflow-y-auto p-3 space-y-1">
              {messages.length === 0 && (
                <div className="text-center py-16 text-gray-600">
                  <p className="text-xs">Ready to design</p>
                  <div className="flex flex-col gap-1.5 mt-4">
                    {['Design a peptide', 'Explain the process', 'What target?'].map((a) => (
                      <button key={a} onClick={() => { setInput(a); setTimeout(() => inputRef.current?.focus(), 50); }}
                        className="text-[10px] border border-[#222] hover:border-white/30 text-gray-400 hover:text-white px-3 py-1.5 rounded-full transition-all">
                        {a}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`text-xs leading-relaxed ${msg.role === 'user' ? 'text-white bg-white/5 rounded-lg px-3 py-2' : 'text-gray-300'}`}>
                  {msg.role === 'agent' && (
                    <div className="flex items-center space-x-1 mb-1">
                      <svg viewBox="0 0 100 100" fill="none" className="w-3 h-3">
                        <g stroke="#666" strokeWidth="3" strokeLinecap="round" fill="none">
                          <path d="M30 15 Q50 25 70 15" opacity=".9"/>
                          <line x1="30" y1="15" x2="30" y2="35" opacity=".6"/>
                          <line x1="70" y1="15" x2="70" y2="35" opacity=".6"/>
                        </g>
                      </svg>
                      <span className="text-[9px] text-gray-600 uppercase tracking-wider">Proteus</span>
                    </div>
                  )}
                  <div className="whitespace-pre-wrap break-words">{msg.content.length > 400 ? msg.content.slice(0, 400) + '...' : msg.content}</div>
                </div>
              ))}
              <div ref={chatEnd} />
            </div>
            <div className="p-3 border-t border-[#1a1a1a]">
              <form onSubmit={handleSend} className="flex space-x-1.5">
                <input ref={inputRef} type="text" value={input} onChange={(e) => setInput(e.target.value)}
                  placeholder="Message..." className="flex-1 bg-[#111] border border-[#222] rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-[#444]" disabled={loading} />
                <button type="submit" disabled={loading || !input.trim()}
                  className="px-3 py-1.5 bg-white text-black rounded-lg text-[10px] font-medium disabled:opacity-30">→</button>
              </form>
            </div>
          </aside>
        )}

        {/* Center: 3D Viewer */}
        <main className={`flex-1 flex flex-col min-w-0 ${comparisonMode ? 'w-1/2' : ''}`}>
          <div className="flex-1 relative bg-[#000]">
            <div className="absolute inset-3">
              <div className="h-full rounded-xl border border-[#1a1a1a] overflow-hidden bg-[#050505]">
                {activeViewerPdb && (
                  <iframe
                    src={`https://embed.rcsb.org/3d/${activeViewerPdb}?style=stick&color=spectrum&showControls=true`}
                    style={{ width: '100%', height: '100%', border: 'none' }}
                    title="Protein structure"
                  />
                )}
                {activeViewerMuts.length > 0 && (
                  <div className="absolute bottom-3 left-3 flex flex-wrap gap-1">
                    {activeViewerMuts.map((m: any, i: number) => (
                      <span key={i} className="text-[9px] font-mono bg-red-900/60 text-red-300 px-1.5 py-0.5 rounded">
                        {m.from}{m.position}{m.to}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Progress bar below viewer */}
          {isRunning && currentRunId && (
            <div className="h-20 border-t border-[#1a1a1a] p-2">
              <ProgressWidget runId={currentRunId} isRunning={isRunning} />
            </div>
          )}
        </main>

        {/* Right: Results panel */}
        <aside className="w-[300px] flex-shrink-0 border-l border-[#1a1a1a] bg-[#050505] overflow-y-auto">
          <div className="p-3 border-b border-[#1a1a1a] flex items-center justify-between">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Candidates</span>
            {candidates.length > 0 && (
              <span className="text-[9px] text-gray-600">{candidates.length} results</span>
            )}
          </div>
          <div className="p-2">
            <ResultsPanel
              candidates={candidates}
              seed={seed}
              onInspect={(seq) => {
                const c = candidates.find((x) => x.sequence === seq);
                if (c) setActiveViewerMuts(seed ? seed.split('').map((a, i) => ({ from: a, to: seq[i] || a, position: i + 1 })).filter((m) => m.from !== m.to) : []);
              }}
              onExport={handleExport}
            />
          </div>
        </aside>
      </div>

      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} commands={paletteCommands} />
    </div>
  );
}
