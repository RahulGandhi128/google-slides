import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { getColor, getPalette } from 'colorthief';
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

function PlanDisplay({ plan, onProceed, isExecuting, buildMode, selectedFile }) {
  const aesthetics = plan.aesthetics || {};
  const isModify = buildMode === 'modify';
  const canProceed = !isModify || (selectedFile && selectedFile.id);
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
          disabled={isExecuting || !canProceed}
        >
          {isExecuting ? (isModify ? 'Updating…' : 'Building…') : isModify ? 'Apply to this presentation' : 'Proceed — Build this presentation'}
        </button>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  isUser,
  onProceedPlan,
  isExecutingPlan,
  buildMode,
  selectedFile,
  onDesignOutline,
  onEditOutline,
  onSaveEditOutline,
  onCancelEditOutline,
  designingOutlineIndex,
  editingOutlineIndex,
  editingOutlineDraft,
  setEditingOutlineDraft,
  messageIndex,
  onReplyToMessage,
  onUseExtractionForReplacements,
}) {
  const toolCalls = message.toolCalls || [];
  const hasTools = !isUser && toolCalls.length > 0;
  const hasPlan = message.plan && message.hasPlan;
  const extractedSlides = message.extractedSlides;
  const replacementSlides = message.replacementSlides;
  const mode = message.mode || 'agent';
  const modeLabel = mode === 'design' ? 'Design' : mode === 'research' ? 'Research' : 'Agent';
  const isResearchWithContent = !isUser && mode === 'research' && !hasPlan && (message.content || '').trim();
  const isDesigningThis = designingOutlineIndex === messageIndex;
  const isEditingThis = editingOutlineIndex === messageIndex;

  return (
    <div
      className={`message ${isUser ? 'message-user' : 'message-assistant'} message-mode-${mode}`}
    >
      <div className="message-avatar">
        {isUser ? (
          <span className="avatar-icon">U</span>
        ) : (
          <span className="avatar-icon assistant">{mode === 'design' ? 'D' : mode === 'research' ? 'R' : 'A'}</span>
        )}
      </div>
      <div className="message-content">
        {!isUser && (
          <div className={`message-mode-label message-mode-label-${mode}`}>
            {modeLabel}
          </div>
        )}
        {hasPlan ? (
          <PlanDisplay
            plan={message.plan}
            onProceed={() => onProceedPlan(message.plan)}
            isExecuting={isExecutingPlan}
            buildMode={buildMode}
            selectedFile={selectedFile}
          />
        ) : isResearchWithContent && isEditingThis ? (
          <div className="message-research-edit">
            <textarea
              className="message-research-edit-textarea"
              value={editingOutlineDraft}
              onChange={(e) => setEditingOutlineDraft(e.target.value)}
              rows={12}
              placeholder="Edit the research outline..."
            />
            <div className="message-research-edit-actions">
              <button
                type="button"
                className="edit-outline-save-btn"
                onClick={() => onSaveEditOutline(messageIndex, editingOutlineDraft)}
              >
                Save
              </button>
              <button
                type="button"
                className="edit-outline-cancel-btn"
                onClick={onCancelEditOutline}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : extractedSlides && extractedSlides.length > 0 ? (
          <div className="message-extracted-card">
            <div className="message-extracted-header">Extracted from presentation</div>
            <div className="message-extracted-slides">
              {extractedSlides.map((s, i) => (
                <div key={i} className="message-extracted-slide-card">
                  <div className="message-extracted-slide-title">Slide {s.slideIndex ?? i + 1}: {s.title || 'Untitled'}</div>
                  <div className="message-extracted-slide-body">{(s.body || '').trim() || '(no body)'}</div>
                </div>
              ))}
            </div>
            {buildMode === 'modify' && onUseExtractionForReplacements && (
              <button
                type="button"
                className="message-extracted-use-btn"
                onClick={() => onUseExtractionForReplacements(extractedSlides)}
              >
                Use for replacements
              </button>
            )}
          </div>
        ) : replacementSlides && replacementSlides.length > 0 ? (
          <div className="message-replacement-card">
            <div className="message-replacement-header">Replacement suggestions</div>
            <div className="message-replacement-slides">
              {replacementSlides.map((s, i) => (
                <div key={i} className={`message-replacement-slide-card message-replacement-${s.action || 'no_change'}`}>
                  <div className="message-replacement-slide-meta">Slide {s.slideIndex ?? i + 1} · {s.topic || '—'} · {s.action === 'replace' ? 'Replace' : 'No change'}</div>
                  {s.action === 'replace' && (s.replacementTitle || s.replacementBody) && (
                    <div className="message-replacement-slide-content">
                      {s.replacementTitle && <div className="message-replacement-slide-title">{s.replacementTitle}</div>}
                      {s.replacementBody && <div className="message-replacement-slide-body">{s.replacementBody}</div>}
                    </div>
                  )}
                  {s.notes && <div className="message-replacement-slide-notes">{s.notes}</div>}
                </div>
              ))}
            </div>
            {(message.content || '').trim() && (
              <div className="message-text message-replacement-raw">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            )}
          </div>
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
        {isResearchWithContent && onDesignOutline && !isEditingThis && (
          <div className="message-research-action">
            <button
              type="button"
              className="edit-outline-btn"
              onClick={() => onEditOutline(messageIndex, message.content)}
            >
              Edit outline
            </button>
            <button
              type="button"
              className="design-outline-btn"
              onClick={() => onDesignOutline(message.content, messageIndex)}
              disabled={isDesigningThis}
            >
              {isDesigningThis ? 'Designing…' : 'Design this outline'}
            </button>
            {onReplyToMessage && (
              <button
                type="button"
                className="reply-outline-btn"
                onClick={() => onReplyToMessage(messageIndex, message.content)}
              >
                Reply
              </button>
            )}
          </div>
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
  const [designingOutlineIndex, setDesigningOutlineIndex] = useState(null);
  const [editingOutlineIndex, setEditingOutlineIndex] = useState(null);
  const [editingOutlineDraft, setEditingOutlineDraft] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [driveFiles, setDriveFiles] = useState([]);
  const [driveFilesLoading, setDriveFilesLoading] = useState(false);
  const [buildMode, setBuildMode] = useState('new'); // 'new' | 'modify'
  const [chatMode, setChatMode] = useState('research'); // 'research' | 'design' | 'agent' (default research for new chat)
  const [sessionId, setSessionId] = useState(null);
  const [chatSessions, setChatSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [attachedDocuments, setAttachedDocuments] = useState([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [savedDocuments, setSavedDocuments] = useState([]);
  const [mentionLoading, setMentionLoading] = useState(false);
  const [sessionMenuOpen, setSessionMenuOpen] = useState(null);
  const [deletingSessionId, setDeletingSessionId] = useState(null);
  const [presentationTypeMenuOpen, setPresentationTypeMenuOpen] = useState(false);
  const [slideOutlineDialogOpen, setSlideOutlineDialogOpen] = useState(false);
  const [slideOutlineName, setSlideOutlineName] = useState('');
  const [slideOutlineSlides, setSlideOutlineSlides] = useState([
    { title: '', guidance: '' },
  ]);
  const [savedSlideOutlines, setSavedSlideOutlines] = useState([]);
  const [selectedSlideOutline, setSelectedSlideOutline] = useState(null);
  const [editingSlideOutlineId, setEditingSlideOutlineId] = useState(null);
  const [loadedSlideOutlineSnapshot, setLoadedSlideOutlineSnapshot] = useState(null);
  const [deletingSlideOutlineId, setDeletingSlideOutlineId] = useState(null);
  const [slideOutlineSaveStatus, setSlideOutlineSaveStatus] = useState(null);
  const [designOutlineDialogOpen, setDesignOutlineDialogOpen] = useState(false);
  const [designOutlineDialogContent, setDesignOutlineDialogContent] = useState('');
  const [designOutlineDialogMessageIndex, setDesignOutlineDialogMessageIndex] = useState(null);
  const [designOutlineMyLogoPreview, setDesignOutlineMyLogoPreview] = useState(null);
  const [designOutlineTargetLogoPreview, setDesignOutlineTargetLogoPreview] = useState(null);
  const [designOutlineMyLogoUrl, setDesignOutlineMyLogoUrl] = useState('');
  const [designOutlineTargetLogoUrl, setDesignOutlineTargetLogoUrl] = useState('');
  const [designOutlineMyCorner, setDesignOutlineMyCorner] = useState('top_left');
  const [designOutlineTargetCorner, setDesignOutlineTargetCorner] = useState('top_right');
  const [designOutlineMyWidthEmu, setDesignOutlineMyWidthEmu] = useState(600000);
  const [designOutlineMyHeightEmu, setDesignOutlineMyHeightEmu] = useState(600000);
  const [designOutlineMyMarginEmu, setDesignOutlineMyMarginEmu] = useState(250000);
  const [designOutlineTargetWidthEmu, setDesignOutlineTargetWidthEmu] = useState(600000);
  const [designOutlineTargetHeightEmu, setDesignOutlineTargetHeightEmu] = useState(600000);
  const [designOutlineTargetMarginEmu, setDesignOutlineTargetMarginEmu] = useState(250000);
  const [designOutlineTab, setDesignOutlineTab] = useState('logos'); // 'logos' | 'advanced'
  const [designOutlineAddLogosToSlides, setDesignOutlineAddLogosToSlides] = useState(false);
  const [logoOverrides, setLogoOverrides] = useState(null);
  const [designOutlineExtracted, setDesignOutlineExtracted] = useState(null);
  const [designOutlineExtracting, setDesignOutlineExtracting] = useState(false);
  const [designOutlineSavingBranding, setDesignOutlineSavingBranding] = useState(false);
  const [extractLoading, setExtractLoading] = useState(false);
  const [pinnedExtractedSlides, setPinnedExtractedSlides] = useState(null);
  const [findReplacementsLoading, setFindReplacementsLoading] = useState(false);
  const [fileCardPickerOpen, setFileCardPickerOpen] = useState(false);
  const fileCardPickerRef = useRef(null);
  /** Research mode: strict verbatim-from-source (default on). */
  const [groundResponseEnabled, setGroundResponseEnabled] = useState(() => {
    try {
      const v = localStorage.getItem('research_ground_response');
      if (v === null) return true;
      return v === 'true';
    } catch {
      return true;
    }
  });
  const persistGroundResponse = (value) => {
    setGroundResponseEnabled(value);
    try {
      localStorage.setItem('research_ground_response', String(value));
    } catch (_) {}
  };
  /** Defaults for plan/execute (previously editable in Settings). */
  const designSettings = {
    style: 'minimalist_bw',
    maxLinesPerSlide: 5,
    printable: false,
  };
  const sessionMenuRef = useRef(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const mentionPopupRef = useRef(null);
  const presentationTypeMenuRef = useRef(null);
  const designOutlineMyLogoInputRef = useRef(null);
  const designOutlineTargetLogoInputRef = useRef(null);
  const designOutlineLogoInputRef = useRef(null);

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

  const fetchChatSessions = async () => {
    setSessionsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`);
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

  useEffect(() => {
    fetchChatSessions();
  }, []);

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
            plan: m.plan,
            hasPlan: m.hasPlan,
            mode: m.mode || 'agent',
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
    fetchChatSessions();
  };

  const fetchSavedDocuments = async () => {
    setMentionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/documents`);
      const data = await res.json();
      if (res.ok && data.documents) setSavedDocuments(data.documents);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setMentionLoading(false);
    }
  };

  const filteredMentionDocs = savedDocuments.filter(
    (d) => !mentionQuery.trim() || d.filename.toLowerCase().includes(mentionQuery.toLowerCase())
  );

  const handleInputChange = (e) => {
    const v = e.target.value;
    setInput(v);
    const selStart = e.target.selectionStart;
    const beforeCaret = v.slice(0, selStart);
    const atMatch = beforeCaret.match(/@([^\s]*)$/);
    if (atMatch) {
      setMentionOpen(true);
      setMentionQuery(atMatch[1] || '');
      if (savedDocuments.length === 0) fetchSavedDocuments();
    } else {
      setMentionOpen(false);
    }
  };

  const selectMentionDoc = (doc) => {
    const caret = inputRef.current?.selectionStart ?? input.length;
    const beforeAt = input.slice(0, caret).replace(/@[^\s]*$/, '');
    const afterAt = input.slice(caret);
    // Keep only the attachment card in UI; do not inject @filename text in textarea.
    setInput(`${beforeAt}${afterAt}`.replace(/\s{2,}/g, ' ').trimStart());
    setAttachedDocuments((prev) => {
      if (prev.some((d) => d.upload_id === doc.upload_id)) return prev;
      return [...prev, { upload_id: doc.upload_id, filename: doc.filename }];
    });
    setMentionOpen(false);
    setMentionQuery('');
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = (file.name || '').toLowerCase().slice(-5);
    if (!ext.endsWith('.pdf') && !ext.endsWith('.docx')) {
      alert('Only PDF and DOCX files are supported.');
      return;
    }
    setUploadingDoc(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/documents/ingest`, { method: 'POST', body: form });
      const data = await res.json();
      if (res.ok && data.upload_id) {
        setAttachedDocuments((prev) => [...prev, { upload_id: data.upload_id, filename: data.filename }]);
      } else {
        alert(data.detail || 'Upload failed');
      }
    } catch (err) {
      alert(err.message || 'Upload failed');
    } finally {
      setUploadingDoc(false);
      e.target.value = '';
    }
  };

  useEffect(() => {
    if (!mentionOpen) return;
    const onDocClick = (e) => {
      if (mentionPopupRef.current && !mentionPopupRef.current.contains(e.target) && inputRef.current && !inputRef.current.contains(e.target)) {
        setMentionOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [mentionOpen]);

  const fetchSlideOutlines = async () => {
    try {
      const res = await fetch(`${API_BASE}/slide-templates?limit=100`);
      const data = await res.json();
      if (res.ok && Array.isArray(data.templates)) {
        setSavedSlideOutlines(data.templates);
      }
    } catch (err) {
      console.error('Failed to fetch slide templates:', err);
    }
  };

  useEffect(() => {
    fetchSlideOutlines();
  }, []);

  useEffect(() => {
    if (!presentationTypeMenuOpen) return;
    const onClick = (e) => {
      if (
        presentationTypeMenuRef.current &&
        !presentationTypeMenuRef.current.contains(e.target)
      ) {
        setPresentationTypeMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [presentationTypeMenuOpen]);

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
    const handleClickOutside = (e) => {
      if (fileCardPickerRef.current && !fileCardPickerRef.current.contains(e.target)) {
        setFileCardPickerOpen(false);
      }
    };
    if (fileCardPickerOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [fileCardPickerOpen]);

  useEffect(() => {
    if (buildMode === 'modify') fetchDriveFiles();
  }, [buildMode]);

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

  const handleOpenDesignOutlineDialog = (outlineContent, messageIndex) => {
    const revokeIfBlob = (url) => {
      if (typeof url === 'string' && url.startsWith('blob:')) URL.revokeObjectURL(url);
    };
    revokeIfBlob(designOutlineMyLogoPreview);
    revokeIfBlob(designOutlineTargetLogoPreview);
    setDesignOutlineDialogContent(outlineContent);
    setDesignOutlineDialogMessageIndex(messageIndex);
    setDesignOutlineMyLogoPreview(null);
    setDesignOutlineTargetLogoPreview(null);
    setDesignOutlineMyLogoUrl('');
    setDesignOutlineTargetLogoUrl('');
    setDesignOutlineExtracted(null);
    setDesignOutlineExtracting(false);
    setDesignOutlineSavingBranding(false);
    setDesignOutlineAddLogosToSlides(false);
    setDesignOutlineTab('logos');
    setDesignOutlineDialogOpen(true);
    if (designOutlineMyLogoInputRef.current) designOutlineMyLogoInputRef.current.value = '';
    if (designOutlineTargetLogoInputRef.current) designOutlineTargetLogoInputRef.current.value = '';

    // Load last-saved DB branding settings for reuse
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/branding/logos`);
        const data = await res.json();
        if (!res.ok) return;
        const prefs = data.prefs || {};
        if (prefs.myCorner) setDesignOutlineMyCorner(prefs.myCorner);
        if (prefs.targetCorner) setDesignOutlineTargetCorner(prefs.targetCorner);
        if (prefs.myWidthEmu) setDesignOutlineMyWidthEmu(prefs.myWidthEmu);
        if (prefs.myHeightEmu) setDesignOutlineMyHeightEmu(prefs.myHeightEmu);
        if (prefs.myMarginEmu) setDesignOutlineMyMarginEmu(prefs.myMarginEmu);
        if (prefs.targetWidthEmu) setDesignOutlineTargetWidthEmu(prefs.targetWidthEmu);
        if (prefs.targetHeightEmu) setDesignOutlineTargetHeightEmu(prefs.targetHeightEmu);
        if (prefs.targetMarginEmu) setDesignOutlineTargetMarginEmu(prefs.targetMarginEmu);
        const logos = Array.isArray(data.logos) ? data.logos : [];
        const my = logos.find((l) => l.role === 'my');
        const tgt = logos.find((l) => l.role === 'target');
        if (my) {
          if (my.logoUrl) {
            setDesignOutlineMyLogoPreview(my.logoUrl);
          } else if (my.smallDataUrl) {
            setDesignOutlineMyLogoPreview(my.smallDataUrl);
          }
        }
        if (tgt) {
          if (tgt.logoUrl) {
            setDesignOutlineTargetLogoPreview(tgt.logoUrl);
          } else if (tgt.smallDataUrl) {
            setDesignOutlineTargetLogoPreview(tgt.smallDataUrl);
          }
        }
      } catch (err) {
        console.error('Failed to load branding:', err);
      }
    };
    load();
  };

  const handleCloseDesignOutlineDialog = () => {
    const revokeIfBlob = (url) => {
      if (typeof url === 'string' && url.startsWith('blob:')) URL.revokeObjectURL(url);
    };
    revokeIfBlob(designOutlineMyLogoPreview);
    revokeIfBlob(designOutlineTargetLogoPreview);
    setDesignOutlineDialogOpen(false);
    setDesignOutlineDialogContent('');
    setDesignOutlineDialogMessageIndex(null);
    setDesignOutlineMyLogoPreview(null);
    setDesignOutlineTargetLogoPreview(null);
    setDesignOutlineMyLogoUrl('');
    setDesignOutlineTargetLogoUrl('');
    setDesignOutlineExtracted(null);
    setDesignOutlineExtracting(false);
    setDesignOutlineSavingBranding(false);
  };

  const handleDesignOutlineLogoChange = (role, e) => {
    const file = e.target?.files?.[0];
    if (!file) return;
    if (role === 'my') {
      if (designOutlineMyLogoPreview) URL.revokeObjectURL(designOutlineMyLogoPreview);
      setDesignOutlineMyLogoPreview(URL.createObjectURL(file));
      setDesignOutlineMyLogoUrl('');
      return;
    }

    if (role === 'target') {
      if (designOutlineTargetLogoPreview) URL.revokeObjectURL(designOutlineTargetLogoPreview);
      setDesignOutlineTargetLogoPreview(URL.createObjectURL(file));
      setDesignOutlineTargetLogoUrl('');
      // Extract palette from TARGET logo
      setDesignOutlineExtracted(null);
      setDesignOutlineExtracting(true);
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = async () => {
        try {
          const [dominant, palette] = await Promise.all([
            getColor(img),
            getPalette(img, { colorCount: 6 }),
          ]);
          setDesignOutlineExtracted({
            dominant: { hex: dominant.hex() },
            palette: (palette || []).map((c) => ({ hex: c.hex() })),
          });
        } catch (err) {
          console.error('Color extraction failed:', err);
          setDesignOutlineExtracted(null);
        } finally {
          setDesignOutlineExtracting(false);
        }
      };
      img.onerror = () => {
        setDesignOutlineExtracting(false);
        setDesignOutlineExtracted(null);
      };
      img.src = URL.createObjectURL(file);
    }
  };

  const handleClearDesignOutlineLogo = (role) => {
    if (role === 'my') {
      if (designOutlineMyLogoPreview && designOutlineMyLogoPreview.startsWith('blob:')) {
        URL.revokeObjectURL(designOutlineMyLogoPreview);
      }
      setDesignOutlineMyLogoPreview(null);
      setDesignOutlineMyLogoUrl('');
      if (designOutlineMyLogoInputRef.current) designOutlineMyLogoInputRef.current.value = '';
      return;
    }
    if (designOutlineTargetLogoPreview && designOutlineTargetLogoPreview.startsWith('blob:')) {
      URL.revokeObjectURL(designOutlineTargetLogoPreview);
    }
    setDesignOutlineTargetLogoPreview(null);
    setDesignOutlineTargetLogoUrl('');
    setDesignOutlineExtracted(null);
    if (designOutlineTargetLogoInputRef.current) designOutlineTargetLogoInputRef.current.value = '';
  };

  const saveBrandingLogosAndPrefs = async () => {
    // Upload logos (if file chosen) or set by URL; then save corner prefs in DB.
    const myFile = designOutlineMyLogoInputRef.current?.files?.[0];
    const targetFile = designOutlineTargetLogoInputRef.current?.files?.[0];
    const myUrl = (designOutlineMyLogoUrl || '').trim();
    const targetUrl = (designOutlineTargetLogoUrl || '').trim();

    const uploadOne = async (role, file) => {
      const form = new FormData();
      form.append('role', role);
      form.append('file', file);
      const res = await fetch(`${API_BASE}/branding/logos`, { method: 'POST', body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Failed to upload ${role} logo`);
      return data;
    };

    const setUrlOne = async (role, url) => {
      const res = await fetch(`${API_BASE}/branding/logos/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, url }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Failed to set ${role} logo URL`);
      return data;
    };

    const tasks = [];
    if (myFile) tasks.push(uploadOne('my', myFile));
    else if (myUrl) tasks.push(setUrlOne('my', myUrl));
    if (targetFile) tasks.push(uploadOne('target', targetFile));
    else if (targetUrl) tasks.push(setUrlOne('target', targetUrl));
    if (tasks.length) await Promise.all(tasks);

    const prefsRes = await fetch(`${API_BASE}/branding/logo-prefs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        myCorner: designOutlineMyCorner,
        targetCorner: designOutlineTargetCorner,
        myWidthEmu: designOutlineMyWidthEmu,
        myHeightEmu: designOutlineMyHeightEmu,
        myMarginEmu: designOutlineMyMarginEmu,
        targetWidthEmu: designOutlineTargetWidthEmu,
        targetHeightEmu: designOutlineTargetHeightEmu,
        targetMarginEmu: designOutlineTargetMarginEmu,
      }),
    });
    const prefsData = await prefsRes.json().catch(() => ({}));
    if (!prefsRes.ok) throw new Error(prefsData.detail || 'Failed to save logo corner preferences');

    setLogoOverrides({
      addLogosToSlides: designOutlineAddLogosToSlides,
      myCorner: designOutlineMyCorner,
      targetCorner: designOutlineTargetCorner,
      myWidthEmu: designOutlineMyWidthEmu,
      myHeightEmu: designOutlineMyHeightEmu,
      myMarginEmu: designOutlineMyMarginEmu,
      targetWidthEmu: designOutlineTargetWidthEmu,
      targetHeightEmu: designOutlineTargetHeightEmu,
      targetMarginEmu: designOutlineTargetMarginEmu,
    });
  };

  const handleDesignOutlineConfirm = async () => {
    const content = designOutlineDialogContent;
    const messageIndex = designOutlineDialogMessageIndex;
    const palette = designOutlineExtracted
      ? {
          dominant: designOutlineExtracted.dominant.hex,
          palette: designOutlineExtracted.palette.map((c) => c.hex),
        }
      : null;
    setDesignOutlineSavingBranding(true);
    try {
      await saveBrandingLogosAndPrefs();
    } catch (err) {
      alert(err.message || 'Failed to save logos/preferences');
      setDesignOutlineSavingBranding(false);
      return;
    }
    handleCloseDesignOutlineDialog();
    if (content != null && messageIndex != null) handleDesignOutline(content, messageIndex, palette);
  };

  const handleExtractPresentation = async () => {
    if (!selectedFile?.id || extractLoading) return;
    setExtractLoading(true);
    try {
      const res = await fetch(`${API_BASE}/extract-presentation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ presentationId: selectedFile.id }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Extract failed');
      const slides = data.slides || [];
      const lines = slides.map(
        (s) => `**Slide ${s.slideIndex}:** ${s.title || 'Untitled'}\n${(s.body || '').trim() ? s.body.trim() : '(no body)'}`
      );
      const content = `**Extracted from "${selectedFile.name}":**\n\n${lines.join('\n\n')}`;
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content, mode: 'agent', extractedSlides: slides },
      ]);
      scrollToBottom();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Extract failed: ${err.message}`, mode: 'agent' },
      ]);
      scrollToBottom();
    } finally {
      setExtractLoading(false);
    }
  };

  const handleUseExtractionForReplacements = (slides) => {
    if (slides && Array.isArray(slides) && slides.length > 0) {
      setPinnedExtractedSlides(slides);
      inputRef.current?.focus();
    }
  };

  const handleFindReplacements = async () => {
    if (!pinnedExtractedSlides?.length || findReplacementsLoading) return;
    setFindReplacementsLoading(true);
    const instructions = input.trim();
    const documents = (attachedDocuments || []).map((d) => ({
      upload_id: d.upload_id,
      filename: d.filename || '',
    }));
    try {
      const res = await fetch(`${API_BASE}/research-modify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extractedSlides: pinnedExtractedSlides,
          instructions: instructions || undefined,
          documents: documents.length ? documents : undefined,
          sessionId,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Find replacements failed');
      if (data.sessionId) setSessionId(data.sessionId);
      fetchChatSessions();
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.message?.content || 'Replacements generated.',
          mode: 'research',
          toolCalls: data.toolCalls || [],
          replacementSlides: data.message?.replacementSlides,
        },
      ]);
      setPinnedExtractedSlides(null);
      setInput('');
      setAttachedDocuments([]);
      scrollToBottom();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message}`, mode: 'research', replacementSlides: null },
      ]);
      scrollToBottom();
    } finally {
      setFindReplacementsLoading(false);
    }
  };

  const handleDesignOutline = async (outlineContent, messageIndex, colorPalette = null) => {
    if (!outlineContent || designingOutlineIndex != null) return;
    setDesigningOutlineIndex(messageIndex);
    // Try to include the original user request that produced this outline
    const maybeUserMsg = messages[messageIndex - 1];
    const userRequest =
      maybeUserMsg && maybeUserMsg.role === 'user' && typeof maybeUserMsg.content === 'string'
        ? maybeUserMsg.content
        : null;
    const documentId = attachedDocuments[0]?.upload_id ?? null;
    try {
      const res = await fetch(`${API_BASE}/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: userRequest || outlineContent,
          documentContext: outlineContent,
          sessionId,
          documentId,
          ...(buildMode === 'modify' && selectedFile && {
            currentFile: { id: selectedFile.id, name: selectedFile.name, mimeType: selectedFile.mimeType },
          }),
          ...(colorPalette && {
            colorPalette: {
              dominant: colorPalette.dominant,
              palette: colorPalette.palette || [],
            },
          }),
          designSettings: {
            style: designSettings.style,
            maxLinesPerSlide: designSettings.maxLinesPerSlide,
            printable: designSettings.printable,
          },
        }),
      });
      const data = await res.json();
      if (res.ok && data.sessionId) setSessionId(data.sessionId);
      fetchChatSessions();
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.content || 'Design plan generated.',
          plan: data.plan,
          hasPlan: data.hasPlan,
          toolCalls: [],
          mode: 'design',
        },
      ]);
      scrollToBottom();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error generating design: ${err.message}.`,
          toolCalls: [],
          mode: 'design',
        },
      ]);
      scrollToBottom();
    } finally {
      setDesigningOutlineIndex(null);
    }
  };

  const _normalizeSlidesForCompare = (slides) =>
    (slides || [])
      .map((s) => ({ title: (s.title || '').trim(), guidance: (s.guidance || '').trim() }))
      .filter((s) => s.title || s.guidance);

  const isSlideOutlineDirty = useMemo(() => {
    const normalized = _normalizeSlidesForCompare(slideOutlineSlides);
    const nameTrim = slideOutlineName.trim();
    if (!loadedSlideOutlineSnapshot) {
      return !!nameTrim || normalized.length > 0;
    }
    const snapNorm = _normalizeSlidesForCompare(loadedSlideOutlineSnapshot.slides);
    if (nameTrim !== (loadedSlideOutlineSnapshot.name || '').trim()) return true;
    if (normalized.length !== snapNorm.length) return true;
    return normalized.some((s, i) => s.title !== snapNorm[i]?.title || s.guidance !== snapNorm[i]?.guidance);
  }, [slideOutlineName, slideOutlineSlides, loadedSlideOutlineSnapshot]);

  const handleOpenSlideOutlineDialog = () => {
    setSlideOutlineName('');
    setSlideOutlineSlides([{ title: '', guidance: '' }]);
    setEditingSlideOutlineId(null);
    setLoadedSlideOutlineSnapshot(null);
    setSlideOutlineSaveStatus(null);
    setSlideOutlineDialogOpen(true);
  };

  const handleSelectSlideOutline = (outline) => {
    setSlideOutlineName(outline.name || '');
    setSlideOutlineSlides(
      (outline.slides || []).length > 0
        ? outline.slides.map((s) => ({ title: s.title || '', guidance: s.guidance || '' }))
        : [{ title: '', guidance: '' }]
    );
    setEditingSlideOutlineId(outline.id);
    setLoadedSlideOutlineSnapshot({ name: outline.name, slides: outline.slides || [] });
    setSlideOutlineSaveStatus(null);
  };

  const handleDeleteSlideOutline = async () => {
    const outline = savedSlideOutlines.find((o) => o.id === editingSlideOutlineId);
    if (!outline?.id || deletingSlideOutlineId) return;
    if (!confirm(`Delete "${outline.name}"?`)) return;
    setDeletingSlideOutlineId(outline.id);
    try {
      const res = await fetch(`${API_BASE}/slide-templates/${outline.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete');
      await fetchSlideOutlines();
      setSlideOutlineName('');
      setSlideOutlineSlides([{ title: '', guidance: '' }]);
      setEditingSlideOutlineId(null);
      setLoadedSlideOutlineSnapshot(null);
      setSlideOutlineSaveStatus(null);
    } catch (err) {
      alert(err.message || 'Failed to delete template');
    } finally {
      setDeletingSlideOutlineId(null);
    }
  };

  const handleAddSlideRow = () => {
    setSlideOutlineSlides((prev) => [...prev, { title: '', guidance: '' }]);
  };

  const handleUpdateSlideRow = (index, field, value) => {
    setSlideOutlineSlides((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const handleRemoveSlideRow = (index) => {
    setSlideOutlineSlides((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSaveSlideOutline = () => {
    const name = slideOutlineName.trim();
    const slides = _normalizeSlidesForCompare(slideOutlineSlides);
    if (!name || slides.length === 0) {
      alert('Add a name and at least one slide with title or guidance.');
      return;
    }
    setSlideOutlineSaveStatus('saving');
    fetch(`${API_BASE}/slide-templates`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, slides }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || 'Failed to save template');
        }
        await fetchSlideOutlines();
        setLoadedSlideOutlineSnapshot({ name, slides });
        setSlideOutlineSaveStatus('saved');
        setTimeout(() => setSlideOutlineSaveStatus(null), 2000);
      })
      .catch((err) => {
        setSlideOutlineSaveStatus(null);
        alert(err.message || 'Failed to save template');
      });
  };

  const handleSelectPresentationType = (outline) => {
    if (!outline) return;
    setSelectedSlideOutline(outline);
    setPresentationTypeMenuOpen(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleEditOutline = (messageIndex, currentContent) => {
    setEditingOutlineIndex(messageIndex);
    setEditingOutlineDraft(typeof currentContent === 'string' ? currentContent : '');
  };

  const handleSaveEditOutline = (messageIndex, newContent) => {
    setMessages((prev) => {
      const next = [...prev];
      if (next[messageIndex] && typeof newContent === 'string') {
        next[messageIndex] = { ...next[messageIndex], content: newContent };
      }
      return next;
    });
    setEditingOutlineIndex(null);
    setEditingOutlineDraft('');
  };

  const handleCancelEditOutline = () => {
    setEditingOutlineIndex(null);
    setEditingOutlineDraft('');
  };

  const handleReplyToMessage = (messageIndex, content) => {
    const text = typeof content === 'string' ? content : '';
    if (!text) return;
    setInput(text);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const executePlan = async (plan) => {
    if (!plan || isExecutingPlan) return;
    if (buildMode === 'modify' && !selectedFile?.id) return;
    setIsExecutingPlan(true);
    const execMsg = {
      role: 'assistant',
      content: buildMode === 'modify' ? 'Updating your presentation from the plan…' : 'Building your presentation from the plan…',
      toolCalls: [],
    };
    setMessages((prev) => [...prev, execMsg]);

    try {
      const res = await fetch(`${API_BASE}/execute-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan,
          sessionId,
          modifyExisting: buildMode === 'modify',
          currentFile: selectedFile ? { id: selectedFile.id, name: selectedFile.name, mimeType: selectedFile.mimeType } : null,
          ...(logoOverrides && { logoOverrides }),
          designSettings: {
            style: designSettings.style,
            maxLinesPerSlide: designSettings.maxLinesPerSlide,
            printable: designSettings.printable,
          },
        }),
      });
      const data = await res.json();

      if (data.sessionId) setSessionId(data.sessionId);
      fetchChatSessions();

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
    const baseText = input.trim();
    const presentationTypeText = selectedSlideOutline
      ? [
          `Presentation type: ${selectedSlideOutline.name}`,
          '',
          ...(selectedSlideOutline.slides || []).map(
            (s, idx) =>
              `${idx + 1}. ${s.title || 'Slide'}${
                s.guidance ? ` — ${s.guidance}` : ''
              }`
          ),
        ].join('\n')
      : '';
    const text = presentationTypeText
      ? (baseText ? `${baseText}\n\n${presentationTypeText}` : presentationTypeText)
      : baseText;
    if (!text || isLoading) return;

    const documents = attachedDocuments.map((d) => ({ upload_id: d.upload_id, filename: d.filename || '' }));
    const documentId = documents[0]?.upload_id ?? null;
    const documentFilename = documents[0]?.filename ?? null;
    const userMessage = { role: 'user', content: text, mode: chatMode };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    if (chatMode !== 'research') setAttachedDocuments([]);
    setIsLoading(true);

    try {
      if (chatMode === 'design') {
        const res = await fetch(`${API_BASE}/plan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: text,
            sessionId,
            documentId,
            ...(buildMode === 'modify' && selectedFile && {
              currentFile: { id: selectedFile.id, name: selectedFile.name, mimeType: selectedFile.mimeType },
            }),
            designSettings: {
              style: designSettings.style,
              maxLinesPerSlide: designSettings.maxLinesPerSlide,
              printable: designSettings.printable,
            },
          }),
        });
        const data = await res.json();
        if (data.sessionId) setSessionId(data.sessionId);
        fetchChatSessions();
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.content || 'No response.',
            plan: data.plan,
            hasPlan: data.hasPlan,
            toolCalls: [],
            mode: 'design',
          },
        ]);
      } else if (chatMode === 'research') {
        const res = await fetch(`${API_BASE}/research`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: text,
            documents,
            sessionId,
            groundResponse: groundResponseEnabled,
            ...(selectedSlideOutline && {
              slideTemplate: {
                name: selectedSlideOutline.name,
                slides: selectedSlideOutline.slides || [],
              },
            }),
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.error || 'Research request failed');
        if (data.sessionId) setSessionId(data.sessionId);
        fetchChatSessions();
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.message?.content || 'No response.',
            toolCalls: data.toolCalls || [],
            mode: 'research',
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
            sessionId,
            documentId,
            documentFilename,
            currentFile: selectedFile ? { id: selectedFile.id, name: selectedFile.name, mimeType: selectedFile.mimeType } : null,
          }),
        });

        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.error || 'Request failed');
        }

        if (data.sessionId) setSessionId(data.sessionId);
        fetchChatSessions();

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.message?.content || 'No response.',
            toolCalls: data.toolCalls || [],
            mode: 'agent',
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
    if (e.key === 'Escape') {
      setMentionOpen(false);
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app assistant-page chatgpt-layout">
      <div className="chat-layout">
        <aside className="chat-sidebar">
          <Link to="/" className="chat-sidebar-logo" title="Home">
            <span className="logo-icon">G</span>
          </Link>
          <div className="chat-sidebar-header">
            <h3>Chat history</h3>
          </div>
            <div className="chat-history-section">
              <button
                type="button"
                className="chat-sidebar-change-btn"
                onClick={startNewChat}
              >
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
            {buildMode === 'modify' && (
              <>
                <div className="chat-sidebar-header chat-sidebar-divider">
                  <h3>Files</h3>
                </div>
                <div className="chat-sidebar-file">
                  {driveFiles.length > 0 ? (
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
                  ) : (
                    <p className="chat-sidebar-empty">
                      {driveFilesLoading ? 'Loading…' : 'No files'}
                    </p>
                  )}
                </div>
              </>
            )}
        </aside>
        <main className="chat-container">
          <div className="mode-tabs-bar">
            <button
              type="button"
              className={`mode-tab mode-tab-build ${buildMode === 'new' ? 'active' : ''}`}
              onClick={() => setBuildMode('new')}
            >
              <span className="mode-tab-label">New presentation</span>
            </button>
            <button
              type="button"
              className={`mode-tab mode-tab-build ${buildMode === 'modify' ? 'active' : ''}`}
              onClick={() => setBuildMode('modify')}
            >
              <span className="mode-tab-label">Modify existing</span>
            </button>
            <button
              type="button"
              className={`mode-tab mode-tab-research ${chatMode === 'research' ? 'active' : ''}`}
              onClick={() => setChatMode('research')}
            >
              <span className="mode-tab-icon mode-tab-icon-research">R</span>
              <span className="mode-tab-label">Research</span>
            </button>
            <button
              type="button"
              className={`mode-tab mode-tab-design ${chatMode === 'design' ? 'active' : ''}`}
              onClick={() => setChatMode('design')}
            >
              <span className="mode-tab-icon mode-tab-icon-design">D</span>
              <span className="mode-tab-label">Design</span>
            </button>
            <button
              type="button"
              className={`mode-tab mode-tab-agent ${chatMode === 'agent' ? 'active' : ''}`}
              onClick={() => setChatMode('agent')}
            >
              <span className="mode-tab-icon mode-tab-icon-agent">A</span>
              <span className="mode-tab-label">Agent</span>
            </button>
          </div>
          <div className="chat-scroll">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-card">
                <h2>{chatMode === 'design' ? 'Design your presentation' : chatMode === 'research' ? 'Deep research on your documents' : selectedFile ? `Working on "${selectedFile.name}"` : 'What can I help you with?'}</h2>
                <p>{chatMode === 'research' ? 'Attach one or more documents (upload or @) to search across them, or ask without attaching.' : 'Try asking:'}</p>
                <ul className="suggestions">
                  {chatMode === 'design' ? (
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
                  ) : chatMode === 'research' ? (
                    <>
                      <li onClick={() => setInput('Summarize the main arguments and evidence')}>
                        Summarize the main arguments and evidence
                      </li>
                      <li onClick={() => setInput('What are the key findings and conclusions?')}>
                        What are the key findings and conclusions?
                      </li>
                      <li onClick={() => setInput('Compare and contrast the main themes')}>
                        Compare and contrast the main themes
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
                  messageIndex={i}
                  isUser={msg.role === 'user'}
                  onProceedPlan={executePlan}
                  isExecutingPlan={isExecutingPlan}
                  buildMode={buildMode}
                  selectedFile={selectedFile}
                  onDesignOutline={handleOpenDesignOutlineDialog}
                  onEditOutline={handleEditOutline}
                  onSaveEditOutline={handleSaveEditOutline}
                  onCancelEditOutline={handleCancelEditOutline}
                  designingOutlineIndex={designingOutlineIndex}
                  editingOutlineIndex={editingOutlineIndex}
                  editingOutlineDraft={editingOutlineDraft}
                  setEditingOutlineDraft={setEditingOutlineDraft}
                  onReplyToMessage={handleReplyToMessage}
                  onUseExtractionForReplacements={handleUseExtractionForReplacements}
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
          </div>
          {pinnedExtractedSlides && pinnedExtractedSlides.length > 0 && (
            <div className="chat-pinned-extraction-banner">
              <span className="chat-pinned-extraction-text">
                Using extraction ({pinnedExtractedSlides.length} slides). Add instructions and/or attach docs, then click Find replacements.
              </span>
              <button
                type="button"
                className="chat-pinned-extraction-clear"
                onClick={() => setPinnedExtractedSlides(null)}
                aria-label="Clear"
              >
                ×
              </button>
            </div>
          )}
          {buildMode === 'modify' && (
            <div className="chat-current-file-card" ref={fileCardPickerRef}>
              {selectedFile ? (
                <>
                  <div className="chat-current-file-card-inner">
                    <span className="chat-current-file-card-name" title={selectedFile.name}>
                      {selectedFile.name.length > 42 ? `${selectedFile.name.slice(0, 42)}…` : selectedFile.name}
                    </span>
                    <a
                      href={`https://docs.google.com/presentation/d/${selectedFile.id}/edit`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="chat-current-file-card-open"
                    >
                      Open in Slides
                    </a>
                    <button
                      type="button"
                      className="chat-current-file-card-change"
                      onClick={() => {
                        fetchDriveFiles();
                        setFileCardPickerOpen((o) => !o);
                      }}
                      disabled={driveFilesLoading}
                    >
                      {driveFilesLoading ? '…' : 'Change'}
                    </button>
                    <button
                      type="button"
                      className="chat-current-file-card-clear"
                      onClick={() => {
                        setSelectedFile(null);
                        updateUrlForFile(null);
                        setFileCardPickerOpen(false);
                      }}
                      aria-label="Clear selection"
                    >
                      ×
                    </button>
                  </div>
                  {fileCardPickerOpen && driveFiles.length > 0 && (
                    <ul className="chat-current-file-card-dropdown">
                      {driveFiles.map((f) => (
                        <li key={f.id}>
                          <button
                            type="button"
                            className={`chat-current-file-card-item ${selectedFile?.id === f.id ? 'selected' : ''}`}
                            onClick={() => {
                              selectFile(f);
                              setFileCardPickerOpen(false);
                            }}
                          >
                            {f.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <div className="chat-current-file-card-inner chat-current-file-card-select">
                  <span className="chat-current-file-card-name">Select a presentation</span>
                  <button
                    type="button"
                    className="chat-current-file-card-change"
                    onClick={() => {
                      fetchDriveFiles();
                      setFileCardPickerOpen((o) => !o);
                    }}
                    disabled={driveFilesLoading}
                  >
                    {driveFilesLoading ? 'Loading…' : 'Select'}
                  </button>
                  {fileCardPickerOpen && (
                    <ul className="chat-current-file-card-dropdown">
                      {driveFiles.length === 0 ? (
                        <li className="chat-current-file-card-empty">No presentations found</li>
                      ) : (
                        driveFiles.map((f) => (
                          <li key={f.id}>
                            <button
                              type="button"
                              className="chat-current-file-card-item"
                              onClick={() => {
                                selectFile(f);
                                setFileCardPickerOpen(false);
                              }}
                            >
                              {f.name}
                            </button>
                          </li>
                        ))
                      )}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
          <div className="input-area-inline">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx"
          className="input-file-hidden"
          onChange={handleFileUpload}
          aria-hidden="true"
        />
        {mentionOpen && (
          <div ref={mentionPopupRef} className="mention-popup">
            <input
              type="text"
              className="mention-search"
              placeholder="Search saved files…"
              value={mentionQuery}
              onChange={(e) => setMentionQuery(e.target.value)}
              autoFocus
            />
            <div className="mention-list">
              {mentionLoading ? (
                <div className="mention-item mention-item-muted">Loading…</div>
              ) : filteredMentionDocs.length === 0 ? (
                <div className="mention-item mention-item-muted">No documents found</div>
              ) : (
                filteredMentionDocs.map((doc) => (
                  <button
                    key={doc.upload_id}
                    type="button"
                    className="mention-item"
                    onClick={() => selectMentionDoc(doc)}
                  >
                    <span className="mention-item-name">{doc.filename}</span>
                    {doc.has_faiss && <span className="mention-item-badge">indexed</span>}
                  </button>
                ))
              )}
            </div>
          </div>
        )}
        <div className="input-inbox">
          {(attachedDocuments.length > 0 || uploadingDoc || selectedSlideOutline) && (
            <div className="input-attached-wrap">
              {uploadingDoc && (
                <span className="input-attached-label">Uploading…</span>
              )}
              {selectedSlideOutline && (
                <div className="input-attached input-attached-outline">
                  <span
                    className="input-attached-label"
                    title={`Presentation type: ${selectedSlideOutline.name}`}
                  >
                    {`Presentation type: ${selectedSlideOutline.name}`}
                  </span>
                  <button
                    type="button"
                    className="input-attached-remove"
                    onClick={() => setSelectedSlideOutline(null)}
                    aria-label="Remove presentation type"
                  >
                    ×
                  </button>
                </div>
              )}
              {attachedDocuments.map((doc, idx) => (
                <div key={doc.upload_id} className="input-attached">
                  <span className="input-attached-label" title={doc.filename}>{doc.filename}</span>
                  <button type="button" className="input-attached-remove" onClick={() => setAttachedDocuments((prev) => prev.filter((_, i) => i !== idx))} aria-label="Remove">×</button>
                </div>
              ))}
            </div>
          )}
          <div className="input-inner">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={pinnedExtractedSlides?.length ? 'Add instructions for replacements (optional). Attach docs, then click Find replacements.' : chatMode === 'design' ? 'Describe your presentation topic... Type @ for saved files' : chatMode === 'research' ? 'Ask a research question... Attach 0+ docs with @ or upload' : (selectedFile ? `Ask about "${selectedFile.name}" or type @ for saved files...` : 'Ask anything... Type @ for saved files')}
              rows={1}
              disabled={isLoading}
              className="chat-textarea"
            />
          </div>
          <div className="input-footer">
            <div className="input-footer-left">
              <button
                type="button"
                className="input-icon-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingDoc || isLoading}
                title="Upload PDF or DOCX"
                aria-label="Upload document"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
                </svg>
              </button>
              <div className="presentation-type-wrap" ref={presentationTypeMenuRef}>
                <button
                  type="button"
                  className="presentation-type-btn"
                  onClick={() =>
                    setPresentationTypeMenuOpen((open) => !open)
                  }
                  disabled={isLoading}
                >
                  Presentation type ▾
                </button>
                {presentationTypeMenuOpen && (
                  <div className="presentation-type-menu">
                    {savedSlideOutlines.length === 0 ? (
                      <div className="presentation-type-empty">
                        No saved types yet
                      </div>
                    ) : (
                      savedSlideOutlines.map((outline) => (
                        <button
                          key={outline.name}
                          type="button"
                          className="presentation-type-item"
                          onClick={() => handleSelectPresentationType(outline)}
                        >
                          {outline.name}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
              <button
                type="button"
                className="slide-outline-btn"
                onClick={handleOpenSlideOutlineDialog}
                disabled={isLoading}
              >
                Slide outline
              </button>
              {chatMode === 'research' && (
                <button
                  type="button"
                  role="switch"
                  aria-checked={groundResponseEnabled}
                  aria-label={
                    groundResponseEnabled
                      ? 'Ground response on: use source text verbatim'
                      : 'Ground response off'
                  }
                  className={`ground-response-toggle ${groundResponseEnabled ? 'on' : 'off'}`}
                  onClick={() => persistGroundResponse(!groundResponseEnabled)}
                  disabled={isLoading}
                  title={
                    groundResponseEnabled
                      ? 'Ground response on: answer using source wording as-is (no paraphrase)'
                      : 'Ground response off: the model may paraphrase or rephrase'
                  }
                >
                  <span className="ground-response-toggle-track" aria-hidden>
                    <span className="ground-response-toggle-knob" />
                  </span>
                  <span className="ground-response-toggle-label">Ground response</span>
                </button>
              )}
              {selectedFile && (
                <button
                  type="button"
                  className="slide-outline-btn extract-btn"
                  onClick={handleExtractPresentation}
                  disabled={extractLoading || isLoading}
                  title="Extract text from selected presentation"
                >
                  {extractLoading ? 'Extracting…' : 'Extract'}
                </button>
              )}
              {pinnedExtractedSlides && pinnedExtractedSlides.length > 0 && (
                <button
                  type="button"
                  className="slide-outline-btn find-replacements-btn"
                  onClick={handleFindReplacements}
                  disabled={findReplacementsLoading || isLoading}
                  title="Find replacement content per slide from docs"
                >
                  {findReplacementsLoading ? 'Finding…' : 'Find replacements'}
                </button>
              )}
            </div>
            <button
              className="send-btn"
              onClick={sendMessage}
              disabled={(!input.trim() && !selectedSlideOutline) || isLoading}
              aria-label="Send"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </div>
        </div>
          </div>
        </main>
      </div>
      {designOutlineDialogOpen && (
        <div
          className="settings-overlay"
          onClick={handleCloseDesignOutlineDialog}
        >
          <div
            className="settings-dialog design-outline-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="settings-dialog-header">
              <h3>Design this outline</h3>
              <button
                type="button"
                className="settings-dialog-close"
                onClick={handleCloseDesignOutlineDialog}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="settings-dialog-body">
              <div className="settings-tabs design-outline-tabs">
                <button
                  type="button"
                  className={`settings-tab ${designOutlineTab === 'logos' ? 'active' : ''}`}
                  onClick={() => setDesignOutlineTab('logos')}
                >
                  Logos
                </button>
                <button
                  type="button"
                  className={`settings-tab ${designOutlineTab === 'advanced' ? 'active' : ''}`}
                  onClick={() => setDesignOutlineTab('advanced')}
                >
                  Advanced
                </button>
              </div>
              {designOutlineTab === 'logos' && (
                <>
              <div className="design-outline-add-logos-row">
                <label htmlFor="design-outline-add-logos-toggle" className="settings-toggle-label">
                  Add logos to slides
                </label>
                <button
                  type="button"
                  role="switch"
                  id="design-outline-add-logos-toggle"
                  aria-checked={designOutlineAddLogosToSlides}
                  className={`settings-toggle ${designOutlineAddLogosToSlides ? 'on' : 'off'}`}
                  onClick={() => setDesignOutlineAddLogosToSlides((v) => !v)}
                >
                  <span className="settings-toggle-slider" />
                </button>
              </div>
              <p className="design-outline-dialog-desc">
                Optional: upload an image or paste a logo URL. Target logo extracts a color palette for design. Logos are only added when the toggle above is on.
              </p>
              <div className="settings-field">
                <label htmlFor="design-outline-my-logo-upload" className="settings-toggle-label">
                  Your company logo
                </label>
                <div className="design-outline-upload-row">
                  <input
                    ref={designOutlineMyLogoInputRef}
                    id="design-outline-my-logo-upload"
                    type="file"
                    accept="image/*"
                    className="input-file-hidden"
                    onChange={(e) => handleDesignOutlineLogoChange('my', e)}
                  />
                  <label htmlFor="design-outline-my-logo-upload" className="settings-upload-btn">
                    Upload image
                  </label>
                  <span className="design-outline-or"> or </span>
                  <input
                    type="url"
                    className="settings-input design-outline-url-input"
                    placeholder="Paste image URL (https://...)"
                    value={designOutlineMyLogoUrl}
                    onChange={(e) => {
                      setDesignOutlineMyLogoUrl(e.target.value);
                      const v = (e.target.value || '').trim();
                      if (v && (v.startsWith('http://') || v.startsWith('https://'))) {
                        setDesignOutlineMyLogoPreview(v);
                      } else if (!v) {
                        setDesignOutlineMyLogoPreview(null);
                      }
                    }}
                  />
                </div>
                {designOutlineMyLogoPreview && (
                  <div className="design-outline-preview-row">
                    <img
                      src={designOutlineMyLogoPreview}
                      alt="Logo preview"
                      className="design-outline-logo-preview"
                    />
                    <button
                      type="button"
                      className="design-outline-clear-btn"
                      onClick={() => handleClearDesignOutlineLogo('my')}
                      aria-label="Remove your logo"
                    >
                      ×
                    </button>
                  </div>
                )}
                <div className="design-outline-corner-row">
                  <span className="design-outline-corner-label">Corner</span>
                  <select
                    className="settings-select design-outline-corner-select"
                    value={designOutlineMyCorner}
                    onChange={(e) => setDesignOutlineMyCorner(e.target.value)}
                  >
                    <option value="top_left">Top left</option>
                    <option value="top_right">Top right</option>
                    <option value="bottom_left">Bottom left</option>
                    <option value="bottom_right">Bottom right</option>
                  </select>
                </div>
              </div>
              <div className="settings-field">
                <label htmlFor="design-outline-target-logo-upload" className="settings-toggle-label">
                  Target company logo
                </label>
                <div className="design-outline-upload-row">
                  <input
                    ref={designOutlineTargetLogoInputRef}
                    id="design-outline-target-logo-upload"
                    type="file"
                    accept="image/*"
                    className="input-file-hidden"
                    onChange={(e) => handleDesignOutlineLogoChange('target', e)}
                  />
                  <label htmlFor="design-outline-target-logo-upload" className="settings-upload-btn">
                    Upload image
                  </label>
                  <span className="design-outline-or"> or </span>
                  <input
                    type="url"
                    className="settings-input design-outline-url-input"
                    placeholder="Paste image URL (https://...)"
                    value={designOutlineTargetLogoUrl}
                    onChange={(e) => {
                      setDesignOutlineTargetLogoUrl(e.target.value);
                      const v = (e.target.value || '').trim();
                      if (v && (v.startsWith('http://') || v.startsWith('https://'))) {
                        setDesignOutlineTargetLogoPreview(v);
                      } else if (!v) {
                        setDesignOutlineTargetLogoPreview(null);
                      }
                    }}
                  />
                </div>
                {designOutlineTargetLogoPreview && (
                  <div className="design-outline-preview-row">
                    <img
                      src={designOutlineTargetLogoPreview}
                      alt="Target logo preview"
                      className="design-outline-logo-preview"
                    />
                    <button
                      type="button"
                      className="design-outline-clear-btn"
                      onClick={() => handleClearDesignOutlineLogo('target')}
                      aria-label="Remove target logo"
                    >
                      ×
                    </button>
                  </div>
                )}
                <div className="design-outline-corner-row">
                  <span className="design-outline-corner-label">Corner</span>
                  <select
                    className="settings-select design-outline-corner-select"
                    value={designOutlineTargetCorner}
                    onChange={(e) => setDesignOutlineTargetCorner(e.target.value)}
                  >
                    <option value="top_left">Top left</option>
                    <option value="top_right">Top right</option>
                    <option value="bottom_left">Bottom left</option>
                    <option value="bottom_right">Bottom right</option>
                  </select>
                </div>
              </div>
              {designOutlineExtracting && (
                <p className="design-outline-extracting">Extracting colors…</p>
              )}
              {designOutlineExtracted && !designOutlineExtracting && (
                <div className="design-outline-colors">
                  <div className="design-outline-color-group">
                    <span className="design-outline-color-label">Dominant</span>
                    <div className="design-outline-swatch-wrap">
                      <span
                        className="design-outline-swatch"
                        style={{ backgroundColor: designOutlineExtracted.dominant.hex }}
                        title={designOutlineExtracted.dominant.hex}
                      />
                      <span className="design-outline-hex">{designOutlineExtracted.dominant.hex}</span>
                    </div>
                  </div>
                  <div className="design-outline-color-group">
                    <span className="design-outline-color-label">Palette</span>
                    <div className="design-outline-palette">
                      {designOutlineExtracted.palette.map((c, i) => (
                        <span
                          key={i}
                          className="design-outline-swatch"
                          style={{ backgroundColor: c.hex }}
                          title={c.hex}
                        />
                      ))}
                    </div>
                    <div className="design-outline-palette-hexes">
                      {designOutlineExtracted.palette.map((c, i) => (
                        <span key={i} className="design-outline-hex-small">{c.hex}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
                </>
              )}
              {designOutlineTab === 'advanced' && (
                <div className="design-outline-advanced">
                  <p className="design-outline-dialog-desc">
                    These settings control deterministic placement. Units are EMU (Slides internal units).
                    Defaults: width=600000, height=600000, margin=250000.
                  </p>
                  <div className="design-outline-advanced-grid">
                    <div className="design-outline-advanced-card">
                      <div className="design-outline-color-label">Your logo</div>
                      <div className="design-outline-advanced-row">
                        <label className="design-outline-advanced-label">Width (EMU)</label>
                        <input className="settings-input" type="number" value={designOutlineMyWidthEmu} onChange={(e) => setDesignOutlineMyWidthEmu(Number(e.target.value))} />
                      </div>
                      <div className="design-outline-advanced-row">
                        <label className="design-outline-advanced-label">Height (EMU)</label>
                        <input className="settings-input" type="number" value={designOutlineMyHeightEmu} onChange={(e) => setDesignOutlineMyHeightEmu(Number(e.target.value))} />
                      </div>
                      <div className="design-outline-advanced-row">
                        <label className="design-outline-advanced-label">Margin (EMU)</label>
                        <input className="settings-input" type="number" value={designOutlineMyMarginEmu} onChange={(e) => setDesignOutlineMyMarginEmu(Number(e.target.value))} />
                      </div>
                    </div>
                    <div className="design-outline-advanced-card">
                      <div className="design-outline-color-label">Target logo</div>
                      <div className="design-outline-advanced-row">
                        <label className="design-outline-advanced-label">Width (EMU)</label>
                        <input className="settings-input" type="number" value={designOutlineTargetWidthEmu} onChange={(e) => setDesignOutlineTargetWidthEmu(Number(e.target.value))} />
                      </div>
                      <div className="design-outline-advanced-row">
                        <label className="design-outline-advanced-label">Height (EMU)</label>
                        <input className="settings-input" type="number" value={designOutlineTargetHeightEmu} onChange={(e) => setDesignOutlineTargetHeightEmu(Number(e.target.value))} />
                      </div>
                      <div className="design-outline-advanced-row">
                        <label className="design-outline-advanced-label">Margin (EMU)</label>
                        <input className="settings-input" type="number" value={designOutlineTargetMarginEmu} onChange={(e) => setDesignOutlineTargetMarginEmu(Number(e.target.value))} />
                      </div>
                    </div>
                  </div>
                  <div className="design-outline-advanced-actions">
                    <button
                      type="button"
                      className="edit-outline-cancel-btn"
                      onClick={() => {
                        setDesignOutlineMyWidthEmu(600000);
                        setDesignOutlineMyHeightEmu(600000);
                        setDesignOutlineMyMarginEmu(250000);
                        setDesignOutlineTargetWidthEmu(600000);
                        setDesignOutlineTargetHeightEmu(600000);
                        setDesignOutlineTargetMarginEmu(250000);
                      }}
                    >
                      Restore defaults
                    </button>
                    <button
                      type="button"
                      className="settings-upload-btn"
                      onClick={async () => {
                        setDesignOutlineSavingBranding(true);
                        try {
                          await saveBrandingLogosAndPrefs();
                        } catch (err) {
                          alert(err.message || 'Failed to save settings');
                        } finally {
                          setDesignOutlineSavingBranding(false);
                        }
                      }}
                      disabled={designOutlineSavingBranding}
                    >
                      {designOutlineSavingBranding ? 'Saving…' : 'Save settings'}
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div className="settings-dialog-footer">
              <button
                type="button"
                className="settings-upload-btn"
                onClick={handleDesignOutlineConfirm}
                disabled={designOutlineSavingBranding}
              >
                {designOutlineSavingBranding ? 'Saving…' : (designOutlineExtracted ? 'Design with these colors' : 'Design')}
              </button>
              <button
                type="button"
                className="edit-outline-cancel-btn"
                onClick={handleCloseDesignOutlineDialog}
                disabled={designOutlineSavingBranding}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      {slideOutlineDialogOpen && (
        <div
          className="settings-overlay"
          onClick={() => setSlideOutlineDialogOpen(false)}
        >
          <div
            className="settings-dialog slide-outline-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="settings-dialog-header">
              <h3>Slide outline template</h3>
              <button
                type="button"
                className="settings-dialog-close"
                onClick={() => setSlideOutlineDialogOpen(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="settings-dialog-body slide-outline-dialog-body">
              <div className="slide-outline-saved-list">
                <div className="slide-outline-saved-header">Saved outlines</div>
                <button
                  type="button"
                  className="slide-outline-new-btn"
                  onClick={() => {
                    setSlideOutlineName('');
                    setSlideOutlineSlides([{ title: '', guidance: '' }]);
                    setEditingSlideOutlineId(null);
                    setLoadedSlideOutlineSnapshot(null);
                    setSlideOutlineSaveStatus(null);
                  }}
                >
                  + New outline
                </button>
                {savedSlideOutlines.length === 0 ? (
                  <div className="slide-outline-saved-empty">No saved outlines yet</div>
                ) : (
                  <ul className="slide-outline-saved-ul">
                    {savedSlideOutlines.map((outline) => (
                      <li
                        key={outline.id}
                        role="button"
                        tabIndex={0}
                        className={`slide-outline-saved-item ${editingSlideOutlineId === outline.id ? 'selected' : ''}`}
                        onClick={() => handleSelectSlideOutline(outline)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSelectSlideOutline(outline)}
                      >
                        <span className="slide-outline-saved-name" title={outline.name}>
                          {outline.name}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="slide-outline-form">
                <div className="slide-outline-form-header">
                  <h4 className="slide-outline-form-title">
                    {editingSlideOutlineId ? 'Edit outline' : 'New outline'}
                  </h4>
                  {editingSlideOutlineId && (
                    <button
                      type="button"
                      className="slide-outline-delete-btn-inline"
                      onClick={handleDeleteSlideOutline}
                      disabled={deletingSlideOutlineId === editingSlideOutlineId}
                    >
                      {deletingSlideOutlineId === editingSlideOutlineId ? 'Deleting…' : 'Delete'}
                    </button>
                  )}
                </div>
                <div className="settings-field">
                  <label
                    htmlFor="slide-outline-name"
                    className="settings-toggle-label"
                  >
                    Presentation name
                  </label>
                  <input
                    id="slide-outline-name"
                    type="text"
                    className="settings-input"
                    placeholder="e.g. Pitch, Investor presentation"
                    value={slideOutlineName}
                    onChange={(e) => setSlideOutlineName(e.target.value)}
                  />
                </div>
                <div className="settings-field">
                  <div className="settings-toggle-label">
                    Slides (title and guidance)
                  </div>
                  <div className="slide-outline-rows">
                    {slideOutlineSlides.map((row, idx) => (
                      <div
                        key={idx}
                        className="slide-outline-row"
                      >
                        <input
                          type="text"
                          className="settings-input slide-outline-title-input"
                          placeholder={`Slide ${idx + 1} title`}
                          value={row.title}
                          onChange={(e) =>
                            handleUpdateSlideRow(
                              idx,
                              'title',
                              e.target.value,
                            )
                          }
                        />
                        <textarea
                          className="settings-input slide-outline-guidance-input"
                          placeholder="Guidance / what to fill in this slide"
                          rows={2}
                          value={row.guidance}
                          onChange={(e) =>
                            handleUpdateSlideRow(
                              idx,
                              'guidance',
                              e.target.value,
                            )
                          }
                        />
                        {slideOutlineSlides.length > 1 && (
                          <button
                            type="button"
                            className="slide-outline-remove-btn"
                            onClick={() => handleRemoveSlideRow(idx)}
                            aria-label="Remove slide"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      className="slide-outline-add-btn"
                      onClick={handleAddSlideRow}
                    >
                      + Add slide
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className="settings-dialog-footer slide-outline-footer">
              {isSlideOutlineDirty && (
                <span className="slide-outline-dirty-msg">
                  {slideOutlineSaveStatus === 'saving'
                    ? 'Saving…'
                    : slideOutlineSaveStatus === 'saved'
                      ? 'Saved'
                      : 'Unsaved changes'}
                </span>
              )}
              <div className="slide-outline-footer-actions">
                <button
                  type="button"
                  className="settings-upload-btn"
                  onClick={handleSaveSlideOutline}
                  disabled={!isSlideOutlineDirty || slideOutlineSaveStatus === 'saving'}
                >
                  {slideOutlineSaveStatus === 'saving' ? 'Saving…' : 'Save'}
                </button>
                <button
                  type="button"
                  className="edit-outline-cancel-btn"
                  onClick={() => setSlideOutlineDialogOpen(false)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatPage;
