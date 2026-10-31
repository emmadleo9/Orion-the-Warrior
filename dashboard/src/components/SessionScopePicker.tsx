import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Session } from '../services/api';
import { sessionPickerStartsExpanded, sessionScopeRows } from '../utils/sessionScope';

interface SessionScopePickerProps {
  sessions: Session[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
}

export function SessionScopePicker({ sessions, selectedIds, onChange, disabled }: SessionScopePickerProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(() => sessionPickerStartsExpanded(selectedIds));
  // Live sessions plus any selected id that no longer resolves to one, so a deleted session's id
  // stays visible and can be unticked instead of riding along on every save.
  const rows = sessionScopeRows(sessions, selectedIds);

  const toggle = (id: string) => {
    onChange(selectedIds.includes(id) ? selectedIds.filter(current => current !== id) : [...selectedIds, id]);
  };

  const chooseSessions = () => setExpanded(true);
  const leaveForAll = () => {
    onChange([]);
    setExpanded(false);
  };

  return (
    <div className="session-scope-picker" role="group" aria-label={t('apiKeys.sessions.label')}>
      {expanded ? (
        <>
          <button
            type="button"
            className="session-scope-toggle"
            onClick={leaveForAll}
            disabled={disabled}
            aria-expanded="true"
          >
            {t('apiKeys.sessions.leaveAll')}
          </button>
          <p className="session-scope-hint">{t('apiKeys.sessions.hint')}</p>
          {/*
            An empty selection WIDENS the key to every session, which is the opposite of what
            unticking the last box looks like it does. The explicit button above says so; reaching
            the same state one checkbox at a time did not, so say it here the moment it is true.
          */}
          {rows.length > 0 && selectedIds.length === 0 && (
            <p className="session-scope-widened" role="status">
              {t('apiKeys.sessions.all')}
            </p>
          )}
          {rows.length === 0 ? (
            <p className="session-scope-empty">{t('apiKeys.sessions.empty')}</p>
          ) : (
            <ul className="session-scope-list">
              {rows.map(({ id, session }) => (
                <li key={id}>
                  <label className="session-scope-option">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(id)}
                      onChange={() => toggle(id)}
                      disabled={disabled}
                    />
                    <span className="session-scope-meta">
                      {/* No live session behind the id: show it raw rather than hide it, which is
                          the only way an operator can drop a deleted session from the allowlist. */}
                      <span className="session-scope-name">{session ? session.name : id}</span>
                      {session?.phone ? <span className="session-scope-phone">{session.phone}</span> : null}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <button
          type="button"
          className="session-scope-toggle"
          onClick={chooseSessions}
          disabled={disabled}
          aria-expanded="false"
        >
          {t('apiKeys.sessions.choose')}
        </button>
      )}
    </div>
  );
}
