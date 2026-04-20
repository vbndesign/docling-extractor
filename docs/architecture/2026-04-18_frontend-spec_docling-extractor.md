# Docling Extractor — Frontend Specification

> **Versão:** 1.1
> **Status:** Draft (para revisão)
> **Autor:** Uma (UX/UI Designer & Design System Architect)
> **Data:** 2026-04-18
> **PRD de referência:** `docs/prd/docling-extractor-prd.md` v1.2
> **Architecture de referência:** `docs/architecture/2026-04-18_architecture_docling-extractor.md` v1.2
> **Referência visual:** `docs/references/frontend/google-ai-studio/` (`App.tsx`, `Index.css`)
> **Escopo:** Story 1.5 — Browser Frontend with HTMX

### Change Log

| Date | Version | Description |
|---|---|---|
| 2026-04-18 | 1.0 | Draft inicial — 13 primitivos, HTML skeleton, contratos HTMX. |
| 2026-04-18 | 1.1 | Incorpora decisões arquiteturais de Aria (arch v1.2): HTMX vendored (não CDN), health check one-shot (drop polling), error envelope com `hint` sempre presente, content negotiation formalizada. |

---

## 1. Introduction

Este documento formaliza o design do frontend da v1 do Docling Extractor. Ele existe para que a Story 1.5 não precise re-descobrir decisões visuais a cada sessão de implementação.

A base visual é o protótipo Google AI Studio armazenado em `docs/references/frontend/google-ai-studio/`. Esse protótipo foi construído em **React + Framer Motion + lucide-react + Tailwind v4 + client-side Gemini**. A stack da v1, por decisão do PRD §4, é **Jinja2 + HTMX + CSS vanilla + Docling server-side** — sem build step, sem npm, sem bundler.

Portanto este spec faz três coisas:

1. **Extrai** os tokens visuais e primitivos de composição do protótipo.
2. **Traduz** os primitivos para CSS vanilla + HTML semântico + HTMX.
3. **Fecha** o contrato de marcação (IDs, classes, atributos `hx-*`) entre a UI e o endpoint `/extract` já definido na Story 1.4.

Ao final da leitura, um desenvolvedor (ou @dev) deve conseguir implementar a Story 1.5 sem precisar consultar o protótipo React novamente.

---

## 2. Design Principles

Herdados do PRD §3 ("Overall UX Vision") e reforçados pela análise do protótipo:

| Princípio | Implicação prática |
|-----------|--------------------|
| **Invisibilidade** — a tool deve desaparecer | Zero ruído visual, zero branding, zero instruções longas na tela. |
| **Entrada única por tela** — URL + PDF + local_path visíveis simultaneamente | Sem abas, sem acordeões, sem estados escondidos. |
| **Feedback progressivo honesto** — não mentir sobre progresso | Spinner + label único. Sem fake drift animado (o servidor não faz streaming). |
| **Erros no mesmo espaço do resultado** — não em popup/toast | Mesma caixa. Só muda a cor da borda e o ícone. |
| **Developer tool, não SaaS** — estética utilitária | Dark theme. Mono em metadados. Uppercase tracking-widest em labels. |
| **Localhost-only** — stateless, single-user | Footer pode exibir `Running on Localhost` sem vergonha. |

---

## 3. Design Tokens

Os tokens abaixo são o contrato mínimo. Todos os valores estilísticos do app DEVEM derivar dessa lista — nada hardcoded em componentes.

### 3.1 Color Tokens

| Token | Valor | Uso |
|-------|-------|-----|
| `--color-bg` | `#0F0F0F` | Background do app, background de botões primários (invertidos). |
| `--color-surface` | `#1A1A1A` | Cards, inputs, dropzone em idle. |
| `--color-surface-raised` | `#1A1A1A` com `box-shadow: 0 4px 24px rgba(0,0,0,0.5)` | Processing card. |
| `--color-border` | `#333333` | Bordas de inputs, cards, separadores `border-t`. |
| `--color-text-primary` | `#EDEDED` | Texto principal, fill de botão primário. |
| `--color-text-secondary` | `#888888` | Labels, metadados, hints, texto muted. |
| `--color-accent` | `#4A90E2` | Hover/focus em inputs, progress bar, links de ação (Copy Path). |
| `--color-success` | `#2ECC71` | Success pill dot, success path-block text, faixa lateral de result-card. |
| `--color-error` | `#E74C3C` | Error pill dot, error border tint, error helper text. |
| `--color-accent-glow` | `rgba(74,144,226,0.6)` | `box-shadow` sutil da progress bar. |

