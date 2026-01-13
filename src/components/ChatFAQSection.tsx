import { Briefcase, Users, GraduationCap, FileText } from "lucide-react";

interface ChatFAQSectionProps {
  onQuestionClick: (question: string) => void;
}

export function ChatFAQSection({ onQuestionClick }: ChatFAQSectionProps) {
  const topicCards = [
    {
      id: "career",
      label: "就業創業",
      icon: Briefcase,
      question: "青年局有哪些創業輔導和就業支援的資源？",
      description: "創業輔導、職涯發展"
    },
    {
      id: "participation",
      label: "公共參與",
      icon: Users,
      question: "什麼是輕參政？青年可以如何參與公共事務？",
      description: "志工服務、青年議會"
    },
    {
      id: "learning",
      label: "培力課程",
      icon: GraduationCap,
      question: "有哪些青年培力課程或學習活動可以參加？",
      description: "技能培訓、交流活動"
    },
    {
      id: "policy",
      label: "政策資訊",
      icon: FileText,
      question: "請介紹桃園市青年事務局的主要業務和服務",
      description: "補助方案、政策說明"
    }
  ];

  return (
    <div className="border-t border-slate-200 pt-3 mt-1">
      <h4 className="text-sm font-medium mb-3 text-slate-600 select-text cursor-text">
        常見問題
      </h4>
      <div className="grid grid-cols-2 gap-2">
        {topicCards.map((topic) => {
          const IconComponent = topic.icon;
          return (
            <button
              key={topic.id}
              className="group flex flex-col items-center p-3 rounded-lg border border-slate-200 bg-white hover:border-[#1E5B8C] hover:bg-[#1E5B8C]/5 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[#1E5B8C] focus:ring-offset-1"
              onClick={() => onQuestionClick(topic.question)}
            >
              <div className="w-10 h-10 rounded-full bg-slate-100 group-hover:bg-[#1E5B8C]/10 flex items-center justify-center mb-2 transition-colors">
                <IconComponent className="w-5 h-5 text-slate-500 group-hover:text-[#1E5B8C] transition-colors" />
              </div>
              <span className="text-sm font-medium text-slate-700 group-hover:text-[#1E5B8C] transition-colors">
                {topic.label}
              </span>
              <span className="text-xs text-slate-400 mt-0.5">
                {topic.description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
