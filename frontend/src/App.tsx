import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { ArtifactsPage } from './pages/ArtifactsPage'
import { ArtifactViewPage } from './pages/ArtifactViewPage'
import { OverviewPage } from './pages/OverviewPage'
import { PipelinesPage } from './pages/PipelinesPage'
import { ProjectIntelligencePage } from './pages/ProjectIntelligencePage'
import { RunDetailPage } from './pages/RunDetailPage'
import { RunsPage } from './pages/RunsPage'
import { SettingsPage } from './pages/SettingsPage'
import { SkillsPage } from './pages/SkillsPage'

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="runs/:runId" element={<RunDetailPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="pipelines" element={<PipelinesPage />} />
        <Route path="artifacts" element={<ArtifactsPage />} />
        <Route path="artifacts/*" element={<ArtifactViewPage />} />
        <Route path="project-intelligence" element={<ProjectIntelligencePage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
