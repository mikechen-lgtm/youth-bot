import { Avatar, AvatarFallback } from "./ui/avatar";
import { Card } from "./ui/card";
import { Bot } from "lucide-react";
import { ChatFAQSection } from "./ChatFAQSection";
import { HOTEL_PRIMARY, HOTEL_PRIMARY_SOFT } from "../styles/hotelTheme";

interface ChatWelcomeMessageProps {
  timestamp: Date;
  onQuestionClick: (question: string) => void;
}

export function ChatWelcomeMessage({ timestamp, onQuestionClick }: ChatWelcomeMessageProps) {
  return (
    <div className="flex gap-3 mb-4 justify-start">
      <Avatar className="w-8 h-8 mt-1">
        <AvatarFallback className="text-white" style={{ backgroundColor: HOTEL_PRIMARY }}>
          <Bot className="w-4 h-4" />
        </AvatarFallback>
      </Avatar>

      <div className="max-w-[85%]">
        <Card
          className="p-4 bg-card border border-slate-200"
          style={{ backgroundColor: HOTEL_PRIMARY_SOFT }}
        >
          <p className="whitespace-pre-wrap mb-4 select-text cursor-text text-slate-700 leading-relaxed">
            您好，歡迎使用桃園市青年事務局智慧客服系統。

我可以協助您了解：
• 青年創業與就業輔導資源
• 青年公共參與及志願服務
• 各項青年培力課程與活動
• 青年政策與補助方案

請問有什麼可以為您服務的？
          </p>
          <ChatFAQSection onQuestionClick={onQuestionClick} />
        </Card>
        <p className="text-xs text-muted-foreground mt-1.5 text-left select-text cursor-text">
          {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  );
}