**Nota:** Paleta deliberadamente pequena (9 tokens, 1 derivado de shadow). Não adicionar grays intermediários — se precisar de mais contraste, ajuste opacity sobre `--color-text-secondary` (`opacity: 0.4` ou `0.6`).

### 3.2 Typography Tokens

| Token | Valor |
|-------|-------|
| `--font-sans` | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif` |
| `--font-mono` | `"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace` |

**Type scale (toda em tokens, sem rem arbitrários no markup):**

| Token | Tamanho / Peso | Uso |
|-------|----------------|-----|
| `--text-xs-caps` | `11px / 700 / uppercase / tracking 0.2em` | Section labels, field labels. |
| `--text-tiny-caps` | `9px / 700 / uppercase / tracking 0.24em` | Metadados no header, helper italic no processing. |
| `--text-tiny-mono` | `10px / 400 / mono / uppercase / tracking 0.1em` | Hints secundárias no dropzone e no footer. |
| `--text-body` | `12px / 400 / mono` | Paths, error messages, input content. |
| `--text-title` | `12px / 700 / uppercase / tracking 0.2em` | Header title do app. |
| `--text-success-path` | `12px / 400 / mono` color `--color-success` | Path do arquivo gerado (visível). |

**Regra:** mono é reservado para conteúdo *de dados* (paths, URLs, error messages, identificadores). Labels e CTA são sans uppercase.

### 3.3 Spacing & Layout Tokens

| Token | Valor | Uso |
|-------|-------|-----|
| `--space-1` → `--space-12` | `4px * N` (escala 4-4-8-16-24-32-48-64-96) | Padding e gap. |
| `--radius-sm` | `4px` | Inputs, buttons. |
| `--radius-md` | `8px` | Cards, dropzone. |
| `--radius-full` | `9999px` | Footer pill, status dots. |
| `--main-max-width` | `640px` | Conteúdo principal centralizado. |
| `--header-height` | `auto` (padding `20px`) | Header sticky. |

### 3.4 Motion Tokens

| Token | Valor | Uso |
|-------|-------|-----|
| `--transition-fast` | `150ms ease-out` | Hover states, border color changes. |
| `--transition-normal` | `300ms ease-out` | Dropzone state swap, card entrada/saída. |
| `--spin-duration` | `1s` | Loader. |
| `--pulse-duration` | `2s` | Status dot. |

**Sem `--transition-slow`.** Nada na UI demora mais que 300ms. Se tentar, está errado.

---

## 4. Layout System

### 4.1 App Shell

```
┌─────────────────────────────────────────────────────┐
│ header (sticky, border-b)                           │
│   [D] title-stack           system-health │ vault   │
├─────────────────────────────────────────────────────┤
│                                                     │
│    ┌───────────────────────────────────┐            │
│    │ SECTION: Source Acquisition       │            │
│    │   - URL form                      │            │
│    │   - PDF dropzone                  │            │
│    │   - local_path fallback           │            │
│    ├───────────────────────────────────┤            │
│    │ SECTION: Output Pipeline          │            │
│    │   - idle | processing | result    │            │
│    └───────────────────────────────────┘            │
│         max-width 640px, centered                   │
│                                                     │
├─────────────────────────────────────────────────────┤
│ footer (fixed bottom, pill)                         │
│          Running on Localhost • Obsidian            │
└─────────────────────────────────────────────────────┘
```

### 4.2 Rhythm

