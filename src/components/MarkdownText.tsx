import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownTextProps {
  children: string;
  className?: string;
  style?: React.CSSProperties;
}

export function MarkdownText({ children, className, style }: MarkdownTextProps) {
  // 清理多餘的連續空行（2個以上空行 → 1個空行）
  const cleanedContent = children
    .replace(/\n{2,}/g, '\n\n')           // 所有多餘空行壓縮為單一空行
    .replace(/：\n\n/g, '：\n');          // 冒號後的空行移除（讓列表更緊湊）

  return (
    <div
      className={className}
      style={{
        ...style,
        wordBreak: 'break-word',
        overflowWrap: 'break-word'
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 链接样式 - 表單連結顯示為按鈕樣式
          a: ({ node, children, ...props }) => {
            const linkText = String(children || '');
            const isFormLink = linkText.includes('表單') || linkText.includes('填寫') || linkText.includes('回饋');

            if (isFormLink) {
              return (
                <a
                  {...props}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block mt-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg cursor-pointer transition-colors no-underline font-medium"
                  onClick={(e) => e.stopPropagation()}
                >
                  {children}
                </a>
              );
            }

            return (
              <a
                {...props}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:text-blue-700 underline cursor-pointer"
                style={{ wordBreak: 'break-all', overflowWrap: 'break-word' }}
                onClick={(e) => e.stopPropagation()}
              >
                {children}
              </a>
            );
          },
          // 代码块样式
          code: ({ node, inline, className, children, ...props }) => {
            if (inline) {
              return (
                <code
                  className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm font-mono"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <code
                className={`block bg-gray-100 dark:bg-gray-800 p-3 rounded-lg overflow-x-auto font-mono text-sm ${className || ''}`}
                {...props}
              >
                {children}
              </code>
            );
          },
          // 预格式化文本块
          pre: ({ node, ...props }) => (
            <pre className="my-2 overflow-x-auto" {...props} />
          ),
          // 标题样式
          h1: ({ node, ...props }) => (
            <h1 className="text-2xl font-bold mt-4 mb-2" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="text-xl font-bold mt-3 mb-2" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="text-lg font-bold mt-2 mb-1" {...props} />
          ),
          h4: ({ node, ...props }) => (
            <h4 className="text-base font-bold mt-2 mb-1" {...props} />
          ),
          h5: ({ node, ...props }) => (
            <h5 className="text-sm font-bold mt-1 mb-1" {...props} />
          ),
          h6: ({ node, ...props }) => (
            <h6 className="text-xs font-bold mt-1 mb-1" {...props} />
          ),
          // 列表样式 - 使用 [&>p] 選擇器移除列表項內段落的多餘間距
          ul: ({ node, ...props }) => (
            <ul className="list-disc list-inside my-2 space-y-1" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="list-decimal list-inside my-2 space-y-1" {...props} />
          ),
          li: ({ node, ...props }) => (
            <li className="ml-4 [&>p]:my-0 [&>p:first-child]:mt-0 [&>p:last-child]:mb-0" {...props} />
          ),
          // 引用块样式
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 my-2 italic text-gray-700 dark:text-gray-300"
              {...props}
            />
          ),
          // 表格样式
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto my-2">
              <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-600" {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => (
            <thead className="bg-gray-100 dark:bg-gray-800" {...props} />
          ),
          tbody: ({ node, ...props }) => (
            <tbody {...props} />
          ),
          tr: ({ node, ...props }) => (
            <tr className="border-b border-gray-300 dark:border-gray-600" {...props} />
          ),
          th: ({ node, ...props }) => (
            <th className="border border-gray-300 dark:border-gray-600 px-4 py-2 text-left font-semibold" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="border border-gray-300 dark:border-gray-600 px-4 py-2" {...props} />
          ),
          // 水平线样式
          hr: ({ node, ...props }) => (
            <hr className="my-4 border-gray-300 dark:border-gray-600" {...props} />
          ),
          // 段落样式
          p: ({ node, ...props }) => (
            <p className="my-1" {...props} />
          ),
          // 强调文本
          strong: ({ node, ...props }) => (
            <strong className="font-bold" {...props} />
          ),
          em: ({ node, ...props }) => (
            <em className="italic" {...props} />
          ),
          // 圖片樣式 - 響應式處理
          img: ({ node, ...props }) => (
            <img
              {...props}
              className="max-w-full h-auto rounded-lg my-2"
              style={{
                maxWidth: '100%',
                height: 'auto',
                objectFit: 'contain'
              }}
              loading="lazy"
            />
          ),
        }}
      >
        {cleanedContent}
      </ReactMarkdown>
    </div>
  );
}