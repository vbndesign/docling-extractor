# Docling Extractor

Local, single-user tool that converts URLs (HTML / PDF), PDF uploads, and
Word documents (`.docx`) into Markdown files ready for ingestion into an
Obsidian vault. Built on
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

| Variável                  | Default    | Descrição                                                          |
| ------------------------- | ---------- | ------------------------------------------------------------------ |
| `OUTPUT_DIR`              | `./output` | Diretório dos `.md` gerados                                        |
| `MAX_UPLOAD_MB`           | `50`       | Limite de upload (HTTP 413 acima disso)                            |
| `REQUEST_TIMEOUT_SECONDS` | `600`      | Timeout duro por request (HTTP 504 se excede — 10 min cobre PDFs de ~100 páginas) |
| `PDF_CHUNK_SIZE`          | `10`       | Páginas por chunk quando o PDF ultrapassa `PDF_CHUNK_THRESHOLD`    |
| `PDF_CHUNK_THRESHOLD`     | `20`       | Acima deste nº de páginas, o PDF é processado em chunks            |
| `MAX_FAILED_PAGES_RATIO`  | `0.10`     | Fração de páginas falhas aceita antes de `422 CONVERSION_FAILED`   |

**Sobre chunking de PDFs grandes (Story 1.7):** PDFs com mais de
`PDF_CHUNK_THRESHOLD` páginas são divididos em blocos de `PDF_CHUNK_SIZE`
páginas e convertidos bloco-a-bloco. Isso evita um vazamento de memória
nativa no estágio *preprocess* do pypdfium2 (backend do Docling) que
silenciosamente descartava ~90 % das páginas em PDFs de 100+ páginas.
Ajuste `PDF_CHUNK_SIZE` para baixo se você tiver pouca RAM; para cima
para reduzir o overhead de modelo por chunk. Se mais de
`MAX_FAILED_PAGES_RATIO` das páginas falharem, o endpoint retorna
`422 CONVERSION_FAILED`; abaixo disso, o `.md` é gerado com
`partial: true` + `failed_pages: [...]` no frontmatter e a UI destaca
as páginas perdidas.

## Como rodar

Do diretório raiz do projeto:

```bash
# Atalho: sobe o servidor e abre o navegador em http://127.0.0.1:8000
uv run docling-serve

# Acrescente --reload para auto-restart ao editar código
uv run docling-serve --reload

# Equivalente manual (sem abrir o navegador)
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Abrir <http://127.0.0.1:8000> (o `docling-serve` já abre automaticamente).

> ⚠️ O default `--host 127.0.0.1` é localhost-only por segurança (não há
> autenticação). Para expor na LAN, mudar explicitamente para
> `--host 0.0.0.0` e apenas em rede confiável.

## Como usar

A página principal tem três campos de entrada numa única tela, cobrindo
seis modalidades de fonte (Story 1.8):

1. **URL HTML** (artigo web) → campo `url` → `Extract`
2. **URL PDF** (PDF remoto) → campo `url` → `Extract`
3. **Upload PDF** (drag-and-drop ou file picker) → campo `file`
4. **Upload DOCX** (drag-and-drop ou file picker) → campo `file`
5. **Local path PDF** (caminho absoluto para `.pdf`) → campo `local_path`
6. **Local path DOCX** (caminho absoluto para `.docx`) → campo
   `local_path`

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
- **PDFs grandes demoram até ~3 minutos:** PDFs de 100+ páginas passam
  pelo chunking automático (Story 1.7). O timeout default é **10 min**
  (`REQUEST_TIMEOUT_SECONDS=600`). Se o seu workload é ainda maior, suba
  esse valor no `.env`. PDFs pequenos continuam respondendo em <30 s.
- **PDF não gera conteúdo útil:** pode ser um PDF *escaneado* (páginas
  como imagem, sem texto extraível). A v1 **não tem OCR**; o endpoint
  responde `422 CONVERSION_FAILED` com hint "OCR is not enabled in v1".
- **Resposta traz `partial: true` e páginas faltando:** algumas páginas
  do PDF falharam na conversão mas o restante foi recuperado (abaixo do
  `MAX_FAILED_PAGES_RATIO`). O `.md` salvo tem `partial: true` +
  `failed_pages: [...]` no frontmatter; a UI mostra as páginas perdidas
  em um bloco de aviso. Para recusar esses casos em vez de aceitá-los,
  reduza `MAX_FAILED_PAGES_RATIO` (ex: `0.01`).
- **`422 CONVERSION_FAILED: ... over threshold`:** mais de
  `MAX_FAILED_PAGES_RATIO` das páginas falharam; nenhum `.md` é gerado.
  Tente um PDF alternativo da mesma fonte, ou relaxe o threshold.
- **URL não gera conteúdo:** a página pode ser uma SPA com render em
  JavaScript. Docling **não executa JS**; sites dinâmicos como
  `twitter.com`, `app.notion.so` etc. não são suportados na v1.
- **`Address already in use`:** outro `uvicorn` está rodando na porta
  8000. Matar o processo (`taskkill /F /PID <pid>` no Windows,
  `lsof -ti:8000 | xargs kill` no macOS/Linux) ou usar `--port 8001`.
- **`local_path` não aceita seu caminho:** o campo aceita caminhos
  absolutos, inclusive formato com aspas (`"C:\...\file.pdf"`) que o
  "Copy as path" do Windows Explorer produz. O arquivo precisa ser `.pdf`
  ou `.docx` válido (magic bytes corretos) e existir.
- **DOCX com macros (`.docm`) não suportado na v1:** salve como `.docx`
  antes de submeter. Arquivos `.docm` podem ter magic bytes ZIP idênticos
  a `.docx`, mas Docling pode falhar ao interpretar recursos específicos
  de macro — o endpoint responde `422 CONVERSION_FAILED` nesse caso.

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
│   ├── fixtures/               # sample.html, sample.pdf, sample.docx, scanned.pdf
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
  e DOCX não são extraídas nem descritas.
- **Sem autenticação:** é uma ferramenta local single-user. Não expor
  na internet.
- **Desktop only:** UI não é otimizada para mobile.
- **Não escreve no vault:** por design, o `.md` fica em `./output/` e o
  usuário move manualmente. Evita colisões e dá revisão antes da
  ingestão.
- **Sites dinâmicos (SPA) não suportados:** Docling não executa
  JavaScript.
- **Formatos Word legacy fora do escopo:** `.doc` (Word 97-2003 binário),
  `.odt` e `.rtf` não são suportados — use `.docx`. DOCX remoto via URL
  também está fora do escopo v1 (apenas upload ou `local_path`).

> **PDFs grandes (100+ páginas):** suportados desde a Story 1.7 via
> chunking automático. O PRD original (NFR3) citava um limite de ~20
> páginas, mas esse teto foi removido — agora o único limite prático é
> `MAX_UPLOAD_MB` (50 MB por default).

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