- **Header padding:** `20px` vertical, justify-between layout (logo-mark à esquerda, meta-blocks à direita).
- **Main:** `max-width: 640px`, `margin: 0 auto`, `padding: 24px 24px 96px`; em desktop `md+`, padding vertical sobe para `64px 24px 96px`.
- **Entre seções:** `padding-top: 32px` + `border-top: 1px solid var(--color-border)` (a seção "Output Pipeline" é separada da "Source Acquisition" por esse divisor).
- **Dentro de uma seção:** `gap: 16px` entre label e conteúdo; `gap: 32px` entre subcampos (URL form ↔ dropzone ↔ local_path).
- **Footer:** `position: fixed; bottom: 40px; left: 0; right: 0;` com pointer-events none no wrapper e `pointer-events: auto` no pill interno (permite selecionar texto mas não bloqueia cliques em elementos sob ele).

---

## 5. Component Primitives

Os 13 primitivos abaixo compõem 100% da UI. Cada um vira uma ou duas classes CSS em `frontend/static/style.css`.

### 5.1 `app-header`

Estrutura: logo-mark (`D` em quadrado accent) + title-stack + meta right-block.

```html
<header class="app-header">
  <div class="app-header__brand">
    <div class="logo-mark">D</div>
    <div>
      <h1 class="app-header__title">Docling Source Converter</h1>
      <p class="app-header__version">v1.0.0-local / SYSTEM_READY</p>
    </div>
  </div>
  <div class="app-header__meta">
    <div class="meta-block">
      <span class="meta-block__label">System Health</span>
      <span class="meta-block__value">
        <span class="status-dot status-dot--success is-pulsing"></span>
        SERVICE_ACTIVE
      </span>
    </div>
    <div class="meta-block meta-block--divided">
      <span class="meta-block__label">Output Dir</span>
      <span class="meta-block__value meta-block__value--accent">./output/</span>
    </div>
  </div>
</header>
```

**Notas:**
- Logo-mark: 32×32px, `background: var(--color-accent)`, `color: white`, `font-weight: 700`, `border-radius: var(--radius-sm)`.
- **System Health:** fetch one-shot no `DOMContentLoaded` via vanilla JS em `app.js`. Polling foi descartado por decisão de @architect (arch doc §7.3 rationale): em localhost, a próxima request de extração já torna a falha do backend visível — polling a cada 30s seria custo sem benefício.
- O valor de "Output Dir" vem do Jinja template (`{{ config.OUTPUT_DIR }}`).

### 5.2 `section-header`

```html
<h2 class="section-header">Source Acquisition</h2>
```

CSS: `var(--text-xs-caps)`, `color: var(--color-text-secondary)`.

### 5.3 `section-divider`

Puramente CSS no `<section>` seguinte: `border-top: 1px solid var(--color-border); padding-top: 32px;`.

### 5.4 `field-label`

```html
<label class="field-label" for="url-input">Remote Source URL</label>
```

CSS: `var(--text-xs-caps)`, `color: var(--color-text-secondary)`, `display: block`, `margin-bottom: 12px`.

### 5.5 `input-with-icon`

```html
<div class="input-with-icon">
  <span class="input-with-icon__icon">🔗</span>
  <input type="url" id="url-input" name="url"
         class="input-with-icon__field"
         placeholder="https://example.com/document" />
</div>
```

**Notas:**
- Ícone em `position: absolute; left: 16px; top: 50%; transform: translateY(-50%); opacity: 0.4;`.
- Input: `padding: 12px 16px 12px 44px`, `background: var(--color-surface)`, `border: 1px solid var(--color-border)`, `border-radius: var(--radius-sm)`, `font-family: var(--font-mono)`, `font-size: 12px`, `color: var(--color-text-primary)`.
- `:focus` → `border-color: var(--color-accent); outline: none;` com `transition: var(--transition-fast)`.
- Ícones podem ser **SVG inline** no Jinja template (preferível) ou emoji unicode. NÃO importar lucide (violaria "no npm / no build").

### 5.6 `btn-primary`

```html
<button type="submit" class="btn-primary">Extract</button>
```

