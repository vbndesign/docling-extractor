# Docling Extractor

Local, single-user tool that converts URLs (HTML / PDF) and PDF uploads
into Markdown files ready for ingestion into an Obsidian vault. Built on
[Docling](https://github.com/docling-project/docling) and FastAPI.

## Visão geral

Docling Extractor é um wrapper local sobre o Docling que produz arquivos
`.md` com frontmatter YAML mínimo, prontos para serem colados no vault
Obsidian do usuário. Foi desenhado para o framework de conhecimento
pessoal do autor: ao topar com um artigo web ou um PDF que merece entrar
como *literature note*, o usuário cola a URL (ou arraga o PDF), recebe o
`.md` em `./output/` e move manualmente para o vault.

Pipeline: **URL ou PDF → Docling → `.md` + frontmatter em `./output/`.**
Stateless, single-user, desktop-only. Sem banco de dados, sem fila,
sem autenticação.

## Pré-requisitos

- **Python 3.11+**
- **~1 GB de disco livre** para o cache de modelos Docling
- **Conexão de rede no primeiro boot** — o Docling baixa seus modelos
  (~600 MB) na primeira conversão; depois disso funciona offline

## Instalação

Clonar o repo, criar um venv e instalar em modo editável com extras de
dev:

```bash
# Com uv (recomendado)
uv venv
uv pip install -e ".[dev]"

# Ou com pip
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

### Configuração

Copiar `.env.example` para `.env` e ajustar se necessário:

| Variável                  | Default    | Descrição                                      |
| ------------------------- | ---------- | ---------------------------------------------- |
| `OUTPUT_DIR`              | `./output` | Diretório dos `.md` gerados                    |
| `MAX_UPLOAD_MB`           | `50`       | Limite de upload (HTTP 413 acima disso)        |
| `REQUEST_TIMEOUT_SECONDS` | `60`       | Timeout duro por request (HTTP 504 se excede)  |

## Como rodar

Do diretório raiz do projeto:

```bash
# Com uv
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Ou com o venv ativado
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Abrir <http://127.0.0.1:8000>.

> ⚠️ O default `--host 127.0.0.1` é localhost-only por segurança (não há
> autenticação). Para expor na LAN, mudar explicitamente para
> `--host 0.0.0.0` e apenas em rede confiável.

## Como usar

A página principal tem três modos de entrada numa única tela:

1. **Colar URL** (artigo HTML ou PDF remoto) → `Extract`
2. **Drag-and-drop de PDF local** → conversão automática ao soltar
3. **Colar caminho absoluto** no campo `local_path` (fallback) →
   `Extract`

Em qualquer modo, o resultado aparece in-place abaixo (via HTMX, sem
reload) com o caminho do `.md` gerado. O arquivo fica em `OUTPUT_DIR` e
pode ser movido manualmente para o vault.

### Swagger UI

A API expõe `POST /extract` documentado automaticamente em
<http://127.0.0.1:8000/docs> (Swagger UI). Útil para inspecionar o
contrato JSON, testar via `curl`/script, ou explorar os códigos de erro
da `ERROR_CATALOG`.

## Troubleshooting

- **Primeiro boot demorado (2–5 min):** Docling está baixando os modelos
  (~600 MB, cacheados em `~/.cache/docling` nas execuções seguintes).
  Normal. Barra de progresso aparece no console do `uvicorn`.
- **PDF não gera conteúdo útil:** pode ser um PDF *escaneado* (páginas
  como imagem, sem texto extraível). A v1 **não tem OCR**; o endpoint
  responde `422 CONVERSION_FAILED` com hint "OCR is not enabled in v1".
- **URL não gera conteúdo:** a página pode ser uma SPA com render em
  JavaScript. Docling **não executa JS**; sites dinâmicos como
  `twitter.com`, `app.notion.so` etc. não são suportados na v1.
- **`Address already in use`:** outro `uvicorn` está rodando na porta
  8000. Matar o processo (`taskkill /F /PID <pid>` no Windows,
  `lsof -ti:8000 | xargs kill` no macOS/Linux) ou usar `--port 8001`.
- **`local_path` não aceita seu caminho:** o campo aceita caminhos
  absolutos, inclusive formato com aspas (`"C:\...\file.pdf"`) que o
  "Copy as path" do Windows Explorer produz. O arquivo precisa ser `.pdf`
  válido e existir.

## Estrutura do projeto

Árvore simplificada (detalhes em
`docs/architecture/2026-04-18_architecture_docling-extractor.md` §9):

```
docling-extractor/
├── backend/                    # FastAPI app
│   ├── main.py                 # app factory, lifespan, routes
│   ├── config.py               # Settings (env-driven)
│   ├── errors.py               # exception hierarchy + handlers
│   ├── models.py               # dataclasses (ExtractionResult, ...)
│   ├── docling_service.py      # extract(source) + type detection
│   ├── frontmatter.py          # build(metadata) → YAML string
│   └── file_writer.py          # save(...) → .md em OUTPUT_DIR
├── frontend/
│   ├── templates/              # Jinja2 + HTMX
│   └── static/                 # style.css, htmx.min.js (vendored)
├── tests/
│   ├── conftest.py             # fixtures compartilhadas
│   ├── fixtures/               # sample.html, sample.pdf, scanned.pdf
│   └── test_*.py               # pytest suite
├── output/                     # gitignored — .md gerados
├── pyproject.toml
├── .env.example
└── README.md
```

## Limitações conhecidas (v1)

- **Sem OCR:** PDFs escaneados (página = imagem) retornam erro 422.
- **Sem batch:** uma fonte por requisição; sem fila.
- **Imagens ignoradas:** o `.md` gerado contém só texto; figuras dos PDFs
  não são extraídas nem descritas.
- **Sem autenticação:** é uma ferramenta local single-user. Não expor
  na internet.
- **Desktop only:** UI não é otimizada para mobile.
- **Não escreve no vault:** por design, o `.md` fica em `./output/` e o
  usuário move manualmente. Evita colisões e dá revisão antes da
  ingestão.
- **Sites dinâmicos (SPA) não suportados:** Docling não executa
  JavaScript.

## Roadmap (v2+)

- **OCR** para PDFs escaneados (via Tesseract ou o pipeline próprio do
  Docling).
- **Extração de imagens** com descrição textual gerada por LLM
  (CLIP/BLIP/GPT-4V).
- **Deploy online** — HuggingFace Spaces ou Fly.io, com autenticação.
- **Batch** (múltiplas URLs de uma vez).
- **Integração direta com o vault** (modo opcional, após
  configuração explícita).

## Testes

```bash
pytest          # roda toda a suíte (~15s, offline — Docling é mockado)
ruff check backend tests       # linter
ruff format --check backend tests  # formatador
```

A suíte inteira roda em <60s em máquina de desenvolvimento típica
(alvo Story 1.6 AC5). Testes que invocam o Docling real (pesados) são
marcados com `@pytest.mark.slow` e excluídos por default; rodar
explicitamente com `pytest -m slow`.

## License

MIT.
