# Docling Extractor — Architecture Document

> **Versão:** 1.2
> **Status:** Draft (para revisão)
> **Autor:** Aria (Architect)
> **Data:** 2026-04-18
> **PRD de referência:** `docs/prd/docling-extractor-prd.md` v1.2
> **Escopo:** v1 — ferramenta local, single-user. Infra de deploy fica para depois.

### Change Log

| Date | Version | Description |
|---|---|---|
| 2026-04-18 | 1.0 | Draft inicial (response ao PRD v1.1). |
| 2026-04-18 | 1.1 | Incorpora should-fixes S1–S4 como ACs delta. |
| 2026-04-18 | 1.2 | Handoff do frontend spec: §7.2 ganha content negotiation (HTMX); §10.2 formaliza `ERROR_CATALOG` (hint sempre presente). Propõe Story 1.4 AC9 ao PM. |

---

## 1. Introduction

Este documento contém a revisão técnica do PRD v1.1 e o desenho arquitetural do **Docling Extractor**, uma ferramenta **local** que converte URLs (HTML/PDF) e uploads de PDF em arquivos Markdown fiéis à fonte, com frontmatter mínimo, prontos para ingestão manual no vault Obsidian do autor (camada `1.1 Documento` do Framework de Conhecimento Pessoal).

A arquitetura é deliberadamente pequena. O PRD já decidiu estrutura de pastas, stack e 6 stories sequenciais. O valor que este documento agrega é:

1. **Validar** as três perguntas arquiteturais levantadas pelo PRD §8.
2. **Expor** riscos técnicos que o PRD não tornou explícitos.
3. **Fechar** contratos de interface entre as camadas (service → builder → writer → endpoint) com a precisão que o código vai exigir.

**Deploy online (v2) está explicitamente fora do escopo deste documento.** Quando for a hora, a gente volta aqui.

---

## 2. Technical Review of PRD v1.1

### 2.1 Resposta às três validações da seção 8

#### (a) Pipeline Docling abstraída em `docling_service.py` sem vazar para camadas superiores → **APROVADO com ajustes**

**O que está certo no PRD:**
- Função única `extract(source)` com detecção de tipo interna (Story 1.2 AC1–AC2).
- Retorno uniforme `(markdown, metadata)` (AC3).
- Exceptions tipadas impedem vazamento de erros genéricos do Docling (AC8).

**Ajustes recomendados:**

| # | Ajuste | Motivo |
|---|--------|--------|
| A1 | Retornar `dataclass ExtractionResult`, não `dict` | Type safety, autocomplete, previne typos em chaves. O PRD admite "dataclass ou dict" — escolher dataclass. |
| A2 | Definir exceptions em `backend/errors.py` (módulo compartilhado) | Para o endpoint importar sem acoplar a camada de rota ao serviço. |
| A3 | Encapsular chamada do Docling em função privada `_run_docling(...)` | Facilita mockar nos testes (Story 1.2 AC6 cita "mockando quando possível"). |
| A4 | Executar conversão em threadpool (`asyncio.to_thread`) no endpoint | Docling é síncrono CPU-bound. Ver §2.2 R1. |

#### (b) Tratamento de exceptions tipadas consistente entre service e endpoint → **APROVADO com centralização**

**O que está certo no PRD:**
- Mapping explícito: `SourceFetchError → 502`, `ConversionError → 422`, outro → 500 (Story 1.4 AC5).
- Erros adicionais: oversize → 413 (AC3), timeout → 504 (AC6), validação → 400 (AC2).

**Ajuste recomendado:**

Consolidar todos os mappings em um único `exception_handler` FastAPI (`backend/errors.py::register_handlers(app)`), não em `try/except` espalhado pelo endpoint. Benefícios: (i) a rota `/extract` fica legível, (ii) formato de erro consistente, (iii) um lugar só para mudar se um dia precisar.

**Formato de erro sugerido** (uma camada além do PRD, ainda minimalista):

```json
{ "status": "error", "code": "SOURCE_FETCH_FAILED", "message": "URL returned 404.", "hint": "Verify the URL is publicly accessible." }
```

O campo `code` em UPPERCASE_SNAKE é mais útil para a UI HTMX que só o `detail` default do FastAPI — permite estilizar/agrupar no frontend se precisar. Custo: ~10 linhas em `errors.py`. Se achar pesado, derrubar e usar o `detail` default tudo bem.

#### (c) Contrato do `/extract` "extensível para v2 sem reescrita" → **N/A em v1**

O PRD §8 pede que este endpoint seja pensado para não precisar de reescrita em v2. Minha leitura: **uma arquitetura em camadas limpa (service puro, sem I/O de disco, sem vazamento do Docling) já entrega isso naturalmente.** Não preciso adicionar versionamento de rota (`/api/v1/...`), envelope de resposta complexo ou flags de configuração para futuras variantes de deploy. Esses custos só se pagam quando v2 existir.

