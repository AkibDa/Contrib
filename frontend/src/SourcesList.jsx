import React, { useState } from 'react';
import {
  FileCode,
  FileText,
  Database,
  File,
  Copy,
  Check,
  ExternalLink,
} from 'lucide-react';

function FileIcon({ filename, size = 14, color = '#00ff41' }) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (
    [
      'py', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'scss',
      'json', 'yaml', 'yml', 'c', 'cpp', 'rs', 'go', 'java',
      'rb', 'php', 'sh', 'sql', 'toml',
    ].includes(ext)
  ) {
    return <FileCode size={size} color={color} />;
  }
  if (['md', 'txt', 'rst', 'log', 'env'].includes(ext)) {
    return <FileText size={size} color={color} />;
  }
  if (
    [
      'cache', 'db', 'sqlite', 'csv', 'parquet', 'dat', 'bin',
      'pt', 'pth', 'onnx', 'pkl',
    ].includes(ext)
  ) {
    return <Database size={size} color={color} />;
  }
  return <File size={size} color={color} />;
}

function SourceChip({ fileItem, repoUrl }) {
  const [copied, setCopied] = useState(false);

  // Normalize string vs future structured object
  const filePath = typeof fileItem === 'string' ? fileItem : fileItem?.path || '';
  const sections = fileItem?.sections || fileItem?.functions || null;
  const relevance = fileItem?.relevance || null;

  if (!filePath) return null;

  const normalized = filePath.replace(/\\/g, '/');
  const pathParts = normalized.split('/');
  const fileName = pathParts.pop() || normalized;
  const dirPath = pathParts.length > 0 ? pathParts.join('/') + '/' : './';

  // Generate GitHub link if repoUrl is available
  let githubUrl = null;
  if (repoUrl && repoUrl.startsWith('http')) {
    const cleanRepo = repoUrl.replace(/\/+$/, '').replace(/\.git$/, '');
    githubUrl = `${cleanRepo}/blob/HEAD/${normalized}`;
  }

  const handleCopy = async e => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(normalized);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch (err) {
      console.warn('Copy path failed', err);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '9px 13px',
        background: 'rgba(0, 16, 5, 0.7)',
        border: '1px solid rgba(0, 255, 65, 0.16)',
        borderRadius: 4,
        fontFamily: "'JetBrains Mono', monospace",
        transition: 'all 0.2s ease',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'rgba(0, 255, 65, 0.4)';
        e.currentTarget.style.background = 'rgba(0, 24, 7, 0.85)';
        e.currentTarget.style.boxShadow = '0 0 12px rgba(0, 255, 65, 0.12)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'rgba(0, 255, 65, 0.16)';
        e.currentTarget.style.background = 'rgba(0, 16, 5, 0.7)';
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.3)';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 3,
            background: 'rgba(0, 255, 65, 0.08)',
            border: '1px solid rgba(0, 255, 65, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <FileIcon filename={fileName} size={14} color="#00ff41" />
        </div>

        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: '#00ff41',
              wordBreak: 'break-all',
              lineHeight: 1.3,
            }}
          >
            {fileName}
          </div>
          <div
            style={{
              fontSize: 10,
              color: '#00701a',
              wordBreak: 'break-all',
              marginTop: 2,
              letterSpacing: 0.3,
            }}
          >
            {dirPath}
          </div>

          {/* Optional sections or relevance badges if provided in future */}
          {relevance && (
            <span
              style={{
                display: 'inline-block',
                marginTop: 4,
                fontSize: 9,
                color: '#00b432',
                background: 'rgba(0, 255, 65, 0.08)',
                padding: '1px 5px',
                borderRadius: 2,
              }}
            >
              relevance: {relevance}
            </span>
          )}
          {sections && Array.isArray(sections) && sections.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
              {sections.map((sec, idx) => (
                <span
                  key={idx}
                  style={{
                    fontSize: 9,
                    color: '#009922',
                    background: 'rgba(0, 100, 30, 0.15)',
                    padding: '1px 5px',
                    borderRadius: 2,
                  }}
                >
                  {sec}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <button
          type="button"
          onClick={handleCopy}
          title="Copy file path"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '4px 7px',
            background: copied ? 'rgba(0, 255, 65, 0.15)' : 'rgba(0, 255, 65, 0.04)',
            border: `1px solid ${copied ? 'rgba(0, 255, 65, 0.5)' : 'rgba(0, 255, 65, 0.18)'}`,
            borderRadius: 3,
            color: copied ? '#00ff41' : '#009922',
            fontSize: 10,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={e => {
            if (!copied) {
              e.currentTarget.style.borderColor = 'rgba(0, 255, 65, 0.4)';
              e.currentTarget.style.color = '#00ff41';
            }
          }}
          onMouseLeave={e => {
            if (!copied) {
              e.currentTarget.style.borderColor = 'rgba(0, 255, 65, 0.18)';
              e.currentTarget.style.color = '#009922';
            }
          }}
        >
          {copied ? <Check size={11} strokeWidth={2.5} /> : <Copy size={11} />}
          <span style={{ fontSize: 9 }}>{copied ? 'COPIED' : 'COPY'}</span>
        </button>

        {githubUrl && (
          <a
            href={githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="View file on GitHub"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 7px',
              background: 'rgba(0, 255, 65, 0.04)',
              border: '1px solid rgba(0, 255, 65, 0.18)',
              borderRadius: 3,
              color: '#00aa28',
              fontSize: 10,
              textDecoration: 'none',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(0, 255, 65, 0.4)';
              e.currentTarget.style.color = '#00ff41';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'rgba(0, 255, 65, 0.18)';
              e.currentTarget.style.color = '#00aa28';
            }}
          >
            <ExternalLink size={11} />
            <span style={{ fontSize: 9 }}>VIEW</span>
          </a>
        )}
      </div>
    </div>
  );
}

export default function SourcesList({ files, repoUrl }) {
  if (!files || !Array.isArray(files) || files.length === 0) {
    return (
      <div
        style={{
          padding: '10px 12px',
          color: '#00701a',
          fontSize: 11,
          fontFamily: "'JetBrains Mono', monospace",
          fontStyle: 'italic',
        }}
      >
        No source files referenced for this response.
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      {files.map((fileItem, idx) => (
        <SourceChip
          key={typeof fileItem === 'string' ? `${fileItem}-${idx}` : `${fileItem?.path}-${idx}`}
          fileItem={fileItem}
          repoUrl={repoUrl}
        />
      ))}
    </div>
  );
}