CSS:
- `background: var(--color-text-primary)` / `color: var(--color-bg)` — **invertido**, é a assinatura visual do CTA.
- `padding: 12px 32px`, `font: var(--text-xs-caps)`, `border-radius: var(--radius-sm)`, `border: none`, `cursor: pointer`.
- `:hover { opacity: 0.9; }`
- `:disabled { opacity: 0.2; cursor: not-allowed; }`
- `:active { transform: translateY(2px); }` — feedback tátil.

### 5.7 `dropzone`

```html
<div class="dropzone"
     id="pdf-dropzone"
     hx-encoding="multipart/form-data"
     hx-post="/extract"
     hx-target="#result"
     hx-swap="innerHTML"
     hx-indicator="#indicator">
  <input type="file" name="file" accept=".pdf" class="dropzone__input" hidden />
  <svg class="dropzone__icon">...upload icon...</svg>
  <p class="dropzone__label">Drag & drop PDF here or click to browse</p>
  <p class="dropzone__hint">Single Document Buffer / 50 MB MAX</p>
</div>
```

**Estados:**
- `default`: `background: rgba(26, 26, 26, 0.4)`, `border: 2px dashed var(--color-border)`.
- `:hover`: `background: rgba(26, 26, 26, 0.6)`, `border-color: var(--color-text-secondary)`, `.dropzone__icon { transform: scale(1.1); }`.
- `.is-dragging` (classe JS): `background: rgba(74, 144, 226, 0.1)`, `border-color: var(--color-accent)`, `.dropzone__icon { color: var(--color-accent); }`.
- Todas transições em `var(--transition-normal)`.

**JS mínimo (vanilla, ~15 linhas):**

```js
const dz = document.getElementById('pdf-dropzone');
const input = dz.querySelector('input[type=file]');
dz.addEventListener('click', () => input.click());
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('is-dragging'); });
dz.addEventListener('dragleave', () => dz.classList.remove('is-dragging'));
dz.addEventListener('drop', e => {
  e.preventDefault();
  dz.classList.remove('is-dragging');
  if (e.dataTransfer.files[0]) {
    input.files = e.dataTransfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }
});
input.addEventListener('change', () => htmx.trigger(dz, 'submit'));
```

### 5.8 `local-path-fallback`

**Atende FR9 + Story 1.5 AC2c.** Mesma primitiva que `input-with-icon` com ícone de pasta, dentro de um mini-form com seu próprio botão.

```html
<form class="local-path-form"
      hx-post="/extract"
      hx-target="#result"
      hx-swap="innerHTML"
      hx-indicator="#indicator">
  <label class="field-label" for="path-input">
    ...ou cole o caminho absoluto do arquivo local
  </label>
  <div class="form-row">
    <div class="input-with-icon">
      <span class="input-with-icon__icon">📁</span>
      <input type="text" id="path-input" name="local_path"
             class="input-with-icon__field"
             placeholder="C:\Users\you\Documents\paper.pdf" />
    </div>
    <button type="submit" class="btn-primary">Extract</button>
  </div>
</form>
```

**Visual weight:** igual ao URL form — mesmo padding, mesma altura de campo, mesmo botão. Diferenciação vem só da label e do ícone.

### 5.9 `status-dot` + `status-pill`

```html
<span class="status-pill status-pill--success">
  <span class="status-dot status-dot--success is-pulsing"></span>
  READY_FOR_IMPORT
</span>
```

CSS:
- Dot: `width: 8px; height: 8px; border-radius: 50%; display: inline-block;`.
- Variants: `--success`, `--error` usam `--color-success` / `--color-error` como `background-color`.
- `.is-pulsing` aplica `animation: pulse var(--pulse-duration) infinite`.
- Pill: `var(--text-xs-caps)` com a cor do variant no texto.

### 5.10 `processing-card`

```html
<div class="processing-card" id="indicator" style="display: none;">
  <div class="loader-spin"></div>
  <p class="processing-card__label">INGESTION ACTIVE</p>
  <p class="processing-card__helper">
    Processing source with Docling. This may take up to 30 seconds for large PDFs.
  </p>
</div>
```

