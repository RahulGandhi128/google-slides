import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import './FinancialSlidesPage.css';

const API_BASE = '/api';

const PRESENTATION_TYPES = [
  {
    id: 'quarterly',
    icon: '📊',
    label: 'Quarterly report',
    description: 'Results, KPIs, and outlook',
  },
  {
    id: 'earnings',
    icon: '📈',
    label: 'Earnings & investor',
    description: 'Narrative for stakeholders',
  },
  {
    id: 'budget',
    icon: '💰',
    label: 'Budget & forecast',
    description: 'Plans, variances, scenarios',
  },
  {
    id: 'risk',
    icon: '⚖️',
    label: 'Risk & compliance',
    description: 'Controls and disclosures',
  },
  {
    id: 'board',
    icon: '📋',
    label: 'Board / executive',
    description: 'Concise executive summary',
  },
  {
    id: 'custom',
    icon: '✨',
    label: 'Custom brief',
    description: 'Describe your own format',
  },
];

export default function FinancialSlidesPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedType, setSelectedType] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    const ta = inputRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  const handleSelectType = (t) => {
    setSelectedType(t.id);
    const hint =
      t.id === 'custom'
        ? 'Describe the financial presentation you need (audience, length, tone).'
        : `Help me outline a ${t.label.toLowerCase()} presentation for Google Slides. Suggest slide titles and key bullets.`;
    setInput((prev) => (prev.trim() ? prev : hint));
    inputRef.current?.focus();
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const chatMessages = [...messages, userMessage].map((m) => ({
        role: m.role,
        content: typeof m.content === 'string' ? m.content : '',
      }));

      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: chatMessages,
          sessionId,
          documentId: null,
          documentFilename: null,
          currentFile: null,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || data.detail || 'Request failed');
      }

      if (data.sessionId) setSessionId(data.sessionId);

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.message?.content || 'No response.',
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `**Error:** ${err.message}. Ensure the backend is running.`,
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="financial-slides">
      <header className="fs-topbar">
        <Link to="/" className="fs-back" title="Back to home">
          ← Home
        </Link>
        <span className="fs-brand">Financial Slides</span>
        <span style={{ width: 72 }} aria-hidden />
      </header>

      <main className="fs-main">
        <section className="fs-welcome" aria-labelledby="fs-welcome-heading">
          <h1 id="fs-welcome-heading">Choose which type of presentation to make</h1>
          <p className="fs-subtitle">
            Pick a template to pre-fill your prompt, then chat to refine the outline. Your assistant uses the same
            Slides agent as the main workspace.
          </p>
          <div className="fs-type-grid" role="list">
            {PRESENTATION_TYPES.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`fs-type-card${selectedType === t.id ? ' selected' : ''}`}
                onClick={() => handleSelectType(t)}
                role="listitem"
              >
                <span className="fs-type-icon" aria-hidden>
                  {t.icon}
                </span>
                <span className="fs-type-label">{t.label}</span>
                <span className="fs-type-desc">{t.description}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="fs-chat-panel" aria-label="Chat">
          <div className="fs-chat-header">Conversation</div>
          <div className="fs-messages">
            {messages.length === 0 && !loading && (
              <p className="fs-empty-hint">
                Messages appear here. Select a presentation type above or type your request in the box below.
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`fs-msg ${m.role === 'user' ? 'fs-msg-user' : 'fs-msg-assistant'}`}
              >
                <div className="fs-msg-avatar" aria-hidden title={m.role === 'user' ? 'You' : 'Assistant'}>
                  {m.role === 'user' ? 'Y' : 'A'}
                </div>
                <div className="fs-msg-body">
                  {m.role === 'assistant' ? (
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="fs-msg fs-msg-assistant">
                <div className="fs-msg-avatar" aria-hidden>
                  A
                </div>
                <div className="fs-msg-body">
                  <span className="fs-loading">
                    <span className="fs-spinner" />
                    Thinking…
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="fs-composer-wrap">
            <div className="fs-composer">
              <textarea
                ref={inputRef}
                className="fs-input"
                rows={1}
                placeholder="Ask for slide outlines, structure, or copy…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                disabled={loading}
                aria-label="Message"
              />
              <button
                type="button"
                className="fs-send"
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                title="Send"
                aria-label="Send message"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M22 2L11 13" />
                  <path d="M22 2l-7 20-4-9-9-4 20-7z" />
                </svg>
              </button>
            </div>
            <p className="fs-footer-note">Shift+Enter for new line · Same API as main Slides chat</p>
          </div>
        </section>
      </main>
    </div>
  );
}
