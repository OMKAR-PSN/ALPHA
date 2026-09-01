// Home Page — Hero, demo scenarios, supported analysis list

import { useState, useEffect } from 'react';
import {
  Satellite, Zap, Map, Layers, Cloud, Eye, Activity,
  ArrowRight, Play, ChevronRight, Globe, BarChart3, Shield
} from 'lucide-react';
import type { DemoScenario } from '../types';
import { fetchDemoScenarios } from '../api/client';
import SatImageCarousel from '../components/hero/SatImageCarousel';

interface HomePageProps {
  onNavigate: (page: string) => void;
  onStartDemo: (scenarioId: string) => void;
}

const CAPABILITIES = [
  {
    icon: Eye,
    title: 'Scene Understanding',
    desc: 'Identify land-cover types, dominant features, and scene composition from a single image.',
    color: 'text-rs-teal',
    bg: 'bg-teal-50',
  },
  {
    icon: Map,
    title: 'Object & Region Detection',
    desc: 'Localise specific features — buildings, water bodies, roads — with spatial precision.',
    color: 'text-rs-navy',
    bg: 'bg-blue-50',
  },
  {
    icon: Activity,
    title: 'Bi-Temporal Change',
    desc: 'Detect and quantify land-cover changes between two dates with statistical confidence.',
    color: 'text-indigo-600',
    bg: 'bg-indigo-50',
  },
  {
    icon: Layers,
    title: 'Optical + SAR Fusion',
    desc: 'Cross-modal reasoning combining optical richness with all-weather SAR capability.',
    color: 'text-purple-600',
    bg: 'bg-purple-50',
  },
  {
    icon: Cloud,
    title: 'Cloud-Aware Analysis',
    desc: 'Automatic cloud detection and SAR-guided reconstruction — triggered without user intervention.',
    color: 'text-rs-orange',
    bg: 'bg-orange-50',
  },
  {
    icon: Shield,
    title: 'Confidence-Aware Results',
    desc: 'Every result carries a confidence score. Cross-tool disagreements are detected and flagged.',
    color: 'text-green-700',
    bg: 'bg-green-50',
  },
];

const TASK_TYPE_COLORS: Record<string, string> = {
  bi_temporal_change: 'badge-navy',
  sar_optical: 'badge-teal',
  cloud_analysis: 'badge-orange',
  single_image: 'badge-gray',
};

const TASK_TYPE_LABELS: Record<string, string> = {
  bi_temporal_change: 'Bi-Temporal',
  sar_optical: 'SAR + Optical',
  cloud_analysis: 'Cloud Analysis',
  single_image: 'Single Image',
};

const DEMO_ICONS: Record<string, typeof Activity> = {
  demo1: Activity,
  demo2: Layers,
  demo3: Cloud,
};

