import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Spinner } from '@fluentui/react-components';
import './DrivePage.css';

const API_BASE = '/api';

// Fallback icons by mime type when iconLink is missing
const MIME_ICONS = {
  'presentation': '📊',
  'spreadsheet': '📗',
  'document': '📝',
  'folder': '📁',
  'pdf': '📕',
  'image': '🖼️',
  'video': '🎬',
  'audio': '🎵',
};

function getFileIcon(file) {
  const m = (file.mimeType || '').toLowerCase();
  if (m.includes('presentation')) return MIME_ICONS.presentation;
  if (m.includes('spreadsheet')) return MIME_ICONS.spreadsheet;
  if (m.includes('document')) return MIME_ICONS.document;
  if (m.includes('folder')) return MIME_ICONS.folder;
  if (m.includes('pdf')) return MIME_ICONS.pdf;
  if (m.includes('image')) return MIME_ICONS.image;
  if (m.includes('video')) return MIME_ICONS.video;
  if (m.includes('audio')) return MIME_ICONS.audio;
  return '📄';
}

// iconLink = file type icon image URL (from Google). webViewLink = open file in browser.

function DrivePage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [failedIconIds, setFailedIconIds] = useState(new Set());

  const fetchFiles = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/drive/files?page_size=50`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to load files');
      setFiles(data.files || []);
    } catch (err) {
      setError(err.message);
      setFiles([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
      setFailedIconIds(new Set());
    }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { dateStyle: 'medium' });
  };

  return (
    <div className="drive-page">
      <header className="drive-header">
        <div className="drive-header-content">
          <span className="drive-logo">G</span>
          <h1>Google Drive</h1>
          <Link to="/chat" className="chat-link">Open Slides Assistant</Link>
          <Link to="/sheets-chat" className="chat-link">Open Sheets Assistant</Link>
        </div>
      </header>

      <main className="drive-main">
        <div className="drive-toolbar">
          <h2>My Drive</h2>
          <Button
            className="drive-refresh-btn"
            onClick={() => fetchFiles(true)}
            disabled={loading || refreshing}
            title="Refresh from Drive"
            appearance="primary"
          >
            {refreshing ? (
              <Spinner size="extra-tiny" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M23 4v6h-6M1 20v-6h6" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            )}
            Refresh
          </Button>
        </div>

        {loading && !refreshing ? (
          <div className="drive-loading">
            <Spinner size="large" />
            <p>Loading files...</p>
          </div>
        ) : error ? (
          <div className="drive-error">
            <p>{error}</p>
            <p className="drive-error-hint">Ensure Drive API is enabled and run: gws auth login -s slides,drive</p>
          </div>
        ) : files.length === 0 ? (
          <div className="drive-empty">
            <p>No files found</p>
          </div>
        ) : (
          <div className="drive-list">
            <div className="drive-list-header">
              <span className="drive-list-col-icon" />
              <span className="drive-list-col-name">Name</span>
              <span className="drive-list-col-date">Modified</span>
              <span className="drive-list-col-action" />
            </div>
            {files.map((file) => {
              const fallbackIcon = getFileIcon(file);
              const iconLink = file.iconLink;
              const useIconImg = iconLink && !failedIconIds.has(file.id);
              const isSlides = (file.mimeType || '').includes('presentation');
              return (
                <div key={file.id} className="drive-list-row">
                  <a
                    href={file.webViewLink || file.webContentLink || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="drive-list-row-link"
                    title={`${file.name} (click to open)`}
                  >
                    <span className="drive-list-col-icon">
                      {useIconImg ? (
                        <img
                          src={iconLink}
                          alt=""
                          className="drive-file-icon-img"
                          onError={() => setFailedIconIds((prev) => new Set(prev).add(file.id))}
                        />
                      ) : (
                        <span className="drive-file-emoji">{fallbackIcon}</span>
                      )}
                    </span>
                    <span className="drive-list-col-name" title={file.name}>{file.name}</span>
                    <span className="drive-list-col-date">{formatDate(file.modifiedTime)}</span>
                  </a>
                  <span className="drive-list-col-action">
                    {isSlides && (
                      <Button
                        type="button"
                        className="drive-edit-ai-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/chat?fileId=${file.id}&fileName=${encodeURIComponent(file.name)}&mimeType=${file.mimeType || ''}`);
                        }}
                        title="Edit with AI Assistant"
                        appearance="outline"
                      >
                        Edit with AI
                      </Button>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

export default DrivePage;
