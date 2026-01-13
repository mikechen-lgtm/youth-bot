import { createRoot } from "react-dom/client";
import { AdminPage } from "./pages/AdminPage";
import "./index.css";

createRoot(document.getElementById("admin-root")!).render(<AdminPage />);
