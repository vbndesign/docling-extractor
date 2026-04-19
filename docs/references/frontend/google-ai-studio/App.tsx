import React, { useState, useRef, useEffect } from "react";
import { GoogleGenAI } from "@google/genai";
import { 
  FileText, 
  Link as LinkIcon, 
  Upload, 
  CheckCircle2, 
  AlertCircle, 
  Loader2,
  FolderOpen,
  ArrowRight,
  Clipboard,
  ExternalLink
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

// Initialize Gemini
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

interface ConversionResult {
  success: boolean;
  filename?: string;
  path?: string;
  error?: string;
}

export default function App() {
  const [url, setUrl] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [result, setResult] = useState<ConversionResult | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [health, setHealth] = useState<{ status: string; version: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const STAGES = [
    "Iniciando captura do conteúdo...",
    "Lendo as primeiras camadas do documento...",
    "Entendendo a estrutura de títulos e listas...",
    "Organizando tabelas e referências...",
    "Trabalhando na formatação final em Markdown...",
    "Finalizando o arquivo para o seu Vault..."
  ];

  useEffect(() => {
    fetch("/api/health")
      .then(res => res.json())
      .then(setHealth)
      .catch(() => console.error("Health check failed"));
      
    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, []);

  /**
   * Mantém a barra em movimento constante dentro de um intervalo de progresso.
   * Modificado para não ser interrompido bruscamente por novos dados.
   */
  const startProgressDrift = (target: number, speed: number = 0.2) => {
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    
    // Frequência maior (50ms) para um movimento mais fluido
    progressIntervalRef.current = setInterval(() => {
      setProgress(prev => {
        if (prev < target - 0.5) return prev + speed;
        return prev;
      });
    }, 50);
  };

  const stopProgressDrift = (finalValue?: number) => {
    if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
    }
    if (finalValue !== undefined) setProgress(finalValue);
  };

  const handleUrlConversion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    
    setIsProcessing(true);
    setResult(null);
    setProgress(0);

    try {
      // Etapa 1: Captura (0% -> 25%)
      setStatusMessage(STAGES[0]);
      startProgressDrift(25, 0.4);
      
      const proxyRes = await fetch("/api/proxy-fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const data = await proxyRes.json();
      if (data.error) throw new Error(data.error);
      const content = data.content;
      
      // Salta para 25% (fim da captura)
      setProgress(25);

      // Etapa 2: Análise & Conversão (25% -> 90%)
      setStatusMessage(STAGES[2]);
      const mdContent = await convertToMarkdownWithProgress(content, "url", url, 25, 90);

      // Etapa 3: Sistema de Arquivos (90% -> 100%)
      setStatusMessage(STAGES[5]);
      startProgressDrift(100, 0.8);
      
      const hostname = new URL(url).hostname.replace(/\./g, '_');
      const filename = `${hostname}-${Date.now()}.md`;
      const saveRes = await fetch("/api/save-markdown", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, content: mdContent })
      });
      const saveData = await saveRes.json();
      
      stopProgressDrift(100);
      setResult({ success: true, filename, path: saveData.path });
    } catch (err: any) {
      stopProgressDrift();
      setResult({ success: false, error: err.message });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!file || !file.type.includes("pdf")) {
      setResult({ success: false, error: "Apenas arquivos PDF são suportados." });
      return;
    }

    setIsProcessing(true);
    setResult(null);
    setProgress(0);

    try {
      // Etapa 1: Leitura Binária (0% -> 20%)
      setStatusMessage(STAGES[1]);
      startProgressDrift(20, 0.6);
      const base64 = await fileToBase64(file);
      setProgress(20);
      
      // Etapa 2: Processamento Estrutural (20% -> 90%)
      setStatusMessage(STAGES[2]);
      const mdContent = await convertToMarkdownWithProgress(base64, "pdf", file.name, 20, 90);

      // Etapa 3: Finalização (90% -> 100%)
      setStatusMessage(STAGES[5]);
      startProgressDrift(100, 1.2);
      
      const nameWithoutExt = file.name.replace(".pdf", "").replace(/\s+/g, '_');
      const filename = `${nameWithoutExt}-${Date.now()}.md`;
      const saveRes = await fetch("/api/save-markdown", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, content: mdContent })
      });
      const saveData = await saveRes.json();
      
      stopProgressDrift(100);
      setResult({ success: true, filename, path: saveData.path });
    } catch (err: any) {
      stopProgressDrift();
      setResult({ success: false, error: err.message });
    } finally {
      setIsProcessing(false);
    }
  };

  const convertToMarkdownWithProgress = async (data: string, type: "url" | "pdf", sourceName: string, startP: number, endP: number) => {
    const model = "gemini-3-flash-preview";
    const prompt = type === "url" 
      ? `Extract the core content from this HTML and convert it into high-fidelity, clean Markdown. 
         Preserve headings, tables, codes, and list structures. Remove ads, navigation, and boilerplate.
         Ensure the output is strictly Markdown. 
         Source Name: ${sourceName}
         
         HTML Content:
         ${data.substring(0, 30000)}` 
      : `Convert this PDF into high-fidelity, clean Markdown. 
         Preserve the structure perfectly (headings, tables, lists). 
         Extract text exactly from the original document.
         Source Name: ${sourceName}`;

    const contents = type === "url" 
      ? { parts: [{ text: prompt }] }
      : { 
          parts: [
            { text: prompt },
            { inlineData: { mimeType: "application/pdf", data: data.split(",")[1] || data } }
          ] 
        };

    const stream = await ai.models.generateContentStream({
      model,
      contents,
      config: {
        systemInstruction: "You are a specialized document conversion engine. Your goal is to produce faithful, clean Markdown from structured sources for a Zettelkasten system. Output ONLY the raw markdown content without any preamble, conversational text, or markdown code blocks wraps."
      }
    });

    let fullText = "";
    let localTick = 0;
    
    // Inicia um "drift" global para a etapa de conversão
    startProgressDrift(endP, 0.1);
    
    for await (const chunk of stream) {
        localTick++;
        fullText += chunk.text;
        
        // Mantemos o progresso saltando com os chunks, mas sem reiniciar o intervalo de drift
        setProgress(prev => {
            const chunkProgress = startP + (localTick * 1.2);
            // Só salta se o progresso do chunk for maior que o drift atual
            return Math.max(prev, Math.min(chunkProgress, endP));
        });
        
        // Atualiza mensagens baseadas em marcos lineares
        setProgress(current => {
            if (current > 45 && current <= 65) setStatusMessage(STAGES[3]);
            if (current > 65 && current <= 85) setStatusMessage(STAGES[4]);
            return current;
        });
    }

    return fullText;
  };

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = error => reject(error);
    });
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  };

  const onDragLeave = () => setDragActive(false);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const files = e.dataTransfer.files;
    if (files && files[0]) handleFileUpload(files[0]);
  };

  return (
    <div className="min-h-screen bg-dark-bg text-dark-text-primary font-sans selection:bg-dark-accent selection:text-white">
      {/* Grid Headers */}
      <header className="border-b border-dark-border p-5 flex justify-between items-center bg-dark-bg sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-dark-accent text-white flex items-center justify-center font-bold text-lg rounded shadow-sm">D</div>
          <div>
            <h1 className="text-xs font-bold uppercase tracking-widest leading-none text-dark-text-secondary">Docling Source Converter</h1>
            <p className="text-[9px] font-mono opacity-40 uppercase mt-1 tracking-tighter">v.1.0.2-local / SYSTEM_READY</p>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="hidden md:flex flex-col items-end">
            <span className="text-[9px] uppercase font-bold text-dark-text-secondary opacity-50">System Health</span>
            <span className="text-[10px] font-mono flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${health ? 'bg-dark-success' : 'bg-dark-error'} animate-pulse`} />
              {health ? "SERVICE_ACTIVE" : "OFFLINE"}
            </span>
          </div>
          <div className="text-right border-l border-dark-border pl-6 ml-2 h-8 flex flex-col justify-center">
            <span className="text-[9px] uppercase font-bold text-dark-text-secondary opacity-50">Vault Root</span>
            <span className="text-[10px] font-mono block text-dark-accent">/10.1 - Documentos/</span>
          </div>
        </div>
      </header>

      <main className="max-w-[640px] mx-auto p-6 md:py-16 pb-24 space-y-12">
        <div className="grid grid-cols-1 gap-12">
          
          {/* Source Acquisition Section */}
          <section className="space-y-4">
            <h2 className="text-[11px] font-bold uppercase tracking-[0.2em] text-dark-text-secondary flex items-center gap-3">
              Source Acquisition
            </h2>

            <div className="space-y-8">
              <form onSubmit={handleUrlConversion} className="space-y-4">
                <label className="text-[11px] font-bold uppercase block tracking-widest text-dark-text-secondary">Remote Source URL</label>
                <div className="flex gap-4">
                  <div className="relative flex-1">
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-dark-text-secondary opacity-40">
                      <LinkIcon className="w-4 h-4" />
                    </div>
                    <input 
                      type="url" 
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      placeholder="https://example.com/document" 
                      className="w-full bg-dark-surface border border-dark-border py-3 pl-11 pr-4 text-xs font-mono text-dark-text-primary rounded focus:border-dark-accent focus:outline-none transition-all"
                    />
                  </div>
                  <button 
                    disabled={isProcessing || !url}
                    className="bg-dark-text-primary text-dark-bg px-8 text-[11px] font-bold uppercase tracking-widest hover:opacity-90 disabled:opacity-20 disabled:cursor-not-allowed transition-all flex items-center gap-3 rounded active:translate-y-0.5"
                  >
                    {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Process</>}
                  </button>
                </div>
              </form>

              <div className="mt-8">
                <label className="text-[11px] font-bold uppercase block mb-3 tracking-widest text-dark-text-secondary">PDF Document Layer</label>
                <div 
                  onDragOver={onDragOver}
                  onDragLeave={onDragLeave}
                  onDrop={onDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`
                    border-2 border-dashed p-10 text-center cursor-pointer transition-all duration-300 rounded-lg group
                    ${dragActive ? 'bg-dark-accent/10 border-dark-accent' : 'bg-dark-surface/40 border-dark-border hover:bg-dark-surface/60 hover:border-dark-text-secondary'}
                  `}
                >
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    className="hidden" 
                    accept=".pdf"
                    onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                  />
                  <Upload className={`w-8 h-8 mx-auto mb-4 transition-transform duration-300 ${dragActive ? 'text-dark-accent' : 'text-dark-text-secondary group-hover:scale-110'}`} />
                  <p className="text-sm font-mono text-dark-text-secondary">Drag & drop PDF here or click to browse</p>
                  <p className="text-[10px] uppercase mt-3 text-dark-text-secondary opacity-40 tracking-widest">Single Document Buffer / 50MB MAX</p>
                </div>
              </div>
            </div>
          </section>

          {/* Pipeline Output Section */}
          <section className="pt-8 border-t border-dark-border space-y-4 min-h-[200px]">
            <h2 className="text-[11px] font-bold uppercase tracking-[0.2em] text-dark-text-secondary flex items-center gap-3">
              Output Pipeline
            </h2>

            <AnimatePresence mode="wait">
              {isProcessing && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="p-12 flex flex-col items-center justify-center bg-dark-surface/30 rounded border border-dark-border shadow-[0px_4px_24px_rgba(0,0,0,0.5)]"
                >
                  <div className="w-full max-w-[320px] space-y-8">
                    <div className="flex flex-col items-center gap-4">
                        <div className="relative">
                            <Loader2 className="w-8 h-8 animate-spin text-dark-accent" />
                        </div>
                        <p className="font-mono text-[10px] uppercase tracking-[0.3em] font-bold text-dark-accent">
                          Ingestão Ativa
                        </p>
                    </div>

                    <div className="space-y-3">
                        <div className="flex justify-between items-end text-[9px] font-mono uppercase tracking-widest text-dark-text-secondary">
                            <span>{statusMessage}</span>
                            <span>{Math.round(progress)}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-dark-bg border border-dark-border rounded-full overflow-hidden">
                            <motion.div 
                                initial={{ width: 0 }}
                                animate={{ width: `${progress}%` }}
                                transition={{ type: "tween", ease: "linear", duration: 0.1 }}
                                className="h-full bg-dark-accent shadow-[0_0_12px_rgba(74,144,226,0.6)]"
                            />
                        </div>
                    </div>
                    
                    <p className="text-[9px] text-dark-text-secondary uppercase mt-2 tracking-widest text-center opacity-40 leading-relaxed italic">
                      Por favor, aguarde. O Gemini está processando as camadas estruturais.
                    </p>
                  </div>
                </motion.div>
              )}

              {result && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`border ${result.success ? "border-dark-border" : "border-dark-error/30"} p-8 bg-dark-surface rounded-lg relative overflow-hidden`}
                >
                  {result.success && <div className="absolute top-0 left-0 w-1 h-full bg-dark-success opacity-50" />}
                  <div className="flex items-start gap-6">
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-center mb-6">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${result.success ? 'bg-dark-success' : 'bg-dark-error'}`} />
                          <h3 className={`font-mono text-[11px] font-bold uppercase tracking-widest ${result.success ? 'text-dark-success' : 'text-dark-error'}`}>
                            {result.success ? "READY_FOR_IMPORT" : "PIPELINE_ERROR"}
                          </h3>
                        </div>
                        {result.success && (
                          <div className="flex gap-4">
                            <span 
                                onClick={() => result.path && navigator.clipboard.writeText(result.path)}
                                className="text-[10px] text-dark-accent hover:text-white cursor-pointer underline underline-offset-4"
                            >
                                Copy Path
                            </span>
                            <span 
                                onClick={() => setResult(null)}
                                className="text-[10px] text-dark-text-secondary hover:text-white cursor-pointer"
                            >
                                New Ingest
                            </span>
                          </div>
                        )}
                      </div>
                      
                      {result.success ? (
                        <div className="space-y-4">
                            <div className="bg-dark-bg/50 border border-dark-border p-4 font-mono text-[12px] text-dark-success break-all rounded leading-relaxed">
                                {result.path}
                            </div>
                            <p className="text-[11px] text-dark-text-secondary opacity-60 flex items-center gap-2">
                                <CheckCircle2 className="w-3.5 h-3.5" /> High fidelity extraction complete.
                            </p>
                        </div>
                      ) : (
                        <div className="space-y-4">
                           <p className="font-mono text-xs text-dark-error bg-dark-error/5 p-4 border border-dark-error/10 rounded">{result.error}</p>
                           <button 
                             onClick={() => setResult(null)}
                             className="text-[10px] font-bold uppercase text-dark-text-secondary hover:text-white border-b border-dark-text-secondary/30"
                           >
                             Dismiss and retry extraction
                           </button>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}

              {!isProcessing && !result && (
                <div className="border border-dashed border-dark-border p-16 flex flex-col items-center justify-center opacity-30 rounded-lg">
                  <FileText className="w-8 h-8 mb-4 stroke-[1.5px]" />
                  <p className="text-xs font-mono uppercase tracking-[0.2em]">Awaiting payload input signal</p>
                </div>
              )}
            </AnimatePresence>
          </section>
        </div>
      </main>

      <footer className="fixed bottom-10 left-0 right-0 flex justify-center pointer-events-none">
        <div className="text-[11px] font-mono text-dark-text-secondary opacity-40 uppercase tracking-widest bg-dark-bg/80 px-4 py-2 rounded-full border border-dark-border backdrop-blur-sm">
           Running on Localhost • System: Obsidian Zettelkasten Framework
        </div>
      </footer>
    </div>
  );
}
