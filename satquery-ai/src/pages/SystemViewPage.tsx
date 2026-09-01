// System Architecture View — interactive flow diagram

import { useState } from 'react';
import {
  User, Brain, GitFork, Wrench, Shield, MessageSquare,
  Eye, Map, Activity, Layers, Cloud, Search, ArrowDown, ChevronRight
} from 'lucide-react';

const TOOLS = [
  { icon: Eye, name: 'Scene Understanding', desc: 'Land-cover classification' },
  { icon: Map, name: 'Object Detection', desc: 'Feature localisation' },
  { icon: Activity, name: 'Change Detection', desc: 'Bi-temporal analysis' },
  { icon: Layers, name: 'SAR–Optical Fusion', desc: 'Cross-modal reasoning' },
  { icon: Cloud, name: 'Cloud Detection', desc: 'Contamination check' },
  { icon: Search, name: 'Cloud Reconstruction', desc: 'SAR-guided infilling' },
];

interface NodeProps {
  icon: React.ElementType;
  label: string;
  sublabel?: string;
  color: string;
  bg: string;
  border: string;
  active?: boolean;
  onClick?: () => void;
}

function FlowNode({ icon: Icon, label, sublabel, color, bg, border, active, onClick }: NodeProps) {
  return (
    <div
      onClick={onClick}
      className={`flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all cursor-pointer
        ${active ? 'shadow-panel-md scale-105' : 'hover:shadow-sm hover:scale-101'}
        ${border} ${bg}`}
    >
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${color === 'text-white' ? 'bg-white/20' : 'bg-white'}`}>
        <Icon size={16} className={color} />
      </div>
      <div>
        <p className={`text-sm font-semibold ${color}`}>{label}</p>
        {sublabel && <p className={`text-[11px] opacity-70 ${color}`}>{sublabel}</p>}
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex justify-center my-1">
      <ArrowDown size={18} className="text-gray-300" />
    </div>
  );
}

const DESCRIPTIONS: Record<string, string> = {
  user: 'The user asks a question in natural language. No model or tool selection required.',
  controller: 'The Central Controller interprets the query, identifies the task type, selects the appropriate strategy, and orchestrates the specialist toolkit.',
  strategy: 'The Solution Space maps task types to ordered tool workflows. Prevents arbitrary tool sequencing.',
  toolkit: 'Specialist tools perform the actual image analysis: classification, change detection, SAR fusion, cloud reconstruction, etc.',
  evidence: 'The Confidence Engine aggregates per-tool confidence scores and detects cross-tool disagreements.',
  answer: 'The Answer Synthesis tool generates a natural-language response grounded in tool outputs.',
};

export default function SystemViewPage() {
  const [active, setActive] = useState<string | null>('controller');

  const desc = active ? DESCRIPTIONS[active] : null;

  return (
    <div className="min-h-screen bg-rs-bg py-10 px-4">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <p className="section-label mb-1">Architecture</p>
          <h1 className="text-2xl font-bold text-rs-text-primary">System View</h1>
          <p className="text-rs-text-secondary text-sm mt-1">
            Click any node to learn about its role in the SatQuery AI agent pipeline.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Flow diagram */}
          <div className="lg:col-span-2 panel p-6">
            {/* USER */}
            <FlowNode
              icon={User} label="User" sublabel="Natural-language query"
              color="text-rs-text-primary" bg="bg-gray-50" border="border-gray-200"
              active={active === 'user'} onClick={() => setActive('user')}
            />
            <Arrow />

            {/* CENTRAL CONTROLLER */}
            <FlowNode
              icon={Brain} label="Central Controller"
              sublabel="Understand · Plan · Select · Orchestrate"
              color="text-white" bg="bg-rs-navy" border="border-navy-900"
              active={active === 'controller'} onClick={() => setActive('controller')}
            />
            <Arrow />

            {/* STRATEGY */}
            <FlowNode
              icon={GitFork} label="Task & Strategy Selection"
              sublabel="Solution Space — workflow registry"
              color="text-rs-teal" bg="bg-teal-50" border="border-teal-200"
              active={active === 'strategy'} onClick={() => setActive('strategy')}
            />
            <Arrow />

            {/* SPECIALIST TOOLKIT */}
            <div
              className={`rounded-xl border-2 transition-all cursor-pointer p-4
                ${active === 'toolkit' ? 'border-indigo-400 bg-indigo-50 shadow-md' : 'border-indigo-200 bg-indigo-50/50 hover:shadow-sm'}`}
              onClick={() => setActive('toolkit')}
            >
              <div className="flex items-center gap-2 mb-3">
                <Wrench size={16} className="text-indigo-600" />
                <span className="text-sm font-bold text-indigo-800">Specialist Toolkit</span>
                <span className="badge badge-navy ml-auto text-[10px]">10 tools</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {TOOLS.map(({ icon: Icon, name, desc }) => (
                  <div key={name} className="flex items-center gap-2 px-2 py-1.5 bg-white rounded-lg border border-indigo-100">
                    <Icon size={12} className="text-indigo-500 flex-shrink-0" />
                    <div>
                      <p className="text-[11px] font-semibold text-indigo-800">{name}</p>
                      <p className="text-[10px] text-indigo-500">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <Arrow />

            {/* EVIDENCE */}
            <FlowNode
              icon={Shield} label="Evidence & Confidence Check"
              sublabel="Cross-tool agreement · Re-analysis if needed"
              color="text-orange-700" bg="bg-orange-50" border="border-orange-200"
              active={active === 'evidence'} onClick={() => setActive('evidence')}
            />
            <Arrow />

            {/* ANSWER */}
            <FlowNode
              icon={MessageSquare} label="Answer Synthesis"
              sublabel="Grounded natural-language response"
              color="text-green-700" bg="bg-green-50" border="border-green-200"
              active={active === 'answer'} onClick={() => setActive('answer')}
            />
          </div>

          {/* Detail panel */}
          <div className="space-y-4">
            {/* Selected node info */}
            <div className="panel p-5 min-h-40">
              {desc ? (
                <div className="animate-fade-in">
                  <p className="section-label mb-3">Component Role</p>
                  <p className="text-sm text-rs-text-secondary leading-relaxed">{desc}</p>
                </div>
              ) : (
                <p className="text-sm text-rs-text-muted">Click a node to see its role.</p>
              )}
            </div>

            {/* Key distinction */}
            <div className="panel p-5 border-l-4 border-l-rs-teal">
              <p className="section-label mb-3">Key Distinction</p>
              <div className="space-y-3">
                <div>
                  <p className="text-xs font-bold text-rs-navy mb-1">LLM / Controller</p>
                  <div className="space-y-1">
                    {['Understand query', 'Plan workflow', 'Select tools', 'Orchestrate', 'Explain results'].map(s => (
                      <div key={s} className="flex items-center gap-1.5 text-xs text-rs-text-secondary">
                        <ChevronRight size={10} className="text-rs-teal" />{s}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-bold text-indigo-700 mb-1">Specialist Tools</p>
                  <div className="space-y-1">
                    {['Analyse images', 'Detect changes', 'Classify pixels', 'Fuse modalities', 'Reconstruct clouds'].map(s => (
                      <div key={s} className="flex items-center gap-1.5 text-xs text-rs-text-secondary">
                        <ChevronRight size={10} className="text-indigo-400" />{s}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Task routing */}
            <div className="panel p-5">
              <p className="section-label mb-3">Task → Strategy</p>
              <div className="space-y-2">
                {[
                  { task: 'Single Image', tools: 'Validation → Scene → Objects → Answer', color: 'bg-gray-100 text-gray-700' },
                  { task: 'Bi-Temporal', tools: 'Validation → Cloud → Change → Class → Evidence → Answer', color: 'bg-navy-100 text-navy-800' },
                  { task: 'SAR + Optical', tools: 'Validation → Scene → Fusion → Evidence → Answer', color: 'bg-teal-100 text-teal-800' },
                  { task: 'Cloud Analysis', tools: 'Validation → Cloud → Reconstruct → Scene → Answer', color: 'bg-orange-100 text-orange-800' },
                ].map(({ task, tools, color }) => (
                  <div key={task} className={`px-3 py-2 rounded-lg ${color}`}>
                    <p className="text-xs font-bold">{task}</p>
                    <p className="text-[10px] opacity-80 mt-0.5">{tools}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
