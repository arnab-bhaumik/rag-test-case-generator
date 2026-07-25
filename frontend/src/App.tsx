import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Generate } from './pages/Generate';
import { TestCaseLibrary } from './pages/TestCaseLibrary';
import { Review } from './pages/Review';
import { CoverageMatrix } from './pages/CoverageMatrix';
import { Export } from './pages/Export';
import { RunHistory } from './pages/RunHistory';
import { Settings } from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        <Sidebar />
        <Routes>
          <Route path="/" element={<Generate />} />
          <Route path="/library" element={<TestCaseLibrary />} />
          <Route path="/review" element={<Review />} />
          <Route path="/review/:runId" element={<Review />} />
          <Route path="/coverage" element={<CoverageMatrix />} />
          <Route path="/coverage/:runId" element={<CoverageMatrix />} />
          <Route path="/export" element={<Export />} />
          <Route path="/export/:runId" element={<Export />} />
          <Route path="/history" element={<RunHistory />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
