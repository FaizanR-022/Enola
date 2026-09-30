import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useOwner } from "./lib/auth";
import { queryClient } from "./lib/query";
import { Approvals } from "./screens/Approvals";
import { Chat } from "./screens/Chat";
import { Dashboard } from "./screens/Dashboard";
import { Finance } from "./screens/Finance";
import { Learning } from "./screens/Learning";
import { Projects } from "./screens/Projects";
import { JobDetail } from "./screens/JobDetail";
import { Jobs } from "./screens/Jobs";
import { Log } from "./screens/Log";
import { Login } from "./screens/Login";
import { Memory } from "./screens/Memory";
import { People } from "./screens/People";
import { Person } from "./screens/Person";
import { Academics } from "./screens/Academics";
import { Email } from "./screens/Email";
import { Tasks } from "./screens/Tasks";
import { Shell } from "./shell/Shell";
import { ThemeProvider } from "./theme/theme";
import { ErrorState } from "./ui";

function Gate() {
  const owner = useOwner();
  if (owner.isPending) return null; // the splash covers this once the shell mounts
  if (owner.isError) return <ErrorState error={owner.error} onRetry={() => void owner.refetch()} />;
  if (owner.data === null) return <Login />;
  return <Shell />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Gate />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/approvals" element={<Approvals />} />
              <Route path="/tasks" element={<Tasks />} />
              <Route path="/log" element={<Log />} />
              <Route path="/email" element={<Email />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/jobs" element={<Jobs />} />
              <Route path="/jobs/:id" element={<JobDetail />} />
              <Route path="/people" element={<People />} />
              <Route path="/people/:id" element={<Person />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/learning" element={<Learning />} />
              <Route path="/academics" element={<Academics />} />
              <Route path="/finance" element={<Finance />} />
              <Route path="/memory" element={<Memory />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
