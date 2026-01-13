import { FloatingChatbot } from "./components/FloatingChatbot";
import { AuthProvider } from "./contexts/AuthContext";

export default function App() {
  return (
    <AuthProvider>
      <FloatingChatbot />
    </AuthProvider>
  );
}
