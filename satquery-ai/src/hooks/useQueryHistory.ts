// useQueryHistory.ts — localStorage-backed query history hook

import { useState, useCallback } from 'react';

export interface HistoryEntry {
  id: string;
  query: string;
  scenarioId: string | null;
  confidence: number;
  confidenceLevel: string;
  finalAnswer: string;
  timestamp: number;
  aoiName?: string;
}

const KEY = 'satquery_history';
const MAX = 10;

function load(): HistoryEntry[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  } catch {
    return [];
  }
}

function save(entries: HistoryEntry[]) {
  localStorage.setItem(KEY, JSON.stringify(entries.slice(0, MAX)));
}

export function useQueryHistory() {
  const [history, setHistory] = useState<HistoryEntry[]>(load);

  const addEntry = useCallback((entry: Omit<HistoryEntry, 'id' | 'timestamp'>) => {
    const newEntry: HistoryEntry = {
      ...entry,
      id: crypto.randomUUID(),
      timestamp: Date.now(),
    };
    setHistory(prev => {
      const next = [newEntry, ...prev].slice(0, MAX);
      save(next);
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    localStorage.removeItem(KEY);
    setHistory([]);
  }, []);

  return { history, addEntry, clearHistory };
}
