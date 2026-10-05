import React, { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";

const API = import.meta.env.VITE_IPSIS_API || "http://127.0.0.1:8000";
const WIDGET_KEY = import.meta.env.VITE_IPSIS_WIDGET_KEY || "";

function IpsisChat({ onAnswer, onError }) {
  const ref = useRef(null);

  useEffect(() => {
    const widget = ref.current;
    const answer = (event) => onAnswer?.(event.detail);
    const error = (event) => onError?.(event.detail);
    widget.addEventListener("ipsis:answer", answer);
    widget.addEventListener("ipsis:error", error);

    const script = document.createElement("script");
    script.src = `${API.replace(/\/$/, "")}/widget.js`;
    script.async = true;
    document.body.appendChild(script);
    return () => {
      widget.removeEventListener("ipsis:answer", answer);
      widget.removeEventListener("ipsis:error", error);
    };
  }, [onAnswer, onError]);

  return React.createElement("ipsis-chat", {
    ref,
    api: API,
    "widget-key": WIDGET_KEY || undefined,
    title: "Help center",
  });
}

function App() {
  return (
    <main>
      <h1>Knowledge base</h1>
      <p>The widget is a Web Component; React only wires its events.</p>
      <IpsisChat
        onAnswer={({ status }) => console.info("Answer:", status)}
        onError={({ message }) => console.error("Widget:", message)}
      />
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
