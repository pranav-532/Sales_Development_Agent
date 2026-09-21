import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ControlProvider } from "@/context/ControlContext";
import { ConflictProvider } from "@/context/ConflictContext";
import { SettingsProvider } from "@/context/SettingsContext";
import Boot from "@/components/Boot";
import AppLayout from "@/layouts/AppLayout";
import Campaigns from "@/pages/Campaigns";
import CampaignDashboard from "@/pages/CampaignDashboard";
import CampaignForm from "@/pages/CampaignForm";
import PromptManager from "@/pages/PromptManager";
import Reps from "@/pages/Reps";
import Conflicts from "@/pages/Conflicts";
import Settings from "@/pages/Settings";

export default function App() {
  return (
    <ControlProvider>
      <Boot>
        <SettingsProvider>
          <ConflictProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<AppLayout />}>
                  <Route path="/" element={<Navigate to="/campaigns" replace />} />
                  <Route path="/campaigns" element={<Campaigns />} />
                  <Route path="/campaigns/new" element={<CampaignForm />} />
                  <Route path="/campaigns/:id/edit" element={<CampaignForm />} />
                  <Route path="/campaigns/:id" element={<CampaignDashboard />} />
                  <Route path="/prompts" element={<PromptManager />} />
                  <Route path="/reps" element={<Reps />} />
                  <Route path="/conflicts" element={<Conflicts />} />
                  <Route path="/settings" element={<Settings />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </ConflictProvider>
        </SettingsProvider>
      </Boot>
    </ControlProvider>
  );
}