**Notas:**
- `display: none` default; HTMX controla visibilidade via `hx-indicator` → a classe `.htmx-request` força `display: flex`.
- `.loader-spin` é `border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; width: 32px; height: 32px; animation: spin var(--spin-duration) linear infinite;`.
- **NÃO** tem barra de progresso na v1. O servidor Docling é blocking e não oferece sinal de progresso honesto.

### 5.11 `result-card` (success)

```html
<div class="result-card result-card--success">
  <div class="result-card__accent-stripe"></div>
  <div class="result-card__header">
    <span class="status-pill status-pill--success">
      <span class="status-dot status-dot--success"></span>
      READY_FOR_IMPORT
    </span>
    <div class="result-card__actions">
      <button class="text-link-subtle" data-copy="/abs/path/to/file.md">Copy Path</button>
      <button class="text-link-subtle text-link-subtle--muted"
              hx-get="/"
              hx-target="body"
              hx-swap="outerHTML">
        New Ingest
      </button>
    </div>
  </div>
  <div class="path-block">/abs/path/to/output/example-document.md</div>
  <p class="result-card__helper">✓ High fidelity extraction complete.</p>
</div>
```

**Notas:**
- `result-card__accent-stripe`: `position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: var(--color-success); opacity: 0.5;`.
- Copy button: vanilla JS `navigator.clipboard.writeText(btn.dataset.copy)` + feedback efêmero "Copied!" por 1.5s trocando o `textContent`.
- "New Ingest" pode ser mais simples: `<a href="/" class="text-link-subtle text-link-subtle--muted">New Ingest</a>` (reload completo é aceitável — reseta tudo).

### 5.12 `result-card` (error)

```html
<div class="result-card result-card--error">
  <div class="result-card__header">
    <span class="status-pill status-pill--error">
      <span class="status-dot status-dot--error"></span>
      PIPELINE_ERROR
    </span>
  </div>
  <div class="error-message">
    <strong>SOURCE_FETCH_FAILED</strong>
    <p>URL returned 404.</p>
    <p class="error-message__hint">Verify the URL is publicly accessible.</p>
  </div>
  <button class="text-link-subtle text-link-subtle--muted"
          hx-get="/" hx-target="body" hx-swap="outerHTML">
    Dismiss and retry extraction
  </button>
</div>
```

**Notas:**
- Usa o envelope de erro definido pela Architecture §2.1(b): `{ code, message, hint }`.
- `error-message`: `background: rgba(231, 76, 60, 0.05)`, `border: 1px solid rgba(231, 76, 60, 0.1)`, `border-radius: var(--radius-sm)`, `padding: 16px`, `font-family: var(--font-mono)`, `color: var(--color-error)`.
- Mantém a marcação DO MESMO `#result` do caso de sucesso — é o endpoint que retorna o parcial HTML de erro em vez do de sucesso.

### 5.13 `empty-state`

```html
<div class="empty-state" id="result">
  <svg class="empty-state__icon">...document icon...</svg>
  <p class="empty-state__label">Awaiting payload input signal</p>
</div>
```

CSS: `border: 1px dashed var(--color-border)`, `border-radius: var(--radius-md)`, `padding: 64px 24px`, `text-align: center`, `opacity: 0.3`.

### 5.14 `footer-pill`

```html
<footer class="footer-pill-wrapper">
  <div class="footer-pill">
    Running on Localhost • System: Obsidian Zettelkasten Framework
  </div>
</footer>
```

CSS:
- Wrapper: `position: fixed; bottom: 40px; left: 0; right: 0; display: flex; justify-content: center; pointer-events: none;`.
- Pill: `pointer-events: auto; background: rgba(15, 15, 15, 0.8); backdrop-filter: blur(8px); border: 1px solid var(--color-border); border-radius: var(--radius-full); padding: 8px 16px; font: var(--text-tiny-mono); color: var(--color-text-secondary); opacity: 0.4;`.

---

## 6. HTML Skeleton (Story 1.5)

