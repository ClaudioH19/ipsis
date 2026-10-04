import React, { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";

const API = import.meta.env.VITE_RAG_API || "http://127.0.0.1:8000";
const WIDGET_KEY = import.meta.env.VITE_RAG_WIDGET_KEY || "";

function RagExtractivoChat({ onAnswer, onError }) {
  const ref = useRef(null);

  useEffect(() => {
    const widget = ref.current;
    const answer = (event) => onAnswer?.(event.detail);
    const error = (event) => onError?.(event.detail);
    widget.addEventListener("rag:respuesta", answer);
    widget.addEventListener("rag:error", error);

    const script = document.createElement("script");
    script.src = `${API.replace(/\/$/, "")}/widget.js`;
    script.async = true;
    document.body.appendChild(script);
    return () => {
      widget.removeEventListener("rag:respuesta", answer);
      widget.removeEventListener("rag:error", error);
    };
  }, [onAnswer, onError]);

  return React.createElement("ipsis-chat", {
    ref,
    api: API,
    "widget-key": WIDGET_KEY || undefined,
    titulo: "Ayuda documental",
  });
}

function App() {
  return (
    <main>
      <h1>Base de conocimiento</h1>
      <p>El widget es un Web Component; React solo conecta sus eventos.</p>
      <RagExtractivoChat
        onAnswer={({ estado }) => console.info("Respuesta:", estado)}
        onError={({ mensaje }) => console.error("Widget:", mensaje)}
      />
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
