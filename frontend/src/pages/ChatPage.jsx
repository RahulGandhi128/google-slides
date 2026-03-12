import React, { useState, useRef, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import '../App.css';

const API_BASE = '/api';

function PlanCard({ slide, index }) {
  const [open, setOpen] = useState(index === 0);
  const details = slide.details || slide.content || '';
  const layout = slide.layout || '';
  const elements = slide.elements || [];

  return (
    <div className="plan-card">
      <button
        type="button"
        className={`plan-card-header ${open ? 'open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="plan-card-number">Slide {slide.slide_number ?? index + 1}</span>
        <span className="plan-card-title">{slide.title || 'Untitled'}</span>
        <span className="plan-card-chevron">{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="plan-card-body">
          {layout && (
            <div className="plan-card-section">
              <strong>Layout</strong>
              <p>{layout}</p>
            </div>
          )}
          {details && (
            <div className="plan-card-section">
              <strong>What to add</strong>
              <p className="plan-card-details">{details}</p>
            </div>
          )}
          {slide.content && details !== slide.content && (
            <div className="plan-card-section">
              <strong>Content</strong>
              <p className="plan-card-content">{slide.content}</p>
            </div>
          )}
          {elements.length > 0 && (
            <div className="plan-card-section">
              <strong>Elements</strong>
              <ul className="plan-card-elements">
                {elements.map((el, i) => (
                  <li key={i}>
                    {el.type}: {el.text || el.query || JSON.stringify(el)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PlanDisplay({ plan, onProceed, isExecuting }) {
  const aesthetics = plan.aesthetics || {};
  return (
    <div className="message-plan">
      <h4 className="message-plan-title">{plan.title}</h4>
      <div className="plan-accordion">
        {plan.slides?.map((s, i) => (
          <PlanCard key={i} slide={s} index={i} />
        ))}
      </div>
      {aesthetics.theme && (
        <div className="plan-aesthetics">
          <strong>Theme:</strong> {aesthetics.theme}
          {aesthetics.primary_color && ` • Color: ${aesthetics.primary_color}`}
          {aesthetics.suggested_icons_style && ` • Icons: ${aesthetics.suggested_icons_style}`}
        </div>
      )}
      <div className="plan-proceed-wrap">
        <button
          type="button"
          className="plan-proceed-btn"
          onClick={onProceed}
          disabled={isExecuting}
        >
          {isExecuting ? 'Building…' : 'Proceed — Build this presentation'}
        </button>
      </div>
    </div>
  );
}

function MessageBubble({ message, isUser, onProceedPlan, isExecutingPlan }) {
  const toolCalls = message.toolCalls || [];
  const hasTools = !isUser && toolCalls.length > 0;
  const hasPlan = message.plan && message.hasPlan;

  return (
    <div
      className={`message ${isUser ? 'message-user' : 'message-assistant'}`}
    >
      <div className="message-avatar">
        {isUser ? (
          <span className="avatar-icon">U</span>
        ) : (
          <span className="avatar-icon assistant">G</span>
        )}
      </div>
      <div className="message-content">
        {hasPlan ? (
          <PlanDisplay
            plan={message.plan}
            onProceed={() => onProceedPlan(message.plan)}
            isExecuting={isExecutingPlan}
          />
        ) : (
          <div className="message-text">
            <ReactMarkdown>{message.content || ''}</ReactMarkdown>
          </div>
        )}
        {hasTools && (
          <details className="message-tools">
            <summary className="message-tools-summary">
              Tools used: {toolCalls.map((t) => t.name).join(', ')}
            </summary>
            <div className="message-tools-list">
              {toolCalls.map((t, i) => (
                <div key={i} className="message-tool-item">
                  <span className="message-tool-name">{t.name}</span>
                  <pre className="message-tool-args">
                    {JSON.stringify(t.args || {}, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isExecutingPlan, setIsExecutingPlan] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [driveFiles, setDriveFiles] = useState([]);
  const [driveFilesLoading, setDriveFilesLoading] = useState(false);
  const [planMode, setPlanMode] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const fileId = searchParams.get('fileId');
    const fileName = searchParams.get('fileName');
    const mimeType = searchParams.get('mimeType') || '';
    if (fileId && fileName) {
      setSelectedFile({
        id: fileId,
        name: decodeURIComponent(fileName),
        mimeType: mimeType || 'application/vnd.google-apps.presentation',
      });
    } else {
      setSelectedFile(null);
    }
  }, [searchParams]);

  const updateUrlForFile = (file) => {
    if (!file) {
      const next = new URLSearchParams(searchParams);
      next.delete('fileId');
      next.delete('fileName');
      next.delete('mimeType');
      setSearchParams(next, { replace: true });
    } else {
      setSearchParams(
        {
          fileId: file.id,
          fileName: file.name,
          mimeType: file.mimeType || '',
        },
        { replace: true }
      );
    }
  };

  const selectFile = (file) => {
    const isSlides = (file.mimeType || '').includes('presentation');
    if (!isSlides) return;
    setSelectedFile({ id: file.id, name: file.name, mimeType: file.mimeType || '' });
    updateUrlForFile({ id: file.id, name: file.name, mimeType: file.mimeType || '' });
  };

  const fetchDriveFiles = async () => {
    setDriveFilesLoading(true);
    try {
      const res = await fetch(`${API_BASE}/drive/files?page_size=50`);
      const data = await res.json();
      if (res.ok && data.files) {
        setDriveFiles(data.files.filter((f) => (f.mimeType || '').includes('presentation')));
      }
    } catch (err) {
      console.error('Failed to fetch drive files:', err);
    } finally {
      setDriveFilesLoading(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const executePlan = async (plan) => {
    if (!plan || isExecutingPlan) return;
    setIsExecutingPlan(true);
    const execMsg = {
      role: 'assistant',
      content: 'Building your presentation from the plan…',
      toolCalls: [],
    };
    setMessages((prev) => [...prev, execMsg]);

    try {
      const res = await fetch(`${API_BASE}/execute-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan,
          currentFile: selectedFile ? { id: selectedFile.id, name: selectedFile.name, mimeType: selectedFile.mimeType } : null,
        }),
      });
      const data = await res.json();

      setMessages((prev) => {
        const next = [...prev];
        const idx = next.findIndex((m) => m === execMsg);
        if (idx >= 0) {
          next[idx] = {
            role: 'assistant',
            content: data.message?.content || 'Presentation created.',
            toolCalls: data.toolCalls || [],
          };
        }
        return next;
      });
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        const idx = next.findIndex((m) => m === execMsg);
        if (idx >= 0) {
          next[idx] = {
            role: 'assistant',
            content: `Error: ${err.message}. Ensure the backend is running and gws is authenticated.`,
            toolCalls: [],
          };
        }
        return next;
      });
    } finally {
      setIsExecutingPlan(false);
      scrollToBottom();
    }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      if (planMode) {
        const res = await fetch(`${API_BASE}/plan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic: text }),
        });
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.content || 'No response.',
            plan: data.plan,
            hasPlan: data.hasPlan,
            toolCalls: [],
          },
        ]);
      } else {
        const chatMessages = [...messages, userMessage].map((m) => ({
          role: m.role,
          content: typeof m.content === 'string' ? m.content : m.content?.[0]?.text ?? '',
        }));

        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: chatMessages,
            currentFile: selectedFile ? { id: selectedFile.id, name: selectedFile.name, mimeType: selectedFile.mimeType } : null,
          }),
        });

        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.error || 'Request failed');
        }

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.message?.content || 'No response.',
            toolCalls: data.toolCalls || [],
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}. Ensure the backend is running and gws is authenticated.`,
          toolCalls: [],
        },
      ]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const adjustTextareaHeight = () => {
    const ta = inputRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app assistant-page">
      <header className="header">
        <div className="header-logo">
          <span className="logo-icon">G</span>
          <h1>GWS Slides Assistant</h1>
          <Link to="/" className="drive-nav-link">Drive</Link>
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={() => setSidebarOpen((o) => !o)}
            title={sidebarOpen ? 'Hide file panel' : 'Show file panel'}
            aria-label={sidebarOpen ? 'Hide file panel' : 'Show file panel'}
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>
        <p className="header-subtitle">
          Manage Google Slides, Drive & Workspace from chat — powered by gws CLI
        </p>
      </header>

      <div className="chat-layout">
        {sidebarOpen && (
          <aside className="chat-sidebar">
            <div className="chat-sidebar-header">
              <h3>Current file</h3>
            </div>
            {selectedFile ? (
              <div className="chat-sidebar-file">
                <div className="chat-sidebar-file-info">
                  <span className="chat-sidebar-file-name" title={selectedFile.name}>{selectedFile.name}</span>
                  <a
                    href={`https://docs.google.com/presentation/d/${selectedFile.id}/edit`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="chat-sidebar-open-link"
                  >
                    Open in Slides
                  </a>
                </div>
                <div className="chat-sidebar-actions">
                  <button
                    type="button"
                    className="chat-sidebar-change-btn"
                    onClick={fetchDriveFiles}
                    disabled={driveFilesLoading}
                  >
                    {driveFilesLoading ? 'Loading…' : 'Change file'}
                  </button>
                  <button
                    type="button"
                    className="chat-sidebar-clear-btn"
                    onClick={() => {
                      setSelectedFile(null);
                      updateUrlForFile(null);
                    }}
                  >
                    Clear
                  </button>
                </div>
                {driveFiles.length > 0 && (
                  <ul className="chat-sidebar-file-list">
                    {driveFiles.map((f) => (
                      <li key={f.id}>
                        <button
                          type="button"
                          className={`chat-sidebar-file-item ${selectedFile?.id === f.id ? 'selected' : ''}`}
                          onClick={() => selectFile(f)}
                        >
                          {f.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <div className="chat-sidebar-empty">
                <p>No file selected</p>
                <button
                  type="button"
                  className="chat-sidebar-change-btn"
                  onClick={fetchDriveFiles}
                  disabled={driveFilesLoading}
                >
                  {driveFilesLoading ? 'Loading…' : 'Select a file'}
                </button>
                {driveFiles.length > 0 && (
                  <ul className="chat-sidebar-file-list">
                    {driveFiles.map((f) => (
                      <li key={f.id}>
                        <button
                          type="button"
                          className="chat-sidebar-file-item"
                          onClick={() => selectFile(f)}
                        >
                          {f.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </aside>
        )}
        <main className="chat-container">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-card">
                <h2>{planMode ? 'Create a presentation plan' : selectedFile ? `Working on "${selectedFile.name}"` : 'What can I help you with?'}</h2>
                <p>Try asking:</p>
                <ul className="suggestions">
                  {planMode ? (
                    <>
                      <li onClick={() => setInput('Create a plan for a 5-slide product launch presentation')}>
                        Create a plan for a 5-slide product launch presentation
                      </li>
                      <li onClick={() => setInput('Outline slides for a quarterly business review')}>
                        Outline slides for a quarterly business review
                      </li>
                      <li onClick={() => setInput('Make a deck about AI in healthcare')}>
                        Make a deck about AI in healthcare
                      </li>
                    </>
                  ) : selectedFile ? (
                    <>
                      <li onClick={() => setInput('Show me the structure of this presentation')}>
                        Show me the structure of this presentation
                      </li>
                      <li onClick={() => setInput('Add a new slide with a title and bullet points')}>
                        Add a new slide with a title and bullet points
                      </li>
                      <li onClick={() => setInput('Change the title slide text')}>
                        Change the title slide text
                      </li>
                      <li onClick={() => setInput('Add a colored background to the first slide')}>
                        Add a colored background to the first slide
                      </li>
                    </>
                  ) : (
                    <>
                      <li onClick={() => setInput('List my recent files in Google Drive')}>
                        List my recent files in Google Drive
                      </li>
                      <li onClick={() => setInput('Create a new Google Slides presentation')}>
                        Create a new Google Slides presentation
                      </li>
                      <li onClick={() => setInput('Search for presentations in my Drive')}>
                        Search for presentations in my Drive
                      </li>
                      <li onClick={() => setInput('Show me my Drive files')}>
                        Show me my Drive files
                      </li>
                    </>
                  )}
                </ul>
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  message={msg}
                  isUser={msg.role === 'user'}
                  onProceedPlan={executePlan}
                  isExecutingPlan={isExecutingPlan}
                />
              ))}
              {isLoading && (
                <div className="message message-assistant">
                  <div className="message-avatar">
                    <span className="avatar-icon assistant">G</span>
                  </div>
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>
      </div>

      <div className="input-area-floating">
        <div className="input-inbox">
          <div className="input-inner">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={planMode ? 'Describe your presentation topic...' : (selectedFile ? `Ask about "${selectedFile.name}" or anything else...` : 'Ask anything about Google Slides, Drive...')}
              rows={1}
              disabled={isLoading}
              className="chat-textarea"
            />
          </div>
          <div className="input-footer">
            <div className="input-mode-buttons">
              <button
                type="button"
                className={`mode-btn ${!planMode ? 'active' : ''}`}
                onClick={() => setPlanMode(false)}
                title="Chat mode"
              >
                Chat
              </button>
              <button
                type="button"
                className={`mode-btn ${planMode ? 'active' : ''}`}
                onClick={() => setPlanMode(true)}
                title="Plan mode - create presentation outline"
              >
                Plan
              </button>
            </div>
            <button
              className="send-btn"
              onClick={sendMessage}
              disabled={!input.trim() || isLoading}
              aria-label="Send"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
