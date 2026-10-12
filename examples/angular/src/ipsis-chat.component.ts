import { afterNextRender, Component, CUSTOM_ELEMENTS_SCHEMA, DestroyRef, ElementRef, inject, viewChild } from '@angular/core';
import { IPSIS_API, IPSIS_WIDGET_KEY } from './config';

@Component({
  selector: 'app-ipsis-chat',
  standalone: true,
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  template: '<ipsis-chat #widget [attr.api]="api" [attr.widget-key]="widgetKey || null" position="bottom-right"></ipsis-chat>',
})
export class IpsisChatComponent {
  readonly api = IPSIS_API;
  readonly widgetKey = IPSIS_WIDGET_KEY;
  private readonly widget = viewChild.required<ElementRef<HTMLElement>>('widget');
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    // Solo navegador, después de renderizar el host; mantener en el componente raíz.
    afterNextRender(() => {
      const host = this.widget().nativeElement;
      const answer = (event: Event) => console.info('Answer:', (event as CustomEvent).detail.status);
      const error = (event: Event) => console.error('Widget:', (event as CustomEvent).detail.message);
      host.addEventListener('ipsis:answer', answer);
      host.addEventListener('ipsis:error', error);
      this.destroyRef.onDestroy(() => {
        host.removeEventListener('ipsis:answer', answer);
        host.removeEventListener('ipsis:error', error);
      });
      if (!document.getElementById('ipsis-script')) {
        const script = document.createElement('script');
        script.id = 'ipsis-script';
        script.src = `${this.api.replace(/\/$/, '')}/widget.js`;
        script.onerror = () => host.dispatchEvent(new CustomEvent('ipsis:error', {
          detail: { message: 'Could not load the assistant widget.' },
        }));
        document.body.appendChild(script);
      }
    });
  }
}
