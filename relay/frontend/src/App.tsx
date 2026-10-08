import { BrowserRouter, Link, Route, Routes } from "react-router";
import { SessionProvider } from "./hooks/useSession";
import { ActivityPage } from "./pages/ActivityPage";
import { ChannelPage } from "./pages/ChannelPage";
import { HomePage } from "./pages/HomePage";

export function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/c/:channelId" element={<ChannelPage />} />
          <Route path="/c/:channelId/t/:threadId" element={<ChannelPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  );
}

function NotFoundPage() {
  return (
    <div className="centered-page">
      <h1>Page not found</h1>
      <Link to="/" className="button">
        Back to home
      </Link>
    </div>
  );
}
