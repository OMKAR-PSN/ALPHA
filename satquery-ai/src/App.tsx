// SatQuery AI — Root Application

import { useState } from 'react';
import NavBar from './components/layout/NavBar';
import HomePage from './pages/HomePage';
import AnalysisPage from './pages/AnalysisPage';
import SystemViewPage from './pages/SystemViewPage';

type Page = 'home' | 'analysis' | 'system';

export default function App() {
  const [page, setPage] = useState<Page>('home');
  const [demoScenario, setDemoScenario] = useState<string | null>(null);

  const handleStartDemo = (scenarioId: string) => {
    setDemoScenario(scenarioId);
    setPage('analysis');
  };

  const handleNavigate = (p: string) => {
    setPage(p as Page);
    if (p !== 'analysis') setDemoScenario(null);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <NavBar currentPage={page} onNavigate={handleNavigate} />

      <main className="flex-1">
        {page === 'home' && (
          <HomePage onNavigate={handleNavigate} onStartDemo={handleStartDemo} />
        )}
        {page === 'analysis' && (
          <AnalysisPage
            initialScenario={demoScenario}
            key={demoScenario ?? 'analysis'}
          />
        )}
        {page === 'system' && (
          <SystemViewPage />
        )}
      </main>
    </div>
  );
}
