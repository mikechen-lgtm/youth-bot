export interface ChatMessage {
  message: string;
  session_id?: string;
  template_id?: string;
}

export interface SourceItem {
  text: string;
}

export interface StreamResponse {
  type: "text" | "end" | "error" | "sources" | "session";
  content: string | SourceItem[];
  session_id: string;
}

const CSRF_TOKEN_ENDPOINT = "/api/csrf-token";

function getDefaultBaseURL(): string {
  const fromEnv = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (!fromEnv) {
    return "";
  }
  return fromEnv.replace(/\/+$/, "");
}

const DEFAULT_BASE_URL = getDefaultBaseURL();

export class ChatAPI {
  private baseURL: string;
  private sessionId: string | null = null;
  private csrfToken: string | null = null;

  constructor(baseURL: string = DEFAULT_BASE_URL) {
    this.baseURL = baseURL;
  }

  private resolveURL(path: string): string {
    if (!this.baseURL) {
      return path;
    }
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseURL}${normalizedPath}`;
  }

  /**
   * Fetch CSRF token from the server if not already cached.
   */
  private async ensureCSRFToken(): Promise<string> {
    if (this.csrfToken) {
      return this.csrfToken;
    }

    const response = await fetch(this.resolveURL(CSRF_TOKEN_ENDPOINT), {
      method: "GET",
      credentials: "include",
    });

    if (!response.ok) {
      const errorMessage = `CSRF token request failed with status ${response.status}`;
      console.error("[ChatAPI]", errorMessage);
      throw new Error(errorMessage);
    }

    const data = await response.json();
    if (!data.success || !data.csrf_token) {
      const errorMessage = "Server returned invalid CSRF token response";
      console.error("[ChatAPI]", errorMessage);
      throw new Error(errorMessage);
    }

    this.csrfToken = data.csrf_token;
    return this.csrfToken;
  }

  async sendMessage(
    message: string,
    templateId?: string,
    onChunk?: (chunk: string) => void,
    onComplete?: (fullMessage: string) => void,
    onError?: (error: string) => void,
    onSources?: (sources: SourceItem[]) => void
  ): Promise<string> {
    const payload: ChatMessage = {
      message,
      session_id: this.sessionId || undefined,
      template_id: templateId || undefined,
    };

    try {
      // Ensure we have a CSRF token before sending the request
      const csrfToken = await this.ensureCSRFToken();

      const response = await fetch(this.resolveURL("/api/chat"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText || ""}`.trim());
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("無法讀取伺服器回應 (Missing readable stream)");
      }

      const decoder = new TextDecoder();
      let fullMessage = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line.startsWith("data:")) {
            continue;
          }

          try {
            const data = JSON.parse(line.slice(5).trim()) as StreamResponse;

            if (data.session_id && !this.sessionId) {
              this.sessionId = data.session_id;
            }

            if (data.type === "text") {
              fullMessage += data.content as string;
              onChunk?.(data.content as string);
            } else if (data.type === "sources") {
              onSources?.(data.content as SourceItem[]);
            } else if (data.type === "end") {
              // 伺服器在 end 事件中帶回格式化後的完整文字，優先使用
              const finalMessage = (data.content as string) || fullMessage;
              onComplete?.(finalMessage);
              return finalMessage;
            } else if (data.type === "error") {
              onError?.(data.content as string);
              throw new Error(data.content as string);
            }
          } catch (parseError) {
            console.warn("Failed to parse SSE payload:", line, parseError);
          }
        }
      }

      return fullMessage;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "未知錯誤，請稍後再試";
      onError?.(errorMessage);
      throw error instanceof Error ? error : new Error(String(error));
    }
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  clearSession(): void {
    this.sessionId = null;
    this.csrfToken = null;
  }
}

export const chatAPI = new ChatAPI();
