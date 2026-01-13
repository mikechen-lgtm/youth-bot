import { useState } from "react";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Card } from "./ui/card";
import { Bot, User, ChevronDown, ChevronUp, FileText } from "lucide-react";
import { MarkdownText } from "./MarkdownText";
import { HOTEL_PRIMARY } from "../styles/hotelTheme";
import { SourceItem } from "../services/api";

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
            className="whitespace-pre-wrap select-text cursor-text"
            style={{ userSelect: 'text', WebkitUserSelect: 'text' }}
          >
            {message}
          </MarkdownText>

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
