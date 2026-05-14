import { useRef, useState } from 'react';

interface FileUploadProps {
  onPDBUpload: (pdbId: string, fileName: string) => void;
  onSequenceInput: (seq: string) => void;
}

export default function FileUpload({ onPDBUpload, onSequenceInput }: FileUploadProps) {
  const [tab, setTab] = useState<'pdb' | 'sequence'>('pdb');
  const [pdbInput, setPdbInput] = useState('');
  const [seqInput, setSeqInput] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState('');

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const content = reader.result as string;
      if (file.name.endsWith('.pdb') || content.startsWith('ATOM') || content.startsWith('HETATM')) {
        onPDBUpload('custom', file.name);
      } else {
        const seq = content.replace(/[^ACDEFGHIKLMNPQRSTVWY]/gi, '').toUpperCase();
        if (seq.length > 0) onSequenceInput(seq);
      }
    };
    reader.readAsText(file);
  };

  const handlePdbLookup = () => {
    if (pdbInput.trim()) onPDBUpload(pdbInput.trim().toUpperCase(), pdbInput.trim());
  };

  const handleSeqSubmit = () => {
    const cleaned = seqInput.replace(/[^ACDEFGHIKLMNPQRSTVWY]/gi, '').toUpperCase();
    if (cleaned.length > 0) onSequenceInput(cleaned);
  };

  return (
    <div className="border border-[#222] rounded-lg p-3 space-y-2">
      <div className="flex space-x-1">
        <button
          onClick={() => setTab('pdb')}
          className={`text-[10px] px-2 py-1 rounded ${tab === 'pdb' ? 'bg-white/10 text-white' : 'text-gray-500'}`}
        >
          PDB Upload / Lookup
        </button>
        <button
          onClick={() => setTab('sequence')}
          className={`text-[10px] px-2 py-1 rounded ${tab === 'sequence' ? 'bg-white/10 text-white' : 'text-gray-500'}`}
        >
          Sequence Input
        </button>
      </div>

      {tab === 'pdb' ? (
        <div className="space-y-2">
          <div className="flex space-x-2">
            <input
              type="text"
              value={pdbInput}
              onChange={(e) => setPdbInput(e.target.value)}
              placeholder="PDB ID (e.g. 6LU7)"
              className="input-field text-xs flex-1"
              onKeyDown={(e) => e.key === 'Enter' && handlePdbLookup()}
            />
            <button onClick={handlePdbLookup} className="btn-primary text-[10px] px-3">Load</button>
          </div>
          <div className="flex items-center space-x-2">
            <div className="flex-1 h-px bg-[#222]" />
            <span className="text-[10px] text-gray-600">or</span>
            <div className="flex-1 h-px bg-[#222]" />
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdb,.fasta,.txt"
            onChange={handleFile}
            className="hidden"
          />
          <button onClick={() => fileRef.current?.click()} className="btn-secondary text-[10px] w-full">
            {fileName ? `Upload  ${fileName}` : 'Upload PDB File'}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            value={seqInput}
            onChange={(e) => setSeqInput(e.target.value)}
            placeholder="Paste amino acid sequence...&#10;e.g. MVLDGEQG"
            className="input-field text-xs font-mono"
            rows={3}
          />
          <button onClick={handleSeqSubmit} className="btn-primary text-[10px] w-full">Load Sequence</button>
        </div>
      )}
    </div>
  );
}
