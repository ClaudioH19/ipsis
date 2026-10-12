import { Component, provideZonelessChangeDetection } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { IpsisChatComponent } from './ipsis-chat.component';

@Component({
  selector: 'app-root', standalone: true, imports: [IpsisChatComponent],
  template: '<main><h1>Knowledge base</h1><p>Ask about the published documents.</p></main><app-ipsis-chat />',
})
class AppComponent {}
bootstrapApplication(AppComponent, { providers: [provideZonelessChangeDetection()] }).catch(console.error);
