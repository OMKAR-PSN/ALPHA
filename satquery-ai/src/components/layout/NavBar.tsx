// Layout — Top navigation bar

import { useState } from 'react';
import { Satellite, LayoutDashboard, FlaskConical, Network, ChevronRight } from 'lucide-react';

interface NavBarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
}

export default function NavBar({ currentPage, onNavigate }: NavBarProps) {
  return (
    <nav className="sticky top-0 z-50 bg-rs-navy border-b border-navy-800 shadow-lg">
      <div className="max-w-screen-2xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <button
          onClick={() => onNavigate('home')}
          className="flex items-center gap-2.5 group"
        >
          <div className="w-8 h-8 rounded-lg bg-rs-teal flex items-center justify-center shadow-md group-hover:bg-teal-500 transition-colors">
            <Satellite className="w-4.5 h-4.5 text-white" size={18} />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-white font-bold text-base tracking-tight">SatQuery AI</span>
            <span className="text-navy-300 text-[10px] font-medium tracking-widest uppercase">Remote Sensing Agent</span>
          </div>
        </button>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-1">
          {[
            { id: 'home', label: 'Home', icon: LayoutDashboard },
            { id: 'analysis', label: 'Analysis', icon: FlaskConical },
            { id: 'system', label: 'System View', icon: Network },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                currentPage === id
                  ? 'bg-white/10 text-white'
                  : 'text-navy-300 hover:text-white hover:bg-white/5'
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {/* Badge */}
        <div className="flex items-center gap-2">
          <span className="hidden sm:flex items-center gap-1 px-2.5 py-1 rounded-full bg-rs-orange/20 border border-rs-orange/30 text-rs-orange text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-rs-orange animate-pulse" />
            DEMO MODE
          </span>
        </div>
      </div>
    </nav>
  );
}
