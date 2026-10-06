# Web integration examples

The three examples use the same Web Component and do not duplicate the
interface:

- `html/`: a static page; change `API` in `config.js` and serve it over HTTP.
- `react/`: a Vite app with a React adapter that listens to the component's
  events.
- `wordpress/`: an installable plugin that registers the `[ipsis]`
  shortcode.

Before opening them, start the service with `ipsis serve` and allow the
site's origin with `ipsis configure cors_origins=...`. The widget's public key
identifies the integration, but it does not replace the protection of the
server or the proxy.

## HTML

Change `API` in `html/config.js` and serve the folder over HTTP.

## React

1. Copy `.env.example` to `.env` and set the URL and the public key.
2. Run `npm install`.
3. Run `npm run dev`, or check the build with `npm run build`.

The adapter keeps the Web Component as the single source of the interface and
turns `ipsis:answer` and `ipsis:error` into React callbacks.

## WordPress

1. Copy this folder to `wp-content/plugins/ipsis-widget`.
2. Activate **ipsis Widget** in the plugins panel.
3. Insert the shortcode in a page:

```text
[ipsis api="https://ipsis.example" key="public-site" color="#7c3aed"]
```

Allow the WordPress origin in the service's `cors_origins`. The key is
visible in the HTML and is therefore a public identifier, not a secret.