**O que vou fazer agora, e só porque é barato e independente de deploy:**
- Manter o service (`docling_service.extract`) puro — sem escrever em disco, sem conhecer o `output_dir`. Quem escreve é o `file_writer`.
- Manter uma assinatura estável de retorno (`ExtractionResult`).

**O que NÃO vou fazer:**
- Prefixar rotas com `/api/v1/` em v1.
- Criar flags `ENV=production`, `ALLOW_LOCAL_PATH`, etc. para deploy futuro.
- Envelopar success response em `{status, data: {...}}` — sigo literalmente o formato do PRD: `{"status": "ok", "output_path": "...", "filename": "..."}`.

Se a v2 acontecer, esse é o momento certo para discutir versionamento. Até lá, simplicidade.

### 2.2 Riscos técnicos adicionais não explícitos no PRD

Estes não estão no PRD mas o código vai tropeçar neles se ignorados:

| # | Risco | Severidade | Mitigação |
|---|-------|-----------|----------|
| R1 | **Docling é CPU-bound síncrono**, FastAPI é async. Sem threadpool, o `/health` fica inacessível durante uma conversão. | HIGH | Wrap em `asyncio.to_thread()` no endpoint. |
| R2 | **Primeira execução baixa modelos** (NFR6 reconhece, não mitiga). Um request `/extract` às 9h da manhã pode travar 2–5 min baixando. | MEDIUM | `lifespan` do FastAPI: no startup, instanciar `DocumentConverter()` uma vez (dispara download se necessário). Documentar em README. |
| R3 | **HEAD request para detectar Content-Type** (Story 1.2 AC2) falha silenciosamente: muitos servidores retornam 405 ou mentem sobre `Content-Type`. | MEDIUM | Fallback: se HEAD falhar, fazer GET com `Range: bytes=0-1023`, inspecionar magic bytes (`%PDF-` para PDF, `<` para HTML). |
| R4 | **`local_path` aceita caminho absoluto do FS** — path traversal é irrelevante em single-user local. Mencionar em README que esse modo pressupõe confiança total no operador. | LOW | Validar: existe, é arquivo, termina em `.pdf` OU magic bytes `%PDF-`. |
| R5 | **Slugificação gera nomes longos** (>255 chars). Windows NTFS trava. | LOW | Truncar slug a 200 chars antes de aplicar sufixo de colisão e extensão `.md`. |
| R6 | **Race condition no file_writer** (colisão `-2`, `-3` da Story 1.3 AC7) — em v1 single-user a chance é quase zero, mas o check-then-write é TOCTOU. | LOW | Usar `pathlib.Path.open('x')` (fail if exists) em loop. Atômico. |
| R7 | **`httpx` sem User-Agent nem timeout explícitos** vaza assinatura default e pode ficar pendurado. (S3 já reconhecido pelo PO.) | MEDIUM | Fixar `headers={"User-Agent": "docling-extractor/1.0"}`, `timeout=httpx.Timeout(30.0, connect=10.0)`. |
| R8 | **Binding 0.0.0.0 vs 127.0.0.1** — `uvicorn ... --host 0.0.0.0` expõe o serviço na LAN. | MEDIUM | Default `127.0.0.1`. Documentar no README. |
| R9 | **`python-slugify` com conteúdo CJK/árabe/acentuado** pode produzir slug vazio. | LOW | Fallback: se slug vazio, usar `document-{timestamp}.md`. |

### 2.3 Decisão sobre os Should-fix pendentes do PO

| Item | Decisão arquitetural |
|------|---------------------|
| **S1** (git init + commit inicial em Story 1.1) | Aceitar. Adicionar AC 1.1.9: "Repositório `git init` + commit inicial com `.gitignore` e `.env.example`." |
| **S2** (pinar versões no pyproject.toml) | Aceitar *com limites superiores*. Formato: `fastapi>=0.110,<0.120`, `docling>=2.0,<3.0`. Evita drift sem trancar patches. |
| **S3** (User-Agent + timeout) | Aceitar. Adicionar a Story 1.2 AC9: "HTTP client usa `User-Agent` identificável e `timeout` de 30s (connect 10s)." |
| **S4** (mencionar `/docs` no README) | Aceitar em Story 1.6 AC3 (seção "Como usar"). |

---

## 3. High Level Architecture

### 3.1 Technical Summary

Monolito Python síncrono dentro de um processo FastAPI async, servindo API REST + HTML estático no mesmo host `127.0.0.1:8000`. O Docling roda inline via `asyncio.to_thread`. Stateless — nenhum DB, nenhuma sessão, nenhum cache persistente entre requests. A estrutura de módulos é uma pipeline linear: `endpoint → service → builder → writer → response`, com exceptions tipadas atravessando as camadas e sendo mapeadas para HTTP em um handler global.

