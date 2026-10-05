# Implantação de {{nombre_asistente}}

Gerado por `ipsis deploy prepare` (perfil `{{perfil}}`). Esta pasta traz
tudo o que o serviço precisa: configuração, documentos, índice, calibração
e avatares. Copie a pasta inteira para o servidor (VPS).

## 1. No servidor

É preciso o Docker com o plugin `compose`. Depois, dentro desta pasta:

```bash
cp .env.ejemplo .env               # e preencha IPSIS_ADMIN_TOKEN se quiser o /admin
sudo chown -R 10001:10001 config .ipsis   # o contêiner não roda como root
docker compose --profile https up -d --build
```

- **HTTPS:** com o perfil `https`, o Caddy obtém e renova o certificado de
  `{{dominio}}`. Antes, aponte o DNS do domínio para o IP do servidor e
  abra as portas 80 e 443.
- **Sem Caddy:** `docker compose up -d --build` deixa o assistente apenas em
  `127.0.0.1:8000`, para o seu próprio proxy.
- **Verificação:** `curl https://{{dominio}}/ready` responde 200 quando tudo
  está pronto; se não, `proyecto.bloqueante` indica o que falta e com qual
  comando resolver.

A primeira construção baixa os modelos do perfil. Depois disso o serviço
não usa a rede.

## 2. No seu site

Cole antes de `</body>`:

```html
{{snippet}}
```

E autorize o seu site no serviço (`cors_origins` em
`config/assistant.yaml`), por exemplo com
`ipsis configure cors_origins=https://www.seu-site.com` antes de preparar a
implantação.

## 3. Painel `/admin`

1. Gere um token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Coloque-o no `.env` como `IPSIS_ADMIN_TOKEN=...`.
3. `docker compose --profile https up -d`.
4. Abra `https://{{dominio}}/admin/panel` e cole o token.

Em produção o `/admin` exige HTTPS. Sem token, o painel não existe.

## Atualização

- **Documentos ou configuração:** no seu computador, execute `ipsis load`,
  `ipsis index` e `ipsis deploy prepare` de novo; copie a pasta e execute
  `docker compose --profile https up -d --build`.
- **Licença:** AGPL-3.0. Se modificar o código, defina `IPSIS_SOURCE_URL` no
  `.env` com a URL das suas alterações.
