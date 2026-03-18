import React, { useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';

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
  const [spreadsheetId, setSpreadsheetId] = useState('');
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const inputRef = useRef(null);

  const sendEnabled = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading]);

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

      if (data.sessionId) setSessionId(data.sessionId);

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
    <div className="app assistant-page chatgpt-layout">
      <div className="chat-layout">
        <aside className="chat-sidebar">
          <Link to="/" className="chat-sidebar-logo" title="Home">
            <span className="logo-icon">G</span>
          </Link>

          <div className="chat-sidebar-divider">
            <h3>Sheets</h3>
          </div>

          <div className="chat-sidebar-file">
            <div style={{ padding: '0.25rem 0.15rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                SpreadsheetId (optional)
              </label>
              <input
                value={spreadsheetId}
                onChange={(e) => setSpreadsheetId(e.target.value)}
                placeholder="e.g. 1AbC...xYz"
                style={{
                  width: '100%',
                  padding: '0.5rem 0.6rem',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-primary)',
                }}
              />
              <div style={{ marginTop: 10, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Leave blank to let the agent request/create.
              </div>
            </div>
          </div>

          <div style={{ marginTop: 'auto' }} />
        </aside>

        <main className="chat-container">
          <div className="chat-scroll">
            {messages.length === 0 ? (
              <div className="welcome">
                <div className="welcome-card">
                  <h2>Sheets data injection</h2>
                  <p>Populate a Google Sheet with financial model inputs, tables, and basic formatting.</p>
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
                placeholder="Describe what you want to write into the sheet (ranges, tables, formatting)..."
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