### 3.2 Platform

- **SO:** Windows 11 (ambiente do usuário).
- **Runtime:** Python 3.11+.
- **Processo:** 1 `uvicorn backend.main:app` (default 1 worker, suficiente para uso single-user).
- **Storage:** filesystem local (`./output/`, gitignored).
- **Rede:** bind `127.0.0.1:8000`. Acesso via browser no mesmo host.
- **Dependências externas em runtime:** apenas `httpx` para fetch de URLs. Docling funciona 100% offline após o download inicial dos modelos.

### 3.3 High-Level Diagram

```
┌─────────────────────────────── Browser (localhost) ──────────────────────────────┐
│  index.html (Jinja2 + HTMX) ── style.css                                         │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │ HTMX POST /extract
                                       │ (multipart/form-data)
                                       ▼
┌────────────────────────── FastAPI process (uvicorn, single worker) ──────────────┐
│                                                                                   │
│   routes (main.py)                                                                │
│     GET  /          → render index.html                                           │
│     GET  /health    → {"status":"ok"}                                             │
│     POST /extract   → orchestrate pipeline                                        │
│           │                                                                       │
│           ▼                                                                       │
│   ┌───────────────────── extraction pipeline ────────────────────────────┐        │
│   │                                                                       │        │
│   │  docling_service.extract(source)                                      │        │
│   │    ├─ detect type (httpx HEAD → Content-Type → magic bytes fallback)  │        │
│   │    └─ Docling DocumentConverter (CPU-bound, asyncio.to_thread)        │        │
│   │          │                                                            │        │
│   │          ▼  ExtractionResult(markdown, metadata) + SourceDescriptor   │        │
│   │                                                                       │        │
│   │  frontmatter.build(metadata, source, now) → str (YAML block)          │        │
│   │                                                                       │        │
│   │  file_writer.save(frontmatter, markdown, metadata, source, outdir)    │        │
│   │    ├─ derive filename (title → pdf_name → url_slug)                   │        │
│   │    ├─ slugify + collision suffix                                      │        │
│   │    └─ atomic write (`open('x')`) → SaveResult                         │        │
│   │                                                                       │        │
│   └───────────────────────────────────┬───────────────────────────────────┘        │
│                                       ▼                                            │
│   response                     ── {"status":"ok","output_path":...,"filename":...} │
│   exception handler (errors.py)── {"status":"error","code":...,"message":...}      │
│                                                                                    │
└─────────────────────────────────────┬──────────────────────────────────────────────┘
                                      │ filesystem write
                                      ▼
                           ./output/<slug>.md
                           ↑
                           └── user moves to vault manually
```

### 3.4 Architectural Patterns

- **Layered monolith (pipeline):** endpoint → service → builder → writer. Cada camada tem uma única responsabilidade e se comunica via dataclasses puros.
- **Stateless request/response:** sem sessão, sem queue, sem cache compartilhado. A única "memória" entre requests é o `output/` no disco (e é do usuário, não da app).
- **Exception translation at boundary:** exceptions tipadas do domínio são levantadas no service e traduzidas para HTTP apenas no handler global. Nenhum `raise HTTPException(...)` dentro do service.
- **Lifespan-scoped singleton:** `DocumentConverter` instanciado 1x no startup, reusado em todas as requests. Evita cold-start por conversão.
- **Dependency injection para config:** `output_dir`, `max_upload_mb`, `timeout_seconds` injetados via FastAPI `Depends(get_settings)`. Testes sobrescrevem via `app.dependency_overrides`.

---

## 4. Tech Stack (final)

Ratificando e expandindo a seção 4 do PRD:

| Camada | Tecnologia | Versão pinada (range) | Justificativa |
|--------|-----------|----------------------|--------------|
| Runtime | Python | 3.11+ | Restrição do Docling |
| Web framework | FastAPI | `>=0.110,<0.120` | Async, OpenAPI automático |
| ASGI server | Uvicorn + standard | `>=0.27,<0.31` | Padrão com FastAPI |
| Conversão | Docling | `>=2.0,<3.0` | Core feature — API `DocumentConverter` |
| HTTP client | httpx | `>=0.27,<0.28` | Async, compatível com FastAPI |
| Templating | Jinja2 | `>=3.1,<4.0` | Render de `index.html` |
| Multipart | python-multipart | `>=0.0.9,<0.1` | Necessário p/ upload |
| YAML | PyYAML | `>=6.0,<7.0` | `yaml.safe_dump` no frontmatter |
| Slug | python-slugify | `>=8.0,<9.0` | Kebab-case ASCII robusto |
| Frontend | HTMX | 1.9.x (vendored) | Sem build step |
| CSS | Vanilla | — | Sem framework |
| Dev: testes | pytest + pytest-asyncio + TestClient | `pytest>=8.0,<9.0` | Stack padrão |
| Dev: lint/format | ruff | `>=0.4,<0.5` | Linter + formatter único |
| Deps manager | `uv` (preferido) ou `pip` + `pyproject.toml` | — | Sem Poetry |

