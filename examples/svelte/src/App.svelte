<script>
  import IpsisChat from './IpsisChat.svelte';
  const api = import.meta.env.VITE_IPSIS_API || 'http://127.0.0.1:8000';
  const widgetKey = import.meta.env.VITE_IPSIS_WIDGET_KEY || '';
</script>
<main><h1>Knowledge base</h1><p>Ask about the published documents.</p></main>
<IpsisChat {api} {widgetKey} onAnswer={(detail) => console.info('Answer:', detail.status)} />
