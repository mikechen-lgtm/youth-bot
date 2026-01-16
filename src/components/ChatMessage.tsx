import { useState } from "react";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Card } from "./ui/card";
import { Bot, User, ChevronDown, ChevronUp, FileText } from "lucide-react";
import { MarkdownText } from "./MarkdownText";
import { HOTEL_PRIMARY } from "../styles/hotelTheme";
import { SourceItem } from "../services/api";

// 回饋表單 URL
const FEEDBACK_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeU_Ntx-uR3E6f9zLw6PBgbmdGXhRjQwMP-YzYIBgrBJ78Iyw/viewform";

// 無法回答的特徵關鍵字
const UNABLE_TO_ANSWER_KEYWORDS = [
  "未在我的資料庫中",
  "尚無足夠資訊",
  "無法回答",
  "找不到相關資訊",
  "資料庫中沒有",
  "超出知識庫範圍",
  "目前資料不足",
  "沒有相關資料",
  "無法提供",
  "不在我的知識範圍"
];

// 檢查訊息是否為「無法回答」的情況
function isUnableToAnswer(message: string): boolean {
  return UNABLE_TO_ANSWER_KEYWORDS.some(keyword => message.includes(keyword));
}

// 檢查訊息是否已包含表單連結（避免重複顯示）
function hasFormLink(message: string): boolean {
  return message.includes("表單") && (message.includes("http") || message.includes("填寫"));
}

interface ChatMessageProps {
  message: string;
  isUser: boolean;
  timestamp: Date;
  sources?: SourceItem[];
}

export function ChatMessage({ message, isUser, timestamp, sources }: ChatMessageProps) {
  const [showSources, setShowSources] = useState(false);

  return (
    <div className={`flex gap-3 mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <Avatar className="w-8 h-8 mt-1">
          <AvatarFallback className="text-white" style={{ backgroundColor: HOTEL_PRIMARY }}>
            <Bot className="w-4 h-4" />
          </AvatarFallback>
        </Avatar>
      )}

      <div className={`max-w-[80%] ${isUser ? 'order-first' : ''}`} style={{ userSelect: 'text', WebkitUserSelect: 'text', WebkitTouchCallout: 'default' }}>
        <Card className={`p-3 ${
          isUser
            ? 'text-white ml-auto border-0'
            : 'bg-card border'
        }`}
        style={{
          ...(isUser ? { backgroundColor: HOTEL_PRIMARY } : {}),
          userSelect: 'text',
          WebkitUserSelect: 'text',
          wordBreak: 'break-word',
          overflowWrap: 'break-word'
        }}>
          <MarkdownText
            className="select-text cursor-text"
            style={{ userSelect: 'text', WebkitUserSelect: 'text' }}
          >
            {message}
          </MarkdownText>

          {/* 無法回答時顯示回饋表單按鈕 */}
          {!isUser && isUnableToAnswer(message) && !hasFormLink(message) && (
            <div className="mt-3">
              <a
                href={FEEDBACK_FORM_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg cursor-pointer transition-colors no-underline font-medium text-sm"
              >
                📝 填寫問題回饋表單
              </a>
            </div>
          )}

          {/* Sources section for AI messages */}
          {!isUser && sources && sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50">
              <button
                onClick={() => setShowSources(!showSources)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <FileText className="w-3 h-3" />
                <span>參考來源 ({sources.length})</span>
                {showSources ? (
                  <ChevronUp className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                )}
              </button>

              {showSources && (
                <div className="mt-2 space-y-2">
                  {sources.map((source, index) => (
                    <div
                      key={index}
                      className="text-xs text-muted-foreground bg-muted/50 rounded p-2"
                      style={{ userSelect: 'text', WebkitUserSelect: 'text' }}
                    >
                      <span className="font-medium text-foreground/70">
                        [{index + 1}]
                      </span>{' '}
                      {source.text.length > 200
                        ? `${source.text.substring(0, 200)}...`
                        : source.text}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
        <p className={`text-xs text-muted-foreground mt-1 select-text cursor-text ${
          isUser ? 'text-right' : 'text-left'
        }`}
        style={{ userSelect: 'text', WebkitUserSelect: 'text' }}>
          {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>

      {isUser && (
        <Avatar className="w-8 h-8 mt-1">
          <AvatarFallback className="bg-secondary text-secondary-foreground">
            <User className="w-4 h-4" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