**Intencionalmente excluído:** Poetry, pre-commit hooks obrigatórios, Docker, nginx, Redis, Celery, bundler JS, TypeScript, Tailwind.

---

## 5. Data Models

### 5.1 Domain Dataclasses

Vivem em `backend/models.py`. Imutáveis (`frozen=True`).

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

@dataclass(frozen=True)
class ExtractedMetadata:
    """Metadados detectados automaticamente. None ⇒ frontmatter omite o campo."""
    source_title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None

@dataclass(frozen=True)
class SourceDescriptor:
    """Descreve a origem — usado por file_writer para derivar nome e por frontmatter para `location`."""
    kind: Literal["url_html", "url_pdf", "pdf_upload", "pdf_local_path"]
    location: str                           # URL, nome original do arquivo, ou path absoluto
    original_filename: Optional[str] = None # apenas para pdf_upload e pdf_local_path

@dataclass(frozen=True)
class ExtractionResult:
    """Output de docling_service.extract."""
    markdown: str                           # corpo Markdown puro, sem frontmatter
    metadata: ExtractedMetadata
    source: SourceDescriptor

@dataclass(frozen=True)
class SaveResult:
    """Output de file_writer.save — retornado pelo endpoint."""
    output_path: Path                       # absoluto
    filename: str                           # basename
```

### 5.2 Frontmatter Schema

YAML gerado pelo `frontmatter.build`:

```yaml
---
note_type: literature_document          # sempre
created: 2026-04-18                     # sempre (YYYY-MM-DD, data local)
extracted_at: 2026-04-18T14:32:11-03:00 # sempre (ISO 8601 com tz)
location: https://example.com/article   # sempre (URL ou filename)
generated_by: docling                   # sempre
source_title: "Example Article Title"   # se detectado
author: "Jane Doe"                      # se detectado
year: 2024                              # se detectado
---
```

**Proibido gerar:** `title`, `source_type`, `domain`, `concepts_extracted` (FR5).

---

## 6. Components

### 6.1 Component Inventory

| # | Módulo | Responsabilidade | Depende de | Usado por |
|---|--------|-----------------|-----------|-----------|
| 1 | `backend/config.py` | Ler env vars, expor `Settings` | `os`, `pydantic-settings` (opcional) | todos |
| 2 | `backend/errors.py` | Exception hierarchy + handler FastAPI | `fastapi` | `main.py` |
| 3 | `backend/models.py` | Dataclasses do domínio | — | `service`, `frontmatter`, `writer`, `main` |
| 4 | `backend/docling_service.py` | `extract(source) → ExtractionResult`; detecção de tipo, chamada Docling, mapeamento de exceptions | `docling`, `httpx`, `errors`, `models` | `main.py` |
| 5 | `backend/frontmatter.py` | `build(metadata, source, now) → str` (bloco YAML) | `yaml`, `models` | `main.py` |
| 6 | `backend/file_writer.py` | `save(...) → SaveResult`; naming + slug + colisão + atomic write | `python-slugify`, `pathlib`, `models`, `errors` | `main.py` |
| 7 | `backend/main.py` | App factory, lifespan, rotas, registro de handlers | 1–6 + `fastapi`, `jinja2` | entrypoint uvicorn |
| 8 | `frontend/templates/index.html` | UI: URL + drop zone + local_path fallback + result area | HTMX 1.9 | browser |
| 9 | `frontend/static/style.css` | Estilização utilitária | — | browser |

### 6.2 Dependency Graph

```
main.py
  ├── config.py
  ├── errors.py ── models.py
  ├── docling_service.py ── errors.py, models.py
  ├── frontmatter.py ── models.py
  └── file_writer.py ── errors.py, models.py
```

Sem ciclos. Fluxo estritamente descendente.

### 6.3 Interface Contracts

```python
# docling_service.py
async def extract(
    source: str | Path | BinaryIO,
    *,
    http_client: httpx.AsyncClient,
    converter: DocumentConverter,
) -> ExtractionResult: ...

# frontmatter.py
def build(
    metadata: ExtractedMetadata,
    source: SourceDescriptor,
    now: datetime,
) -> str: ...

