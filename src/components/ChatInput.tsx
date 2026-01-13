import { useState, useRef } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Send } from "lucide-react";
import { HOTEL_PRIMARY } from "../styles/hotelTheme";
import { useAuth } from "../contexts/AuthContext";

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  onLoginRequired?: () => void;
}

export function ChatInput({ onSendMessage, disabled = false, onLoginRequired }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { isAuthenticated, isLoading } = useAuth();

  const handleInteraction = () => {
    // Check if user needs to login when interacting with input
    console.log('[ChatInput] handleInteraction:', { isLoading, isAuthenticated, hasCallback: !!onLoginRequired });
    if (!isAuthenticated && onLoginRequired) {
      console.log('[ChatInput] Triggering login modal');
      onLoginRequired();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      onLoginRequired?.();
      return;
    }
    if (message.trim() && !disabled) {
      onSendMessage(message.trim());
      setMessage("");
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-3 bg-slate-50">
      <Input
        ref={inputRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onFocus={handleInteraction}
        onClick={handleInteraction}
        onKeyPress={handleKeyPress}
        placeholder={isAuthenticated ? "請輸入您的問題..." : "請先登入以開始對話..."}
        disabled={disabled}
        className="flex-1 border-slate-200 focus-visible:border-[#1E5B8C] focus-visible:ring-[#1E5B8C]/20 h-10 bg-white"
        autoComplete="off"
      />
      <Button
        type="submit"
        disabled={!message.trim() || disabled || !isAuthenticated}
        className="px-3 h-10 text-white border-0 bg-[#1E5B8C] hover:bg-[#134A73] transition-colors disabled:opacity-50"
        style={{
          backgroundColor: HOTEL_PRIMARY
        }}
      >
        <Send className="w-4 h-4" />
      </Button>
    </form>
  );
}