export default function HomePage({ onNavigate, onStartDemo }: HomePageProps) {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDemoScenarios()
      .then(setScenarios)
      .catch(() => setScenarios([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-rs-bg">

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-rs-navy">
        {/* Grid background */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px',
          }}
        />
        {/* Accent glows */}
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-rs-teal opacity-5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-indigo-600 opacity-5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/4" />

        <div className="relative max-w-screen-xl mx-auto px-6 py-16 md:py-24">
          {/* Two-column layout: text left, carousel right */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">

            {/* ── LEFT: Text ── */}
            <div>
              {/* Tag */}
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 border border-white/15 text-white/80 text-xs font-medium mb-6">
                <Globe size={12} />
                <span>Vision-Language Agent for Multimodal Remote Sensing</span>
              </div>

              <h1 className="text-4xl md:text-5xl font-extrabold text-white leading-tight mb-5 tracking-tight">
                Ask questions about{' '}
                <span className="text-rs-teal" style={{textShadow: '0 0 30px rgba(26,107,107,0.5)'}}>
                  satellite imagery.
                </span>
                <br />
                Let the agent decide how to answer.
              </h1>

              <p className="text-navy-200 text-base leading-relaxed mb-8">
                SatQuery AI interprets your natural-language query, selects the appropriate
                specialist remote-sensing tools, executes them in the correct order, and
                returns a confidence-grounded answer — all without you needing to choose a model.
              </p>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => onNavigate('analysis')}
                  className="btn-secondary text-base px-6 py-3"
                >
                  <Zap size={18} />
                  Start Analysis
                </button>
                <button
                  onClick={() => scenarios[0] && onStartDemo(scenarios[0].scenario_id)}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white/10 border border-white/20 text-white font-semibold text-base hover:bg-white/15 transition-all"
                >
                  <Play size={18} />
                  Try Demo
                </button>
              </div>

              {/* Architecture pipeline */}
              <div className="mt-10 flex flex-wrap items-center gap-2 text-xs text-navy-300 font-mono">
                {['User Query', 'Controller', 'Tool Selection', 'Evidence', 'Answer'].map((s, i) => (
                  <span key={i} className="flex items-center gap-2">
                    <span className="px-2 py-1 rounded bg-white/8 border border-white/10 text-white/70">{s}</span>
                    {i < 4 && <ArrowRight size={11} className="text-navy-500" />}
                  </span>
                ))}
              </div>
            </div>

            {/* ── RIGHT: 3D Carousel ── */}
            <div className="hidden lg:flex items-center justify-center py-8">
              <div className="relative">
                {/* Floating label above */}
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 flex items-center gap-2 text-white/50 text-xs font-mono whitespace-nowrap">
                  <span className="w-1.5 h-1.5 rounded-full bg-rs-teal animate-pulse" />
                  Live Satellite Imagery Samples
                </div>
                <SatImageCarousel />
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── Demo Scenarios ────────────────────────────────────────────────── */}
      <section className="max-w-screen-xl mx-auto px-6 py-14">
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="section-label mb-1">Preloaded Demonstrations</p>
            <h2 className="text-2xl font-bold text-rs-text-primary">Run a Demo Instantly</h2>
          </div>
          <button
            onClick={() => onNavigate('analysis')}
            className="btn-ghost text-sm"
          >
            Custom Analysis <ArrowRight size={14} />
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[0, 1, 2].map(i => (
              <div key={i} className="panel h-52 shimmer" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {scenarios.map((s, idx) => {
              const Icon = DEMO_ICONS[s.scenario_id] || Activity;
              const isMain = idx === 0;
              return (
                <div
                  key={s.scenario_id}
                  className={`panel relative overflow-hidden group cursor-pointer hover:shadow-panel-md transition-all duration-200 ${
                    isMain ? 'ring-2 ring-rs-teal ring-offset-2' : ''
                  }`}
                  onClick={() => onStartDemo(s.scenario_id)}
                >
                  {isMain && (
                    <div className="absolute top-3 right-3">
                      <span className="badge badge-teal text-xs">Featured Demo</span>
                    </div>
                  )}
                  <div className="p-5">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${
                      idx === 0 ? 'bg-navy-100' : idx === 1 ? 'bg-teal-50' : 'bg-orange-50'
                    }`}>
                      <Icon size={20} className={idx === 0 ? 'text-rs-navy' : idx === 1 ? 'text-rs-teal' : 'text-rs-orange'} />
                    </div>

                    <div className={`badge ${TASK_TYPE_COLORS[s.task_type]} mb-3`}>
                      {TASK_TYPE_LABELS[s.task_type]}
                    </div>

                    <h3 className="font-semibold text-rs-text-primary mb-1">{s.title}</h3>
                    <p className="text-sm text-rs-text-secondary mb-4">{s.description}</p>

                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 mb-4">
                      <p className="text-xs text-rs-text-muted mb-1">Example query</p>
                      <p className="text-sm text-rs-text-primary italic">"{s.default_query}"</p>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mb-4">
                      {s.tags.map(tag => (
                        <span key={tag} className={`badge ${tag === 'REAL SATELLITE' ? 'badge-teal font-bold' : tag === 'EXPERIMENTAL' ? 'bg-orange-100 text-orange-800' : 'badge-gray'}`}>{tag}</span>
                      ))}
                    </div>

                    <button className="w-full btn-primary justify-center text-sm py-2 group-hover:bg-navy-800">
                      <Play size={14} /> Run Demo
                    </button>
                  </div>

                  {/* Image count indicator */}
                  <div className="border-t border-rs-border px-5 py-2 flex items-center gap-4 bg-gray-50">
                    <span className="text-xs text-rs-text-muted">
                      {s.images.length} image{s.images.length > 1 ? 's' : ''} ·{' '}
                      {s.images.map(i => i.sensor).filter((v, i, a) => a.indexOf(v) === i).join(' + ')}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ── Capabilities Grid ─────────────────────────────────────────────── */}
      <section className="bg-white border-y border-rs-border">
        <div className="max-w-screen-xl mx-auto px-6 py-14">
          <div className="text-center mb-10">
            <p className="section-label mb-2">Supported Analysis</p>
            <h2 className="text-2xl font-bold text-rs-text-primary">What the Agent Can Do</h2>
            <p className="text-rs-text-secondary mt-2 max-w-xl mx-auto text-sm">
              The controller selects from these capabilities automatically based on your query.
              You never need to specify which tool to run.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {CAPABILITIES.map(({ icon: Icon, title, desc, color, bg }) => (
              <div key={title} className="flex gap-4 p-5 rounded-xl border border-rs-border bg-white hover:shadow-panel-md transition-all group">
                <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
                  <Icon size={20} className={color} />
                </div>
                <div>
                  <h3 className="font-semibold text-rs-text-primary text-sm mb-1">{title}</h3>
                  <p className="text-xs text-rs-text-secondary leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Principle CTA ─────────────────────────────────────────────────── */}
      <section className="max-w-screen-xl mx-auto px-6 py-14">
        <div className="bg-rs-navy rounded-2xl p-8 md:p-12 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-full opacity-5"
            style={{
              backgroundImage: 'radial-gradient(circle at 20% 50%, #1A6B6B 0%, transparent 50%), radial-gradient(circle at 80% 50%, #E07B39 0%, transparent 50%)'
            }}
          />
          <div className="relative">
            <p className="text-rs-teal font-semibold text-sm mb-2 uppercase tracking-widest">Core Principle</p>
            <h2 className="text-2xl font-bold text-white mb-3">
              The user asks.<br />The agent decides.
            </h2>
            <p className="text-navy-300 max-w-xl text-sm leading-relaxed">
              SatQuery AI does not make the user choose a model, preprocessing step, or tool.
              Ask in natural language. The central controller interprets your intent,
              selects specialist tools, chains them, checks confidence, and delivers a grounded answer.
            </p>
          </div>
          <button
            onClick={() => onNavigate('analysis')}
            className="relative btn-orange whitespace-nowrap px-8 py-3 text-base"
          >
            Start Analysis <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-rs-border py-6">
        <div className="max-w-screen-xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Satellite size={14} className="text-rs-teal" />
            <span className="text-xs text-rs-text-muted font-medium">SatQuery AI — Prototype v1.0</span>
          </div>
          <p className="text-xs text-rs-text-muted max-w-lg">
            Demo scenarios run live algorithms on REAL satellite imagery. Note: SAR optical fusion is currently unavailable.
          </p>
        </div>
      </footer>
    </div>
  );
}