# file_writer.py
def save(
    frontmatter_str: str,
    markdown_body: str,
    metadata: ExtractedMetadata,
    source: SourceDescriptor,
    output_dir: Path,
) -> SaveResult: ...
```

`ExtractionResult` já carrega `SourceDescriptor` internamente — evita passar a origem duas vezes pelas camadas.

---

## 7. API Specification

### 7.1 Endpoints

| Método | Path | Descrição | Request | Response |
|--------|------|----------|---------|---------|
| `GET` | `/` | UI HTML | — | `text/html` |
| `GET` | `/health` | Liveness | — | `{"status":"ok"}` |
| `POST` | `/extract` | Dispara pipeline de extração | `multipart/form-data` | JSON (ver §7.2) |
| `GET` | `/static/*` | Arquivos estáticos (CSS, JS vendored) | — | assets |
| `GET` | `/docs` | OpenAPI Swagger UI | — | HTML (FastAPI default) |

### 7.2 `POST /extract` — contrato detalhado

**Request (multipart/form-data):**

Exatamente **um** dos três campos deve estar presente:
- `url`: string (URL HTTP/HTTPS válida)
- `file`: upload de arquivo (`.pdf`)
- `local_path`: string (caminho absoluto para `.pdf` no FS local)

**Response 200 (sucesso)** — formato literal do PRD (Story 1.4 AC4):

```json
{
  "status": "ok",
  "output_path": "C:\\code\\projetos-estudos\\python\\docling\\output\\example-article.md",
  "filename": "example-article.md"
}
```

**Responses de erro:**

| HTTP | `code` | Gatilho |
|------|--------|--------|
| 400 | `INVALID_INPUT` | Zero ou múltiplos campos fornecidos; `local_path` não existe ou não é PDF |
| 413 | `UPLOAD_TOO_LARGE` | Upload excede `MAX_UPLOAD_MB` |
| 422 | `CONVERSION_FAILED` | `ConversionError` do service (PDF corrompido, HTML vazio, sem texto) |
| 502 | `SOURCE_FETCH_FAILED` | `SourceFetchError` do service (URL 404, DNS, TLS) |
| 504 | `REQUEST_TIMEOUT` | Excede `REQUEST_TIMEOUT_SECONDS` |
| 500 | `INTERNAL_ERROR` | Qualquer outra exception não mapeada |

Body de erro (todos):

```json
{ "status": "error", "code": "SOURCE_FETCH_FAILED", "message": "URL returned 404.", "hint": "Verify the URL is publicly accessible and returns HTTP 200." }
```

### 7.3 Content Negotiation (HTMX dual-format)

O mesmo endpoint `POST /extract` serve dois contratos de resposta, selecionados pelo header `Accept` da requisição. Essa ADR resolve o handoff do frontend spec (§11 do `frontend-spec`), que precisa de HTML fragments para HTMX fazer swap em `#result`.

**Regra de precedência:**

| `Accept` recebido | Response format |
|---|---|
| contém `text/html` **e não** contém `application/json` | HTML partial (Jinja2) |
| contém `application/json` **e não** contém `text/html` | JSON (§7.2) |
| ambos / `*/*` / ausente | **JSON** (default — preserva contrato literal PRD Story 1.4 AC4 para clientes CLI/script/Swagger UI) |

**Implementação:**

```python
# backend/main.py
def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept

@app.post("/extract")
async def extract_endpoint(request: Request, ...) -> Response:
    save_result: SaveResult = await run_pipeline(...)
    if _prefers_html(request):
        return templates.TemplateResponse(
            "partials/result_success.html",
            {"request": request, "result": save_result},
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "output_path": str(save_result.output_path),
            "filename": save_result.filename,
        },
    )
