import React, { useEffect, useRef } from "react";

// Mantener en el layout raíz: un widget por documento, con API y clave fijas.
export function IpsisChat({ api, widgetKey = "", onAnswer, onError }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!document.getElementById("ipsis-script")) {
      const script = document.createElement("script");
      script.id = "ipsis-script";
      script.src = `${api.replace(/\/$/, "")}/widget.js`;
      script.onerror = () => ref.current?.dispatchEvent(new CustomEvent("ipsis:error", {
        detail: { message: "Could not load the assistant widget." },
      }));
      document.body.appendChild(script);
    }
  }, [api]);
  useEffect(() => {
    const widget = ref.current;
    const answer = (event) => onAnswer?.(event.detail);
    const error = (event) => onError?.(event.detail);
    widget.addEventListener("ipsis:answer", answer);
    widget.addEventListener("ipsis:error", error);
    return () => {
      widget.removeEventListener("ipsis:answer", answer);
      widget.removeEventListener("ipsis:error", error);
    };
  }, [onAnswer, onError]);
  return React.createElement("ipsis-chat", {
    ref, api, "widget-key": widgetKey || undefined, position: "bottom-right",
  });
}
