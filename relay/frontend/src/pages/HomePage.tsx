import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { api } from "../api/client";
import { APP_NAME, Logo } from "../components/Logo";
import { useSession } from "../hooks/useSession";

/** The landing page. Returning visitors with channels go straight to their first channel. */
export function HomePage() {
  const { ready, user, channels, ensureUser, refreshChannels } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const firstChannel = channels.owned[0] ?? channels.shared[0];
  if (!ready) return null;
  if (firstChannel) return <Navigate to={`/c/${firstChannel.id}`} replace />;

  const createFirstChannel = async (event: FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setErrorMessage("");
    try {
      await ensureUser(name);
      const channel = await api.createChannel(`Channel ${channels.owned.length + 1}`);
      await refreshChannels();
      navigate(`/c/${channel.id}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not create a channel.");
      setCreating(false);
    }
  };

  return (
    <div className="home">
      <header className="home__header">
        <span className="brand">
          <Logo />
          {APP_NAME}
        </span>
      </header>
      <main className="home__main">
        <h1 className="home__title">A chat room where your team and its AI agents work together.</h1>
        <p className="muted">Share a link with your agents and they join the conversation.</p>
        <form className="home__form" onSubmit={createFirstChannel}>
          {!user && (
            <input
              className="input"
              placeholder="What should we call you?"
              value={name}
              maxLength={40}
              onChange={(event) => setName(event.target.value)}
              autoFocus
            />
          )}
          <button
            type="submit"
            className="button button--primary button--large"
            disabled={creating || (!user && !name.trim())}
          >
            Create a channel
          </button>
          {errorMessage && (
            <p className="form-error" role="alert">
              {errorMessage}
            </p>
          )}
        </form>
        <p className="muted home__note">No sign-up. Everything stays on this server.</p>
      </main>
    </div>
  );
}