```

**Por que single endpoint e não rotas separadas (`/extract` + `/ui/extract`):**
1. HTMX é hypermedia-first; content negotiation é HTTP idiomático, não um hack.
2. Uma URL pública = uma entrada no Swagger, um caminho de log, um set de testes.
3. O "acoplamento cosmético" (endpoint conhece path de templates) é trivial — 2 linhas.
4. CLI/script consumers ganham o mesmo contrato JSON do PRD sem precisar de `Accept` explícito.

**Impacto em testes (Story 1.4 AC7 + AC9 proposto):**
- `test_extract_returns_json_when_no_accept` — preserva contrato PRD.
- `test_extract_returns_html_when_accept_text_html` — novo caminho HTMX.
- `test_extract_returns_json_when_accept_application_json` — clientes explícitos.
- `test_error_respects_accept_header` — handler global aplica a mesma regra (§10.2).

**AC delta proposto para Story 1.4 (a ser aplicado em PRD v1.3 pelo @pm):**

> **AC9.** O endpoint `POST /extract` aplica content negotiation via header `Accept`: se o cliente preferir `text/html` (HTMX default) e não preferir `application/json`, retorna partial Jinja2 (`frontend/templates/partials/result_success.html` em sucesso; `frontend/templates/partials/result_error.html` em erro, com status HTTP apropriado). Caso contrário, retorna o JSON definido em AC4/AC5. O handler global de exceptions respeita a mesma regra. Testes cobrem: (a) `Accept: text/html` retorna HTML em sucesso e em erro; (b) ausência de `Accept` retorna JSON (preserva contrato AC4); (c) `Accept: application/json` retorna JSON.

---

## 8. Core Workflows

### 8.1 Sequência de extração (happy path — URL HTML)

```
Browser                Endpoint              Service              Builder            Writer
   │                     │                     │                     │                 │
   │─ POST /extract (url="https://…") ──────▶ │                     │                 │
   │                     │                     │                     │                 │
   │                     │── validate form ───▶│                     │                 │
   │                     │── extract(url) ────▶│                     │                 │
   │                     │                     │── httpx HEAD ──▶ net│                 │
   │                     │                     │◀── Content-Type ────│                 │
   │                     │                     │── DocumentConverter │                 │
   │                     │                     │   (asyncio.to_thread)                 │
   │                     │◀── ExtractionResult ─                    │                 │
   │                     │── build(meta, src, now) ─────────────────▶│                 │
   │                     │◀── frontmatter_str ─────────────────────────                │
   │                     │── save(fm, md, meta, src, outdir) ──────────────────────────▶│
   │                     │                                                             │── write .md ▶ FS
   │                     │◀── SaveResult(output_path, filename) ────────────────────────│
   │◀── 200 {"status":"ok","output_path":"...","filename":"..."} ──                    │
```

### 8.2 Sequência de erro (URL 404)

```
Browser              Endpoint             Service              Handler
   │                   │                    │                    │
   │─ POST /extract ──▶│                    │                    │
   │                   │── extract(url) ───▶│                    │
   │                   │                    │── httpx GET ─▶ net │
   │                   │                    │◀─ 404              │
   │                   │                    │── raise SourceFetchError("URL returned 404")
   │                   │◀───────────────────│                    │
   │                   │── exception propagates to handler ──────▶│
   │                   │                                          │── translate to 502
   │◀── 502 {"status":"error","code":"SOURCE_FETCH_FAILED",...} ──│
```

### 8.3 Startup lifespan (download de modelos Docling)

```
uvicorn boots                  FastAPI lifespan               DocumentConverter
   │                                │                              │
   │── import main ────────────────▶│                              │
   │── app starts ─────────────────▶│                              │
   │                                │── new DocumentConverter() ──▶│
   │                                │                              │── check local cache
   │                                │                              │── (if miss) download ~600MB
   │                                │◀── ready ────────────────────│
   │                                │── store in app.state.converter
   │◀── ready to accept requests ───│                              │
```

Primeiro boot é lento (2–5 min dependendo de rede). Boots subsequentes são instantâneos. Documentar em README (Story 1.6 AC3).

---

## 9. Source Tree

```
docling-extractor/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # app factory, lifespan, routes, static+templates mounts
│   ├── config.py               # Settings (env-driven), get_settings() dependency
│   ├── errors.py               # exception hierarchy + FastAPI handlers
│   ├── models.py               # dataclasses (ExtractionResult, ExtractedMetadata, SourceDescriptor, SaveResult)
│   ├── docling_service.py      # extract(source) + type detection + exception translation
│   ├── frontmatter.py          # build(metadata, source, now) → YAML string
│   └── file_writer.py          # save(fm, body, meta, src, outdir) → SaveResult
├── frontend/
│   ├── templates/
│   │   └── index.html          # Jinja2 + HTMX (single page)
│   └── static/
│       ├── style.css
│       └── htmx.min.js         # vendored
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # fixtures: tmp output_dir, mock DocumentConverter, TestClient
│   ├── fixtures/
│   │   ├── sample.html
│   │   ├── sample.pdf
│   │   └── scanned.pdf
│   ├── test_docling_service.py
│   ├── test_frontmatter.py
│   ├── test_file_writer.py
│   ├── test_errors.py
│   └── test_endpoints.py
├── output/                     # gitignored
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

**Divergências vs PRD §4:** adicionei `models.py`, `errors.py`, `test_file_writer.py`, `test_errors.py`, `conftest.py`, `htmx.min.js`. Todos por clareza e testabilidade.

---

## 10. Error Handling Strategy

### 10.1 Exception Hierarchy (`backend/errors.py`)

```python
class DoclingExtractorError(Exception):
    """Base. Nunca instanciada diretamente."""
    code: str = "INTERNAL_ERROR"
    http_status: int = 500

class InvalidInputError(DoclingExtractorError):
    code = "INVALID_INPUT"; http_status = 400

class UploadTooLargeError(DoclingExtractorError):
    code = "UPLOAD_TOO_LARGE"; http_status = 413

class SourceFetchError(DoclingExtractorError):
    code = "SOURCE_FETCH_FAILED"; http_status = 502

class ConversionError(DoclingExtractorError):
    code = "CONVERSION_FAILED"; http_status = 422

class RequestTimeoutError(DoclingExtractorError):
    code = "REQUEST_TIMEOUT"; http_status = 504
```