Arquivo: `frontend/templates/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Docling Source Converter</title>
  <link rel="stylesheet" href="/static/style.css" />
  <!-- HTMX vendored (not CDN) — arch decision §7.3: tool is local-first, must work offline. -->
  <!-- Loaded synchronously (no defer) so `window.htmx` is defined before app.js runs. -->
  <script src="/static/htmx.min.js"></script>
  <script src="/static/app.js" defer></script>
</head>
<body>

  <header class="app-header">
    <!-- ...brand + meta-blocks (§5.1) -->
  </header>

  <main class="app-main">

    <section class="section section--source">
      <h2 class="section-header">Source Acquisition</h2>

      <!-- URL form -->
      <form class="form-row"
            hx-post="/extract"
            hx-target="#result"
            hx-swap="innerHTML"
            hx-indicator="#indicator">
        <label class="field-label sr-only" for="url-input">Remote Source URL</label>
        <!-- §5.5 input-with-icon + §5.6 btn-primary -->
      </form>

      <!-- PDF dropzone -->
      <!-- §5.7 dropzone -->

      <!-- Local path fallback -->
      <!-- §5.8 local-path-fallback -->
    </section>

    <section class="section section--output">
      <h2 class="section-header">Output Pipeline</h2>

      <div id="indicator" class="processing-card htmx-indicator">
        <!-- §5.10 processing-card content -->
      </div>

      <div id="result">
        <!-- §5.13 empty-state as default; HTMX swaps to result-card success or error -->
      </div>
    </section>

  </main>

  <footer class="footer-pill-wrapper">
    <!-- §5.14 footer-pill -->
  </footer>

</body>
</html>
```

**Swap targets:**

| Form / trigger | `hx-target` | Conteúdo retornado pelo endpoint |
|----------------|-------------|-----------------------------------|
| URL form submit | `#result` | Partial Jinja: `result_success.html` ou `result_error.html` |
| Dropzone (file change) | `#result` | Idem |
| Local path form submit | `#result` | Idem |

### 6.1 Partial templates

- `frontend/templates/partials/result_success.html` — renderiza o `result-card--success` (§5.11).
- `frontend/templates/partials/result_error.html` — renderiza o `result-card--error` (§5.12).

**Contrato backend:** o endpoint `/extract` detecta `Accept: text/html` (default do HTMX) e renderiza o partial correspondente. Para clientes que pedirem `Accept: application/json`, retorna o JSON definido na Story 1.4 AC4. Isso mantém compatibilidade com ferramentas CLI sem quebrar o fluxo HTMX.

---

## 7. Interaction States — Reference Table

Estado global da UI é a combinação de `#indicator` (visibilidade) × `#result` (conteúdo). Essa tabela é o "state diagram" da v1.

| Estado | `#indicator` | `#result` |
|--------|--------------|-----------|
| **Idle** (primeira carga) | hidden | `empty-state` (§5.13) |
| **Processing** | visível (via `.htmx-request` class) | conteúdo anterior permanece (ou idle) |
| **Success** | hidden | `result-card--success` (§5.11) |
| **Error** | hidden | `result-card--error` (§5.12) |
| **After "New Ingest" / dismiss** | hidden | `empty-state` |

HTMX controla automaticamente:
- `.htmx-request` class em `#indicator` enquanto a requisição estiver em voo (`hx-indicator="#indicator"`).
- Swap de `#result` quando a resposta chega.

**Não há estado "partial success" ou "retrying".** Uma request → uma resposta → um swap. Simplicidade.

---

## 8. Divergences from the Google AI Studio Reference

Para quem comparar com `App.tsx`, estas são as diferenças intencionais:

