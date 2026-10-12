import React from "react";
import { createRoot } from "react-dom/client";
import { IpsisChat } from "./IpsisChat.jsx";

const API = import.meta.env.VITE_IPSIS_API || "http://127.0.0.1:8000";
const WIDGET_KEY = import.meta.env.VITE_IPSIS_WIDGET_KEY || "";

function App() {
  return (
    <main>
      <h1>Knowledge base</h1>
      <p>The widget is a Web Component; React only wires its events.</p>
      <IpsisChat
        api={API}
        widgetKey={WIDGET_KEY}
        onAnswer={({ status }) => console.info("Answer:", status)}
        onError={({ message }) => console.error("Widget:", message)}
      />
    </main>
  );
}

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