### 10.2 Error Catalog & Global Handler

O campo `hint` do envelope de erro (§7.2) é **sempre obrigatório** — nunca null, nunca omitido. Isso evita null-checks na UI e garante que todo `code` conhecido carregue orientação acionável.

**Catálogo (`backend/errors.py`):**

```python
# (default_message, hint) por code. hint é fixo por code;
# message pode ser sobrescrita pela exception instance (ex: "URL returned 404").
ERROR_CATALOG: dict[str, tuple[str, str]] = {
    "INVALID_INPUT":       ("Invalid request payload.",
                            "Provide exactly one of: url, file, or local_path."),
    "UPLOAD_TOO_LARGE":    ("Upload exceeds size limit.",
                            "Reduce file size or adjust MAX_UPLOAD_MB in .env."),
    "SOURCE_FETCH_FAILED": ("Failed to fetch source.",
                            "Verify the URL is publicly accessible and returns HTTP 200."),
    "CONVERSION_FAILED":   ("Docling conversion failed.",
                            "Source may be corrupted, empty, or a scanned PDF (OCR not supported in v1)."),
    "REQUEST_TIMEOUT":     ("Extraction exceeded timeout.",
                            "Try a smaller source or increase REQUEST_TIMEOUT_SECONDS in .env."),
    "INTERNAL_ERROR":      ("An unexpected error occurred.",
                            "Check the server console logs for details."),
}
```

**Handler global** — respeita content negotiation (§7.3):

```python
# backend/errors.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept

async def handler(request: Request, exc: DoclingExtractorError) -> Response:
    default_msg, hint = ERROR_CATALOG.get(exc.code, ERROR_CATALOG["INTERNAL_ERROR"])
    message = str(exc) if str(exc) else default_msg
    payload = {"code": exc.code, "message": message, "hint": hint}

    if _prefers_html(request):
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            "partials/result_error.html",
            {"request": request, **payload},
            status_code=exc.http_status,
        )
    return JSONResponse(
        status_code=exc.http_status,
        content={"status": "error", **payload},
    )

async def unexpected_handler(request: Request, exc: Exception) -> Response:
    # Catch-all: promove qualquer exception não tipada para INTERNAL_ERROR.
    # Log detalhado fica aqui; cliente recebe mensagem genérica.
    logger.exception("Unhandled exception during /extract", exc_info=exc)
    promoted = DoclingExtractorError()
    promoted.code = "INTERNAL_ERROR"
    promoted.http_status = 500
    return await handler(request, promoted)

def register_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DoclingExtractorError, handler)
    app.add_exception_handler(Exception, unexpected_handler)
```

**Invariantes garantidas para a UI:**
1. Todo response de erro tem `{status: "error", code, message, hint}`. Sem null-checks no frontend.
2. `code` é sempre um dos 6 valores do catálogo (subclasses novas exigem entrada no catálogo — enforçar via teste em `test_errors.py`).
3. `hint` é ação orientada ao usuário ("Verify...", "Reduce...", "Try..."), nunca descrição técnica.
4. HTML e JSON responses compartilham o mesmo dict — nenhuma divergência possível entre contratos.

### 10.3 Boundary Rules

1. **`docling_service`, `frontmatter`, `file_writer` só levantam `DoclingExtractorError`** (ou subclasses). Nunca `HTTPException`.
2. **`main.py` não tem `try/except`** no corpo do endpoint — toda tradução passa pelo handler global.
3. **Logs** ficam no handler, não no service — evita duplicação.

### 10.4 Corner case handling (Story 1.6)

| Caso | Exception | Mensagem |
|------|-----------|----------|
| URL 404 | `SourceFetchError` | "URL returned 404. Verify the URL is publicly accessible." |
| HTML vazio / SPA | `ConversionError` | "Extracted content is empty. JavaScript-rendered pages (SPA) are not supported in v1." |
| PDF scanned sem texto | `ConversionError` | "PDF appears to be scanned without extractable text. OCR is not enabled in v1." |
| Upload não-PDF | `InvalidInputError` | "Uploaded file is not a valid PDF." |
| Upload > MAX_UPLOAD_MB | `UploadTooLargeError` | "Upload exceeds MAX_UPLOAD_MB (50 MB)." |
| Timeout | `RequestTimeoutError` | "Extraction exceeded REQUEST_TIMEOUT_SECONDS (60s)." |

---

## 11. Security

Ferramenta local, single-user. Conforme NFR7: sem auth, sem CORS, sem rate limit.