| Divergência | Motivo |
|-------------|--------|
| **Drop Framer Motion, AnimatePresence, `motion.div`** | PRD §4: no build step. Transições simples em CSS puro. |
| **Drop lucide-react** | Mesma razão. Ícones viram SVG inline nos templates Jinja. |
| **Drop Tailwind utility classes** | Trocamos por classes semânticas (`.dropzone`, `.field-label`) em CSS vanilla. Mais legível no template Jinja, menos rebuilds. |
| **Drop 6-stage progress drift** | O protótipo mostra drift porque o Gemini streama chunks. Docling é blocking no servidor — fingir progresso detalhado seria desonesto. Usamos spinner + label única. |
| **Add `local_path` fallback input** | FR9 / Story 1.5 AC2c. Não existia no protótipo. |
| **`Output Dir` no header substitui `Vault Root`** | O protótipo sugeria `/10.1 - Documentos/` (vault path do autor). Na v1, a tool **não escreve no vault** — escreve em `OUTPUT_DIR`. Exibir o vault path seria enganoso. |
| **System Health via polling HTMX ou fetch único** | Protótipo fazia `useEffect` com fetch `/api/health`. Traduzimos para `hx-get="/health" hx-trigger="load, every 30s"` num elemento de status, ou um único fetch vanilla no load. |
| **Textos do processing em inglês técnico único** (`INGESTION ACTIVE`) | Protótipo tinha 6 stages em português. Um único label inglês técnico é menos ruído e mais honesto. |

---

## 9. Accessibility Minima

PRD §3 declara "Accessibility: None" — sem WCAG formal. Ainda assim, minimalismo de acessibilidade é barato e correto:

| Prática | Justificativa |
|---------|---------------|
| `<label>` sempre associada a `<input>` via `for` / `id` | Screen readers + clique expandido. |
| `<button type="submit">` e `<button type="button">` explícitos | Evita submits acidentais. |
| Foco visível em inputs e botões (`:focus` com `outline` ou `border-color`) | PRD §3: "navegação por teclado desejável". |
| Contraste `--color-text-primary` (`#EDEDED`) sobre `--color-bg` (`#0F0F0F`) | Ratio 15.8:1 — excede AAA. |
| Contraste `--color-text-secondary` (`#888`) sobre `--color-bg` | Ratio 5.8:1 — passa AA. OK para labels. |
| `aria-live="polite"` no `#result` | Screen reader anuncia resultado/erro quando HTMX faz swap. |
| `aria-busy="true"` no `#result` durante request (adicionar via `hx-on::before-request`) | Anuncia "carregando". |
| `sr-only` class (`position: absolute; width: 1px; height: 1px; overflow: hidden;`) para labels visualmente redundantes | Caso algum label seja omitido visualmente. |

**Não fazer na v1:**
- Audit formal WCAG.
- Skip links.
- Suporte a `prefers-reduced-motion` (única animação séria é o spinner — aceitável manter).
- Alto contraste opcional.

---

## 10. File Deliverables for Story 1.5

| Arquivo | Responsabilidade | Linhas estimadas |
|---------|------------------|-------------------|
| `frontend/templates/index.html` | Shell completo (§6) | ~120 |
| `frontend/templates/partials/result_success.html` | Partial para `#result` em sucesso | ~20 |
| `frontend/templates/partials/result_error.html` | Partial para `#result` em erro | ~15 |
| `frontend/static/style.css` | Todos os tokens (§3) + todos os primitivos (§5) | ~350 |
| `frontend/static/htmx.min.js` | HTMX 1.9.x vendored (arch §7.3 — tool é local-first) | ~50KB asset |
| `frontend/static/app.js` | Dropzone handlers (§5.7) + copy-to-clipboard (§5.11) + aria-busy toggle (§9) + health check one-shot (§5.1) | ~55 |

**Total:** ~560 linhas de código + 1 asset vendored (htmx.min.js). Zero dependências de rede em runtime.

---

## 11. Handoff & Architectural Decisions

### 11.1 Decisions received from @architect (Aria, arch doc v1.2 — 2026-04-18)

As duas perguntas que eu tinha aberto para Aria foram respondidas, mais 4 decisões colaterais que ela consolidou:

