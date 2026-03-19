import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link, useSearchParams } from 'react-router-dom';

import '../App.css';

const API_BASE = '/api';

function SheetsMessageBubble({ message, isUser }) {
  const mode = message.mode || 'sheets';
  return (
    <div className={`message ${isUser ? 'message-user' : 'message-assistant'} message-mode-${mode}`}>
      <div className="message-avatar">
        {isUser ? <span className="avatar-icon">U</span> : <span className="avatar-icon assistant">S</span>}
      </div>
      <div className="message-content">
        {!isUser && <div className={`message-mode-label message-mode-label-${mode}`}>{mode === 'sheets' ? 'Sheets' : 'Assistant'}</div>}
        <div className="message-text">
          <ReactMarkdown>{message.content || ''}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

export default function SheetsChatPage() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [selectedSheet, setSelectedSheet] = useState(null);
  const [driveFiles, setDriveFiles] = useState([]);
  const [driveFilesLoading, setDriveFilesLoading] = useState(false);
  const [chatSessions, setChatSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionMenuOpen, setSessionMenuOpen] = useState(null);
  const [deletingSessionId, setDeletingSessionId] = useState(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [searchParams, setSearchParams] = useSearchParams();
  const inputRef = useRef(null);
  const sessionMenuRef = useRef(null);

  const spreadsheetId = selectedSheet?.id ?? '';

  const sendEnabled = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading]);

  const fetchDriveFiles = async () => {
    setDriveFilesLoading(true);
    try {
      const res = await fetch(`${API_BASE}/drive/files?page_size=50`);
      const data = await res.json();
      if (res.ok && data.files) {
        setDriveFiles(data.files.filter((f) => (f.mimeType || '').includes('spreadsheet')));
      }
    } catch (err) {
      console.error('Failed to fetch drive files:', err);
    } finally {
      setDriveFilesLoading(false);
    }
  };

  const selectSheet = (file) => {
    const isSheet = (file.mimeType || '').includes('spreadsheet');
    if (!isSheet) return;
    setSelectedSheet({ id: file.id, name: file.name, mimeType: file.mimeType || '' });
    setSearchParams({ fileId: file.id, fileName: file.name, mimeType: file.mimeType || '' }, { replace: true });
  };

  const clearSheet = () => {
    setSelectedSheet(null);
    setSearchParams({}, { replace: true });
  };

  const fetchChatSessions = async () => {
    setSessionsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat/sessions?mode=sheets`);
      const data = await res.json();
      if (res.ok && data.sessions) {
        setChatSessions(data.sessions);
      }
    } catch (err) {
      console.error('Failed to fetch chat sessions:', err);
    } finally {
      setSessionsLoading(false);
    }
  };

  const loadSession = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${id}`);
      const data = await res.json();
      if (res.ok && data.messages) {
        setSessionId(data.id);
        setMessages(
          data.messages.map((m) => ({
            role: m.role,
            content: m.content,
            mode: m.mode || 'sheets',
          }))
        );
      }
    } catch (err) {
      console.error('Failed to load session:', err);
    }
  };

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setSessionMenuOpen(null);
    fetchChatSessions();
  };

  const handleDeleteSession = async (sessionIdToDelete, e) => {
    e?.stopPropagation?.();
    if (deletingSessionId || !sessionIdToDelete) return;
    setDeletingSessionId(sessionIdToDelete);
    setSessionMenuOpen(null);
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionIdToDelete}`, { method: 'DELETE' });
      if (res.ok) {
        fetchChatSessions();
        if (sessionId === sessionIdToDelete) {
          setSessionId(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    } finally {
      setDeletingSessionId(null);
    }
  };

  useEffect(() => {
    fetchDriveFiles();
    fetchChatSessions();
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (e.target?.closest?.('.chat-history-dots')) return;
      if (sessionMenuRef.current && !sessionMenuRef.current.contains(e.target)) {
        setSessionMenuOpen(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const fileId = searchParams.get('fileId');
    const fileName = searchParams.get('fileName');
    const mimeType = searchParams.get('mimeType') || '';
    if (fileId && fileName) {
      setSelectedSheet({ id: fileId, name: decodeURIComponent(fileName), mimeType });
    }
  }, [searchParams]);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      const el = document.querySelector('.chat-scroll');
      if (el) el.scrollTop = el.scrollHeight;
    });
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const nextMessages = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/sheets-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: nextMessages.map((m) => ({ role: m.role, content: m.content })),
          sessionId,
          spreadsheetId: spreadsheetId.trim() || null,
        }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || data.error || 'Sheets request failed');

      if (data.sessionId) {
        setSessionId(data.sessionId);
        fetchChatSessions();
      }

      const assistantContent = data.message?.content || 'No response.';
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: assistantContent,
          mode: 'sheets',
          toolCalls: data.toolCalls || [],
        },
      ]);
      scrollToBottom();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}`,
          mode: 'sheets',
        },
      ]);
      scrollToBottom();
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="app assistant-page chatgpt-layout sheets-chat-page">
      <div className="chat-layout">
        <aside className="chat-sidebar">
          <Link to="/" className="chat-sidebar-logo" title="Home">
            <span className="logo-icon">G</span>
          </Link>

          <div className="chat-sidebar-header">
            <h3>Chat history</h3>
          </div>
          <div className="chat-history-section">
            <button type="button" className="chat-sidebar-change-btn" onClick={startNewChat}>
              New chat
            </button>
            {sessionsLoading ? (
              <p className="chat-sidebar-empty">Loading…</p>
            ) : chatSessions.length > 0 ? (
              <ul className="chat-history-list">
                {chatSessions.map((s) => {
                  const fullTitle = s.title || 'New chat';
                  const shortTitle = fullTitle.length > 24 ? fullTitle.slice(0, 24) : fullTitle;
                  const isMenuOpen = sessionMenuOpen === s.id;
                  const isDeleting = deletingSessionId === s.id;
                  return (
                    <li key={s.id} className="chat-history-item">
                      <div
                        role="button"
                        tabIndex={0}
                        className={`chat-sidebar-file-item chat-history-card ${sessionId === s.id ? 'selected' : ''}`}
                        onClick={() => { setSessionMenuOpen(null); loadSession(s.id); }}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSessionMenuOpen(null); loadSession(s.id); } }}
                        title={fullTitle}
                      >
                        <span className="chat-history-title">{shortTitle}</span>
                        <button
                          type="button"
                          className="chat-history-dots"
                          onClick={(e) => { e.stopPropagation(); setSessionMenuOpen(isMenuOpen ? null : s.id); }}
                          aria-label="Options"
                        >
                          ⋯
                        </button>
                      </div>
                      {isMenuOpen && (
                        <div className="chat-history-menu" ref={sessionMenuRef}>
                          <button
                            type="button"
                            className="chat-history-menu-delete"
                            onClick={(e) => handleDeleteSession(s.id, e)}
                            disabled={isDeleting}
                          >
                            {isDeleting ? 'Deleting…' : 'Delete'}
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="chat-sidebar-empty">No chats yet</p>
            )}
          </div>

          <div className="chat-sidebar-header chat-sidebar-divider" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
            <h3>Files</h3>
            <button
              type="button"
              className="chat-sidebar-change-btn"
              onClick={fetchDriveFiles}
              disabled={driveFilesLoading}
              title="Refresh file list"
              aria-label="Refresh file list"
              style={{ width: 'auto', padding: '0.25rem 0.5rem', flexShrink: 0 }}
            >
              {driveFilesLoading ? '…' : '↻'}
            </button>
          </div>
          <div className="chat-sidebar-file">
            {selectedSheet && (
              <div className="chat-sidebar-file-info" style={{ marginBottom: '0.5rem' }}>
                <span className="chat-sidebar-file-name" title={selectedSheet.name} style={{ display: 'block', fontSize: '0.85rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {selectedSheet.name}
                </span>
                <a
                  href={`https://docs.google.com/spreadsheets/d/${selectedSheet.id}/edit`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="chat-sidebar-open-link"
                  style={{ fontSize: '0.8rem', marginTop: 4, display: 'inline-block' }}
                >
                  Open in Sheets
                </a>
                <button
                  type="button"
                  className="chat-sidebar-clear-btn"
                  onClick={clearSheet}
                  style={{ marginTop: 6, display: 'block' }}
                >
                  Clear
                </button>
              </div>
            )}
            {driveFiles.length > 0 ? (
              <ul className="chat-sidebar-file-list">
                {driveFiles.map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      className={`chat-sidebar-file-item ${selectedSheet?.id === f.id ? 'selected' : ''}`}
                      onClick={() => selectSheet(f)}
                    >
                      {f.name}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="chat-sidebar-empty">
                {driveFilesLoading ? 'Loading…' : 'No spreadsheets'}
              </p>
            )}
          </div>

          <div style={{ marginTop: 'auto' }} />
        </aside>

        <main className="chat-container">
          <div className="chat-scroll">
            {messages.length === 0 ? (
              <div className="welcome">
                <div className="welcome-card">
                  <h2>{selectedSheet ? `Working on "${selectedSheet.name}"` : 'Sheets data injection'}</h2>
                  <p>
                    {selectedSheet
                      ? 'Describe what you want to write into this spreadsheet (ranges, tables, formatting).'
                      : 'Select a spreadsheet from the sidebar, or leave unselected to let the agent create/request one. Populate with financial model inputs, tables, and basic formatting.'}
                  </p>
                  <ul className="suggestions">
                    <li onClick={() => setInput('Create a simple model template with a header row for Revenue, Cost, and Profit for Q1-Q4.')}>
                      Create a simple model template
                    </li>
                    <li
                      onClick={() =>
                        setInput(
                          'Write these values into the sheet: Revenue [100,120,140,160], Cost [80,90,100,110], Profit [20,30,40,50] for Q1-Q4. Use a clean header row.'
                        )
                      }
                    >
                      Write financial values into a table
                    </li>
                    <li onClick={() => setInput('Add formatting: bold header row and auto-resize columns for the table range.')}>
                      Add minimal table formatting
                    </li>
                  </ul>
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <SheetsMessageBubble key={i} message={msg} isUser={msg.role === 'user'} />
              ))
            )}
          </div>

          <div className="input-inbox">
            <div className="input-inner">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={selectedSheet ? `Describe what to write into "${selectedSheet.name}"...` : 'Select a spreadsheet from the sidebar, or describe what you want to create...'}
                rows={1}
                disabled={isLoading}
                className="chat-textarea"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
              />
            </div>
            <div className="input-footer">
              <div className="input-footer-left">
                <button type="button" className="send-btn" disabled={!sendEnabled} onClick={sendMessage} aria-label="Send">
                  {isLoading ? 'Sending…' : 'Send'}
                </button>
              </div>
              <div className="input-footer-right" style={{ color: 'var(--text-secondary)', fontSize: '0.78rem' }}>
                Tools are executed server-side via `gws` Sheets API.
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