**Precauções concretas:**
- Bind default em `127.0.0.1` (não `0.0.0.0`). Documentar no README como mudar se o usuário explicitamente quiser acesso via LAN.
- `local_path` valida que o path (i) existe, (ii) é arquivo, (iii) termina em `.pdf` ou tem magic bytes `%PDF-`. Isso bloqueia typos óbvios, não intenção maliciosa — que é aceitável pois o operador é o próprio usuário.
- Tamanho: `local_path` aplica a mesma checagem de `MAX_UPLOAD_MB`.
- Upload aceita apenas `.pdf` (por extensão E magic bytes).

---

## 12. Testing Strategy

### 12.1 Pirâmide

- **Unit (rápidos, sem I/O de rede):**
  - `test_frontmatter.py` — casos combinatoriais de campos condicionais + escapes.
  - `test_file_writer.py` — 3 origens de nome + colisão + slug vazio + nome longo.
  - `test_errors.py` — handler produz envelope correto para cada subclasse.
- **Unit com mock do Docling:**
  - `test_docling_service.py` — mocka `DocumentConverter` (via fixture); testa detecção de tipo com `httpx.MockTransport`.
- **Integration (via `fastapi.testclient.TestClient`):**
  - `test_endpoints.py` — 4 casos de sucesso (URL HTML, URL PDF, upload, `local_path`) + corner cases da Story 1.6.

### 12.2 Fixtures

- `tests/fixtures/sample.html` — HTML mínimo (<5KB, commitado).
- `tests/fixtures/sample.pdf` — PDF curto com texto real (~20KB, commitado).
- `tests/fixtures/scanned.pdf` — PDF de 1 página só-imagem (~50KB, commitado) para o caso "PDF sem texto".
- `conftest.py` fornece: `tmp_output_dir`, `mock_docling_result`, `test_client` com overrides de dependências.

### 12.3 Performance

Suíte completa `pytest` deve rodar em <60s (Story 1.6 AC5). `test_docling_service.py` mocka o converter pesado → suíte rápida. 1 ou 2 testes "fumaça" podem invocar Docling real, marcados com `@pytest.mark.slow` e excluídos do default (`pytest -m "not slow"`).

### 12.4 Manual validation

Conforme PRD §4. Documentado em README: lista de URLs reais para os 3 tipos + fallback + 1 erro (Story 1.6 AC7).

---

## 13. Local Deployment

```bash
# setup (1x)
uv venv
uv pip install -e .

# run
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
# abrir http://127.0.0.1:8000
```

Nenhum CI, nenhum Docker, nenhum git push remoto para v1.

---

## 14. Checklist of Acceptance for This Architecture

- [x] Atende todos os FR1–FR14 do PRD.
- [x] Atende todos os NFR1–NFR8 do PRD.
- [x] Responde às 3 perguntas arquiteturais da PRD §8.
- [x] Documenta 9 riscos técnicos adicionais com mitigações.
- [x] Incorpora os 4 should-fix do PO (S1–S4) como ACs delta para Stories 1.1, 1.2, 1.6.
- [x] Define contratos de função precisos para as 3 camadas core (service, builder, writer).
- [x] Define mapping completo de erros para HTTP.
- [x] Define estratégia de testes com pirâmide explícita.

---

## 15. Handoff

### Para @pm (Morgan)

As 4 should-fixes do PO (S1–S4) foram aceitas e mapeadas para ACs delta em Stories 1.1, 1.2, 1.6. Recomendo atualizar o PRD para v1.2 com essas incorporações antes de @sm começar `*draft` da Story 1.1, para evitar que o SM e o Dev descubram as mudanças via handoff indireto.

### Para @sm (River)

Quando iniciar `*draft`, referenciar este documento como autoridade técnica em empate com o PRD. A seção §6.3 (function signatures) é vinculante para Stories 1.2 e 1.3 — os testes unitários devem conferir esses contratos.

### Para @dev (Dex)

Ordem de implementação recomendada dentro de cada story respeita a dependency graph §6.2:
1. `config.py` + `models.py` + `errors.py` (foundation)
2. `file_writer.py` + `frontmatter.py` (puros, testáveis isoladamente)
3. `docling_service.py` (mockar Docling nos testes)
4. `main.py` (integra tudo)
5. `index.html` + `style.css` (último, depende do endpoint estar de pé)

### Para @po (Pax)

Sugiro rodar `*validate-story-draft` em cada story após o @sm aplicar as ACs delta de S1–S4, para confirmar que a renumeração não quebrou cross-references entre stories.

---

*Architecture document gerado em sessão de revisão técnica pela agente Architect (Aria). Pronto para revisão do autor e, se aprovado, para consumo por @sm iniciando `*draft` da Story 1.1.*