| # | Decisão | Autoridade | Impacto no spec |
|---|---------|-----------|-----------------|
| D1 | **Content negotiation no `POST /extract`** via header `Accept`. `text/html` (sem `application/json`) → HTML partial. Senão → JSON. Default = JSON (preserva contrato PRD AC4 para CLI/Swagger). | arch §7.3 + Story 1.4 AC9 proposto | Confirma que §5.11 e §5.12 (result-card success/error) são servidos como partials Jinja pelo backend. Nenhuma mudança de markup. |
| D2 | **`hint` é campo obrigatório** no envelope de erro — nunca null, nunca omitido. Resolvido por `ERROR_CATALOG: dict[str, tuple[str, str]]` em `backend/errors.py` (6 codes × `(default_message, hint)`). | arch §10.2 | Confirma que §5.12 error-card pode assumir `{code, message, hint}` sem null-check. Markup existente já estava correto. |
| D3 | **HTMX vendored (`/static/htmx.min.js`), não CDN.** Tool é explicitamente local-first (NFR1) — depender de CDN contraria o próprio propósito. | arch §7.3 rationale | §6 (HTML skeleton) patchado: `<script src="/static/htmx.min.js"></script>` sem `defer` + `app.js` com `defer`. §10 File Deliverables inclui o vendored asset. |
| D4 | **Health check = fetch one-shot** no `DOMContentLoaded`. Polling descartado (custo sem benefício em localhost). | arch recommendation | §5.1 app-header atualizada. `app.js` ganha ~5 linhas. |
| D5 | **`Output Dir` no header** (substitui `Vault Root` do protótipo) — APROVADO sem ressalvas. Alinha com FR6 ("tool não escreve no vault"). | arch ratification | §5.1 já estava correta. Sem mudanças. |
| D6 | **`aria-busy` + `aria-live` no `#result`** — APROVADO, fica no escopo da Story 1.5 AC atual. | arch ratification | §9 Accessibility Minima já estava correta. Sem mudanças. |

### 11.2 Resolved open questions (decididas pelo @architect)

Aria confirmou as minhas duas recomendações contra NFRs do PRD:

| Questão | Decisão | Autoridade |
|---------|---------|-----------|
| Keyboard shortcut `Esc` para "New Ingest"? | **NÃO na v1.** Zero ACs pedem; complexidade sem valor. | arch recommendation (alinhado com scope mínimo) |
| Remember last input mode via `localStorage`? | **NÃO.** NFR2 é explícito sobre statelessness. Se virar desejo real, v2. | NFR2 enforcement |

### 11.3 Para @pm (Morgan)

**Ação pendente:** adicionar **Story 1.4 AC9** no PRD e bumpar para v1.3. Texto literal proposto por @architect está no arch doc §7.3. Sem esse AC, o handler de dual-format fica sem âncora em ACs.

### 11.4 Para @sm (River)

Story 1.5 está dimensionada para este spec. Sugiro que o `*draft` da 1.5:
- Referencie este arquivo em **Dev Notes**.
- Copie os 13 primitivos (§5) como checklist auxiliar.
- Espere a atualização do PRD (Story 1.4 AC9) antes de começar, já que o contrato de `/extract` com HTMX depende disso.

### 11.5 Para @dev (Dex)

- **HTMX vendoring:** baixar `htmx.min.js` v1.9.x e commitar em `frontend/static/`. Não usar CDN.
- **Ordem dos scripts no `<head>`:** HTMX **sem** `defer` (carga síncrona garante `window.htmx` definido antes do parse do `app.js`); `app.js` **com** `defer`.
- **Copy-to-clipboard** em `http://127.0.0.1:*` funciona em Chrome/Firefox modernos sem HTTPS — sem polyfill.
- **Templates de partial:** `frontend/templates/partials/result_success.html` e `result_error.html` — estrutura idêntica a §5.11 e §5.12, variáveis Jinja `{{ result.output_path }}`, `{{ result.filename }}`, `{{ code }}`, `{{ message }}`, `{{ hint }}`.

---

*Spec v1.1 — incorpora decisões arquiteturais de Aria (arch v1.2). Pronto para @pm aplicar AC9 no PRD e @sm fazer `*draft` da Story 1.5.*
