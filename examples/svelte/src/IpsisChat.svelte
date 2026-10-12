<script>
  import { onMount } from 'svelte';
  let { api, widgetKey = '', onAnswer, onError } = $props();
  let widget;
  // onMount no se ejecuta durante SSR; mantener este componente en el layout raíz.
  onMount(() => {
    const answer = (event) => onAnswer?.(event.detail);
    const error = (event) => onError?.(event.detail);
    widget.addEventListener('ipsis:answer', answer);
    widget.addEventListener('ipsis:error', error);
    if (!document.getElementById('ipsis-script')) {
      const script = document.createElement('script');
      script.id = 'ipsis-script';
      script.src = `${api.replace(/\/$/, '')}/widget.js`;
      script.onerror = () => error({ detail: { message: 'Could not load the assistant widget.' } });
      document.body.appendChild(script);
    }
    return () => {
      widget.removeEventListener('ipsis:answer', answer);
      widget.removeEventListener('ipsis:error', error);
    };
  });
</script>
<ipsis-chat bind:this={widget} {api} widget-key={widgetKey || undefined} position="bottom-right"></ipsis-chat>
