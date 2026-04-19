# Docling Extractor — Product Requirements Document (PRD)

> **Versão:** 1.3
> **Status:** Approved (pós design system + arquitetura consolidada)
> **Autor:** Morgan (PM) — sessão de planejamento
> **Data:** 2026-04-18
> **Escopo:** v1 local-first MVP

---

## 1. Goals and Background Context

### Goals

- Reduzir ao máximo a fricção de levar conteúdo externo (PDFs, artigos web, páginas HTML) para dentro do vault Obsidian como nota `1.1 Documento` do Framework de Conhecimento Pessoal.
- Manter o output fiel à fonte — sem interpretação, sem fragmentação, sem decisão intelectual automatizada.
- Entregar um fluxo de uso simples o bastante para ser operado várias vezes ao dia em segundos, pelo browser, sem tocar no terminal.
- Produzir arquivos `.md` com frontmatter mínimo e fiel aos metadados reais da fonte, sem preencher campos subjetivos.
- Garantir portabilidade técnica para que, numa v2, o sistema possa ser publicado online em hosting gratuito sem reescrita estrutural.

### Background Context

O Framework de Conhecimento Pessoal do autor é um sistema Zettelkasten em Obsidian com camadas progressivas de elaboração. A primeira camada de entrada externa — `1.1 Documento` em `/10 - Literatura/10.1 - Documentos` — exige que o texto da fonte esteja disponível em Markdown fiel para ser citado pelas camadas superiores sem que a fonte original precise ser reaberta. Hoje esse passo é manual ou ad-hoc, o que cria atrito suficiente para desacelerar o ritual de processamento de fontes.

O framework já define a biblioteca Docling como a ferramenta-padrão de conversão, mas não existe ainda nenhum wrapper operacional sobre ela. Este projeto cria esse wrapper — um serviço local com interface browser simples que aceita URLs e PDFs e devolve um arquivo `.md` pronto para ser movido para o vault. O sistema é deliberadamente estreito: ele **não** interpreta, **não** fragmenta em conceitos 1.2, **não** gerencia o vault. Ele apenas resolve o problema de "a fonte não está em Markdown ainda".

### Change Log

| Date | Version | Description | Author |
|---|---|---|---|
| 2026-04-11 | 1.0 | Draft inicial do PRD | Morgan (PM) |
| 2026-04-18 | 1.1 | Validação PO — fix M1 (Story 1.4/1.5 cross-reference `local_path`) e M2 (renumeração de ACs da Story 1.6); status Draft → Approved | Pax (PO) |
| 2026-04-18 | 1.2 | Revisão arquitetural (Aria) — incorpora should-fixes S1–S4 como ACs delta nas Stories 1.1, 1.2, 1.6. Sem mudança funcional de escopo. | Morgan (PM) |
| 2026-04-18 | 1.3 | Incorpora decisões do design system (Uma, frontend-spec v1.1) + arquitetura consolidada (Aria, arch v1.2): Story 1.4 ganha AC9 (content negotiation HTMX + JSON no endpoint `/extract`). Sem mudança nas demais stories; contratos de erro e rendering passam a ser normativos via arch §7.3 e §10.2. | Morgan (PM) |

---

## 2. Requirements

### Functional

- **FR1:** O sistema DEVE aceitar como entrada: (a) URL de página web HTML, (b) URL de PDF remoto, (c) arquivo PDF local enviado via upload.
- **FR2:** O sistema DEVE usar a biblioteca Docling para converter o conteúdo de entrada em Markdown fiel à fonte, sem interpretação ou reescrita.
- **FR3:** O sistema DEVE gerar um frontmatter YAML mínimo, incluindo **sempre** os campos: `note_type: literature_document`, `created`, `extracted_at`, `location`, `generated_by: docling`.
- **FR4:** O sistema DEVE incluir no frontmatter os campos `source_title`, `author` e `year` **somente quando** a tool conseguir extraí-los com confiança do PDF metadata ou das meta-tags HTML da fonte. Campos não detectados DEVEM ser omitidos do YAML, não deixados como strings vazias.
- **FR5:** O sistema NÃO DEVE preencher os campos `title`, `source_type`, `domain` e `concepts_extracted` — esses são decisões intelectuais do autor e ficam fora do YAML gerado pela tool.
- **FR6:** O sistema DEVE persistir o arquivo `.md` resultante em um diretório de output configurável, separado do vault Obsidian do usuário. A tool não escreve diretamente no vault.
- **FR7:** O sistema DEVE nomear o arquivo de saída automaticamente, seguindo a ordem de prioridade: (1) título detectado nos metadados, (2) nome original do arquivo PDF quando upload local, (3) slug da URL quando web. O nome deve ser slugificado (kebab-case ASCII) e ter extensão `.md`.
- **FR8:** O sistema DEVE expor uma interface HTML no browser com dois modos de entrada: (a) campo para colar URL e (b) área drag-and-drop para upload de arquivo PDF local.
- **FR9:** A interface DEVE oferecer um **fallback** para upload de PDF local via campo de texto aceitando caminho absoluto do arquivo no sistema de arquivos local, quando drag-and-drop não for a preferência do usuário.
- **FR10:** O sistema DEVE exibir feedback de progresso na UI enquanto a extração estiver em andamento (spinner ou estado "processando"), e exibir claramente o caminho do arquivo gerado quando a operação for bem-sucedida.
- **FR11:** O sistema DEVE retornar mensagens de erro claras e acionáveis na UI quando falhar — por exemplo, URL inacessível, arquivo não é PDF válido, tamanho excedido, timeout de conversão.
- **FR12:** O sistema DEVE rejeitar uploads que excedam o limite máximo configurado de tamanho de arquivo (default: 50 MB), retornando erro claro antes de iniciar a conversão.
- **FR13:** O sistema DEVE processar uma fonte por requisição. Batch processing está fora do escopo da v1.
- **FR14:** O sistema DEVE ignorar completamente imagens contidas nas fontes na v1. O Markdown gerado conterá apenas texto e estrutura (títulos, listas, tabelas, parágrafos).

### Non Functional

- **NFR1:** O sistema DEVE rodar inteiramente localmente em máquina Windows com Python 3.11+ sem depender de nenhum serviço externo pago.
- **NFR2:** O sistema DEVE ser stateless: nenhum banco de dados, nenhuma sessão persistente, nenhum histórico de conversões. O único estado em disco é o conjunto transitório de arquivos no diretório de output, que o usuário limpa manualmente.
- **NFR3:** A latência típica de conversão (tempo entre submissão e disponibilização do arquivo) DEVE ser aceitável para uso interativo no browser — alvo: < 30 segundos para fontes típicas (artigo web médio ou PDF de até 20 páginas sem OCR).
- **NFR4:** O sistema DEVE ser arquitetado de forma que a separação backend/frontend permita publicação futura em hosting gratuito (ex: HuggingFace Spaces, Fly.io) na v2, sem exigir reescrita do core.
- **NFR5:** O código DEVE ter cobertura de testes automatizados mínima para os três cenários de entrada (URL HTML, URL PDF, upload PDF local) e para o builder de frontmatter. Testes de integração DEVEM exercitar o fluxo ponta-a-ponta via endpoint HTTP.
- **NFR6:** A primeira execução da tool pode baixar modelos do Docling (aproximadamente algumas centenas de MB). Esse comportamento DEVE ser documentado no README; não é um bug nem um requisito de otimização para v1.
- **NFR7:** O sistema NÃO DEVE implementar autenticação, multi-usuário, controle de acesso ou qualquer mecanismo de segurança de rede na v1 — ele é local e pressupõe acesso confiável a `localhost`.
- **NFR8:** OCR (conversão de PDFs escaneados) está explicitamente fora da v1. O sistema DEVE usar a pipeline padrão do Docling sem habilitação de OCR.

---

## 3. User Interface Design Goals

### Overall UX Vision

Interface mínima, funcional, invisível. O usuário abre a página, cola uma URL ou arrasta um PDF, clica, vê o caminho do arquivo gerado em segundos, fecha. Nenhuma curva de aprendizado, nenhuma configuração por sessão, nenhum ruído visual. O objetivo é que a ferramenta desapareça e o foco do usuário permaneça no ato intelectual de escolher o que extrair — não em operar a tool.

### Key Interaction Paradigms

- **Entrada única por tela:** dois campos de entrada visíveis simultaneamente (URL e upload), ambos disponíveis, sem abas ou estados escondidos.
- **Feedback progressivo:** qualquer operação que demore mais de meio segundo exibe estado "processando" com indicação visual clara.
- **Resultado terminal:** após a conversão, a tela exibe o caminho absoluto do arquivo gerado e um botão/link para abrir o diretório de output no explorador de arquivos (se o navegador permitir).
- **Erros como parte do fluxo:** mensagens de erro aparecem no mesmo espaço onde o resultado apareceria — não em popups nem toasts — e explicam em uma frase o que deu errado.

### Core Screens and Views

- **Tela única `/`** — formulário com campo URL + área de upload drag-and-drop + campo fallback de path local; área de resultado/erro logo abaixo.
- **Endpoint `/health`** — rota técnica para verificar que o serviço está no ar (sem UI).

### Accessibility: None

A v1 não tem requisitos de acessibilidade formais (WCAG), por ser uma ferramenta single-user local. Contraste razoável e navegação por teclado são desejáveis mas não medidos.

### Branding

Sem branding. Estética utilitária, monocromática, com tipografia legível (system font). O visual deve se parecer com uma ferramenta de developer — não com um produto SaaS.

### Target Device and Platforms: Desktop Only

Uso exclusivamente em navegador desktop (Chrome/Firefox/Edge) no mesmo sistema operacional onde o backend está rodando. Não há meta de responsividade mobile na v1.

---

## 4. Technical Assumptions

### Repository Structure: Monorepo

Um único repositório contendo backend FastAPI, frontend estático servido pelo próprio FastAPI, testes e documentação. Não há necessidade de separação multi-repo para esta escala.

### Service Architecture

**Monolito Python local.** Um único processo FastAPI que serve tanto a API REST quanto o HTML estático do frontend. O Docling é invocado inline no mesmo processo — não há worker separado, fila, nem processamento assíncrono complexo. A simplicidade é uma feature.

**Estrutura proposta:**

```
docling-extractor/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + rotas
│   ├── docling_service.py   # wrapper do Docling (URL / PDF remoto / PDF local)
│   ├── frontmatter.py       # mapeia metadata → YAML mínimo
│   ├── file_writer.py       # nomenclatura + persistência no output
│   └── config.py            # output_dir, max_upload_mb, request_timeout
├── frontend/
│   ├── templates/
│   │   └── index.html       # Jinja2 + HTMX
│   └── static/
│       └── style.css
├── tests/
│   ├── fixtures/            # 1 HTML pequeno + 1 PDF curto
│   ├── test_docling_service.py
│   ├── test_frontmatter.py
│   └── test_endpoints.py
├── output/                 # output dir, gitignored
├── pyproject.toml
├── .env.example
└── README.md
```

### Testing Requirements

**Unit + Integration.**

- **Unit tests** para `docling_service.py` (mockando a chamada do Docling quando possível) e para `frontmatter.py` (mapping determinístico de metadados → YAML).
- **Integration tests** para os endpoints FastAPI, cobrindo os 3 cenários de entrada ponta-a-ponta com fixtures reais (1 arquivo HTML mínimo e 1 PDF curto checados no repo).
- **Manual validation** documentada no README para casos que envolvem a rede (URLs reais de artigos web e PDFs remotos) — não fazem parte da suíte automatizada para evitar flakiness.

### Additional Technical Assumptions and Requests

- **Linguagem:** Python 3.11+ (restrição do Docling).
- **Framework backend:** FastAPI + Uvicorn. Preferido por performance, suporte nativo a async, e compatibilidade com a maioria dos free-tier hostings para v2.
- **Frontend:** HTML estático renderizado via Jinja2, interatividade via HTMX, CSS vanilla. Sem build step, sem npm, sem bundler.
- **Gerenciamento de dependências:** `pyproject.toml` + `uv` ou `pip` direto. Sem Poetry.
- **Docling:** usar a API de alto nível (`DocumentConverter`) conforme o exemplo `minimal.py` da documentação oficial. Customizações da pipeline (OCR, imagem, tabelas) ficam desabilitadas na v1 — default Docling é suficiente.
- **HTTP client para URLs remotas:** `httpx` (já usado pelo ecossistema FastAPI).
- **Detecção de tipo de URL:** request HEAD para verificar `Content-Type` antes de escolher pipeline Docling (HTML vs PDF).
- **Controle de versão:** Git local. Push remoto e CI fora do escopo da v1 — serão tratados se a v2 precisar.
- **Qualidade de código:** linter via `ruff`, formatação `ruff format`. Sem pre-commit hooks obrigatórios na v1.

---

## 5. Epic List

A v1 é suficientemente pequena para ser entregue em um único epic com stories sequenciais. Justificativa: splitting em múltiplos epics introduziria overhead de coordenação sem benefício, já que não há paralelismo real entre frentes — o backend precisa existir antes do frontend, e os testes precisam dos dois.

- **Epic 1: Docling Extractor v1 — Local MVP.** Entregar, de forma incremental, uma ferramenta local com interface browser que aceita URLs (HTML/PDF) e uploads de PDF, converte via Docling, gera arquivo `.md` com frontmatter mínimo no diretório de output e exibe o resultado ao usuário, cobrindo todos os requisitos funcionais e não-funcionais da v1.

---

## 6. Epic 1: Docling Extractor v1 — Local MVP

> **📌 Epic shard:** Esta seção foi sharded via `*shard-prd` em 2026-04-18 para `docs/epics/2026-04-18_epic-1_docling-extractor.md`. O arquivo do epic é o **control document** (status, progresso, DoD, handoff chain). **Os ACs abaixo permanecem aqui como single source of truth** — o epic referencia por link, nunca duplica.

**Goal:** Entregar em 6 stories sequenciais um MVP totalmente funcional da ferramenta de extração, do scaffolding inicial até a UI browser com tratamento de erros e testes de integração. Ao final do Epic 1, o usuário deve conseguir abrir `http://localhost:8000`, submeter qualquer uma das três modalidades de entrada suportadas, e receber um arquivo `.md` no diretório de output, pronto para ser movido manualmente para o vault Obsidian e completado como nota `1.1 Documento`.

### Story 1.1: Project Scaffolding & Configuration

As a solo developer setting up the project,
I want a minimal FastAPI application skeleton with config, folder structure, and a health endpoint,
so that I have a reliable foundation to iterate on without fighting plumbing.

**Acceptance Criteria:**

1. Repositório inicializado com a estrutura de pastas definida em Technical Assumptions (`backend/`, `frontend/`, `tests/`, `output/`).
2. `pyproject.toml` declara Python 3.11+ e as dependências diretas **com limites superiores de versão** (S2): `fastapi>=0.110,<0.120`, `uvicorn[standard]>=0.27,<0.31`, `docling>=2.0,<3.0`, `httpx>=0.27,<0.28`, `jinja2>=3.1,<4.0`, `python-multipart>=0.0.9,<0.1`, `pyyaml>=6.0,<7.0`, `python-slugify>=8.0,<9.0`, mais dev-deps `pytest>=8.0,<9.0`, `pytest-asyncio`, `ruff>=0.4,<0.5`. Os ranges permitem patches sem drift de major/minor.
3. `backend/config.py` define constantes/env vars para `OUTPUT_DIR` (default `./output`), `MAX_UPLOAD_MB` (default 50), `REQUEST_TIMEOUT_SECONDS` (default 60).
4. `backend/main.py` expõe app FastAPI com endpoint `GET /health` retornando `{"status": "ok"}` e status 200.
5. `uvicorn backend.main:app` sobe sem erros e o `/health` responde corretamente em browser/curl.
6. `.gitignore` exclui `output/`, `__pycache__/`, `.venv/`, `.env`.
7. `.env.example` documenta as variáveis de configuração disponíveis.
8. `README.md` inicial cobre: pré-requisitos (Python 3.11+), instalação, como rodar o servidor, como checar o `/health`.
9. Repositório inicializado com `git init` + commit inicial incluindo `.gitignore`, `.env.example` e toda a estrutura de pastas base (S1). Mensagem do commit segue conventional commits (ex: `chore: initial project scaffolding`).

### Story 1.2: Core Docling Extraction Service

As the backend,
I want a unified service function that accepts any of the 3 input types (HTML URL, PDF URL, local PDF file) and returns a tuple of (markdown_body, raw_metadata),
so that the upper layers of the app (endpoints, writer) have a single clean interface to Docling regardless of source type.

**Acceptance Criteria:**

1. `backend/docling_service.py` expõe uma função pública `extract(source)` que aceita: (a) string URL para página HTML, (b) string URL para PDF remoto, (c) caminho local ou file-like object para PDF local.
2. A função detecta o tipo de input (HEAD request para URLs + checagem de Content-Type; detecção de extensão/MIME para arquivos locais) e roteia para a pipeline apropriada do Docling.
3. Retorna um dataclass ou dict com duas chaves: `markdown` (string com o conteúdo Markdown puro gerado pelo Docling) e `metadata` (dict com os campos detectados — ex: `source_title`, `author`, `year` — omitindo os não detectados).
4. Usa a API `DocumentConverter` do Docling conforme o exemplo `minimal.py` oficial, sem customizações de pipeline. OCR desabilitado.
5. Imagens dentro das fontes são ignoradas — o Markdown gerado contém apenas texto e estrutura.
6. Testes unitários em `tests/test_docling_service.py` usam fixtures (`tests/fixtures/sample.html` e `tests/fixtures/sample.pdf`) pequenas e commitadas no repo, exercitando os 3 caminhos.
7. Testes cobrem o caso de sucesso para cada tipo e pelo menos um caso de falha explícita (ex: arquivo corrompido retorna exception bem definida).
8. A função lança exceptions tipadas (ex: `SourceFetchError`, `ConversionError`) em vez de deixar vazar exceptions genéricas do Docling — isso prepara o tratamento de erro nas camadas superiores.
9. Cliente HTTP externo (`httpx`) usado para fetch de URLs remotas está configurado com (S3): (a) header `User-Agent: docling-extractor/1.0` identificável, (b) timeout total de 30 segundos com `connect_timeout` de 10 segundos, (c) seguir redirects HTTP com limite de 5 hops. Essas configurações são aplicadas via `httpx.AsyncClient` instanciado no nível da aplicação.

### Story 1.3: Frontmatter Builder & File Writer

As the backend,
I want a deterministic component that takes (markdown_body, metadata, source) and produces a final `.md` file written to the output dir with the correct filename and frontmatter,
so that the output always respects the "minimum frontmatter" rule and naming convention without ambiguity.

**Acceptance Criteria:**

1. `backend/frontmatter.py` expõe função `build(metadata, source, now) -> str` que retorna o YAML frontmatter como string (delimitado por `---`).
2. Os seguintes campos DEVEM sempre estar presentes no YAML gerado: `note_type: literature_document`, `created` (YYYY-MM-DD), `extracted_at` (ISO 8601 com timezone), `location` (URL ou nome do arquivo original), `generated_by: docling`.
3. Os seguintes campos DEVEM estar presentes **somente se** vieram preenchidos no dict `metadata`: `source_title`, `author`, `year`. Se ausentes, omitir completamente — nunca incluir como string vazia, null ou placeholder.
4. Os campos `title`, `source_type`, `domain`, `concepts_extracted` **nunca** são gerados pela tool.
5. Valores com caracteres especiais (aspas, colons, caminhos Windows com barras invertidas) são corretamente escapados no YAML usando `yaml.safe_dump` ou equivalente.
6. `backend/file_writer.py` expõe função `save(frontmatter_str, markdown_body, metadata, source, output_dir) -> Path` que: (a) concatena `frontmatter_str + "\n" + markdown_body`, (b) deriva o nome do arquivo pela ordem de prioridade definida em FR7, (c) aplica slug kebab-case ASCII, (d) escreve no `output_dir`, (e) retorna o Path absoluto do arquivo criado.
7. Se um arquivo com o mesmo nome já existir no output, o writer adiciona sufixo numérico incremental (`-2`, `-3`) em vez de sobrescrever silenciosamente.
8. Testes unitários em `tests/test_frontmatter.py` cobrem: todos os campos condicionais presentes, todos ausentes, combinações mistas, e verificação de que campos proibidos nunca aparecem.
9. Testes do file_writer cobrem as 3 origens de nome (title, filename, URL slug) e o caso de colisão com sufixo incremental.

### Story 1.4: Extraction API Endpoint

As a frontend client,
I want a single HTTP endpoint that accepts either a URL or a multipart file upload and triggers the full extraction + write pipeline,
so that the UI can submit any of the 3 input types through one clean JSON contract.

**Acceptance Criteria:**

1. `backend/main.py` expõe `POST /extract` aceitando `multipart/form-data` com **três campos opcionais mutuamente exclusivos**: `url` (string), `file` (upload) ou `local_path` (string — caminho absoluto para PDF no sistema de arquivos local, atendendo ao fallback FR9).
2. O endpoint valida que exatamente um dos três campos foi fornecido — retorna HTTP 400 com mensagem clara se zero, dois ou três estiverem presentes. Para `local_path`, valida adicionalmente que o caminho existe, é legível e corresponde a um arquivo PDF (extensão `.pdf` ou MIME `application/pdf`); falhas retornam HTTP 400 com mensagem acionável.
3. Uploads excedendo `MAX_UPLOAD_MB` retornam HTTP 413 com mensagem clara. A verificação acontece antes de a conversão iniciar.
4. A rota integra, na ordem: `docling_service.extract` → `frontmatter.build` → `file_writer.save`, e retorna JSON `{"status": "ok", "output_path": "<absolute path>", "filename": "<basename>"}` com HTTP 200 em sucesso.
5. Exceptions tipadas da camada de serviço são mapeadas para respostas HTTP claras: `SourceFetchError` → 502, `ConversionError` → 422, qualquer outra → 500. Todas incluem mensagem textual acionável.
6. Timeout global por requisição respeitando `REQUEST_TIMEOUT_SECONDS` do config; excedê-lo retorna 504 com mensagem clara.
7. Testes de integração em `tests/test_endpoints.py` cobrem, via `TestClient` do FastAPI, os **4 cenários de sucesso** (URL HTML, URL PDF, upload PDF local, `local_path`) e os casos de erro (sem input, múltiplos inputs simultâneos, upload oversized, URL inacessível, `local_path` inexistente, `local_path` apontando para arquivo não-PDF).
8. Para cada caso de sucesso no teste, o arquivo é efetivamente criado no output dir (fixture aponta para diretório temporário) e o conteúdo é validado: frontmatter correto + corpo não-vazio.
9. O endpoint `POST /extract` aplica content negotiation via header `Accept`: se o cliente preferir `text/html` (HTMX default) e não preferir `application/json`, retorna partial Jinja2 (`frontend/templates/partials/result_success.html` em sucesso; `frontend/templates/partials/result_error.html` em erro, com status HTTP apropriado). Caso contrário, retorna o JSON definido em AC4/AC5. O handler global de exceptions respeita a mesma regra (referência normativa: arch doc §7.3 + §10.2). Testes cobrem: (a) `Accept: text/html` retorna HTML em sucesso e em erro; (b) ausência de `Accept` retorna JSON (preserva contrato AC4); (c) `Accept: application/json` retorna JSON.

### Story 1.5: Browser Frontend with HTMX

As a user of the tool,
I want a single-page browser interface where I can paste a URL or drop a PDF file and see the result without ever leaving the page or touching the terminal,
so that the tool integrates seamlessly into my daily knowledge-processing ritual.

**Acceptance Criteria:**

1. `backend/main.py` expõe `GET /` renderizando `frontend/templates/index.html` via Jinja2.
2. `index.html` apresenta, em uma única tela: (a) input de texto com label "URL (página web ou PDF remoto)" + botão "Extrair", (b) área drag-and-drop visível para upload de PDF, (c) abaixo das áreas de drag-and-drop, um campo de texto expansível rotulado "ou cole o caminho absoluto do arquivo local" como fallback (FR9), (d) área vazia reservada para resultado/erro.
3. O arquivo `frontend/static/style.css` contém estilização minimalista, monocromática, system font, layout centralizado, sem dependência de framework CSS externo.
4. Os formulários usam HTMX (`hx-post="/extract"`, `hx-swap="innerHTML"`, `hx-target="#result"`) para submeter via AJAX e atualizar a área de resultado sem reload da página.
5. Durante a requisição, um indicador de progresso ("Processando...") aparece na área de resultado usando `hx-indicator`.
6. Em sucesso, a área de resultado mostra: o nome do arquivo gerado, o caminho absoluto (copiável), e um atalho visual para o diretório de output (pode ser apenas o path em destaque — não precisa abrir o explorador).
7. Em erro, a área de resultado mostra a mensagem HTTP recebida do backend em estilo visualmente distinto (cor diferente ou borda), sem popup/toast.
8. O fallback de path local (item 2c) submete o conteúdo do campo como o form field `local_path` do endpoint `/extract` (já definido em Story 1.4 AC1), apresentando o resultado na mesma área de resultado/erro dos outros dois modos de entrada, sem divergência visual.
9. Validação manual: o fluxo completo funciona em Chrome e Firefox em Windows, para os 3 tipos de entrada + o fallback de path.

### Story 1.6: QA Hardening & Documentation

As the owner of the tool,
I want the v1 finalized with integration tests, corner case handling, and a complete README,
so that I can rely on the tool daily without surprises and can return to it in months without needing to re-learn how it works.

**Acceptance Criteria:**

1. Testes de integração cobrem explicitamente os seguintes corner cases, todos com expectativas bem definidas: (a) URL web que retorna 404, (b) URL web que retorna HTML vazio ou quase-vazio (SPA não-renderizada), (c) PDF sem texto (página totalmente imagem, simulando o caso que não será suportado por falta de OCR), (d) arquivo enviado que não é PDF válido, (e) upload excedendo `MAX_UPLOAD_MB`, (f) timeout na conversão.
2. Para o caso (c) PDF sem texto, o sistema retorna um erro claro orientando o usuário de que OCR não está habilitado na v1, em vez de produzir um arquivo vazio.
3. `README.md` é atualizado com seções: Visão geral, Pré-requisitos, Instalação, Como rodar, Como usar (passo a passo com screenshots opcionais; inclui menção ao Swagger UI automático em `http://127.0.0.1:8000/docs` para inspeção do endpoint `/extract` — S4), Troubleshooting (primeira execução baixando modelos, PDFs sem texto, URLs dinâmicas não suportadas), Estrutura do projeto, Limitações conhecidas da v1, Roadmap de v2 (OCR, extração de imagens com descrição via LLM, deploy online).
4. Linter `ruff check backend tests` passa sem erros; `ruff format --check` passa sem alterações pendentes.
5. Toda a suíte de testes (`pytest`) roda em menos de 60 segundos em máquina de desenvolvimento típica.
6. QA Gate rodado por `@qa` retorna verdict PASS ou CONCERNS (não FAIL).
7. O autor executa manualmente 5 fluxos reais de ponta a ponta (3 tipos de fonte + fallback de path + 1 caso de erro) e confirma que cada um produz o resultado esperado.

---

## 7. Checklist Results Report

**PO Master Checklist (executado em 2026-04-18 por Pax):**

- **Classificação do projeto:** Greenfield com UI/UX
- **Overall readiness:** 87% → **CONDITIONAL APPROVAL** → **APPROVED** (após correções M1 e M2 aplicadas em v1.1)
- **Critical blockers:** 0
- **Must-fix resolvidos em v1.1:**
  - **M1** — Endpoint `/extract` agora contempla o 3º input `local_path` diretamente em Story 1.4 AC1/2/7; Story 1.5 AC8 deixa de ser retroativa.
  - **M2** — ACs da Story 1.6 renumerados de 1–7 (gap de AC2 eliminado).
- **Should-fix resolvidos em v1.2 (via revisão arquitetural de Aria):**
  - ✅ **S1** — Story 1.1 ganhou AC9: `git init` + commit inicial com `.gitignore`, `.env.example` e estrutura base.
  - ✅ **S2** — Story 1.1 AC2 atualizado com version ranges (`>=X,<Y`) para todas as dependências — trava majors/minors, libera patches.
  - ✅ **S3** — Story 1.2 ganhou AC9: `httpx.AsyncClient` com User-Agent identificável, timeout 30s (connect 10s), redirect limit 5.
  - ✅ **S4** — Story 1.6 AC3 atualizado: seção "Como usar" do README menciona Swagger UI em `/docs`.
- **Resolvido em v1.3 (design system + arquitetura consolidada):**
  - ✅ **Story 1.4 AC9** — Content negotiation (HTMX HTML partial + JSON default) formalizado no endpoint `/extract`. Referência normativa: `docs/architecture/2026-04-18_architecture_docling-extractor.md` §7.3.
  - ✅ **Frontend spec publicado** — `docs/architecture/2026-04-18_frontend-spec_docling-extractor.md` v1.1: 13 primitivos, design tokens, HTML skeleton, contratos HTMX. Passa a ser o insumo canônico de Dev Notes da Story 1.5.
  - ✅ **Error envelope formalizado** — `{status, code, message, hint}` sempre presente; `hint` obrigatório, resolvido via `ERROR_CATALOG` em `backend/errors.py`. Referência: arch §10.2.
- **Seções puladas legitimamente:** 1.2, 2.1 (DB), 3.1, 3.3, 7 (Brownfield Risk). Nota: a §3 original pulou o design system formal, mas a v1.3 passa a referenciar o frontend-spec como norma não-formal de design para Story 1.5.

*Relatório completo disponível no histórico da conversa de validação.*

**PM Checklist:** *pendente — será executado por `@pm *checklist` se solicitado antes da fase de implementação.*

---

## 8. Next Steps

### Architect Prompt

@architect — este PRD define uma aplicação Python local monolítica (FastAPI + HTMX + Docling) com 6 stories sequenciais em um único epic. O escopo técnico é deliberadamente pequeno e a arquitetura está praticamente toda decidida (veja seção 4 — Technical Assumptions). Sua tarefa, se necessária, é revisar as decisões técnicas para validar que: (a) a pipeline Docling está corretamente abstraída em `docling_service.py` sem vazar para as camadas superiores, (b) o tratamento de exceptions tipadas entre service e endpoint está consistente, (c) o contrato do endpoint `/extract` é extensível para a v2 sem reescrita estrutural. Se concordar com as decisões como estão, confirme e libere para @sm iniciar o `*draft` da Story 1.1.

### SM Prompt

@sm — PRD v1.3 aprovado e consolidado com as seguintes referências normativas (usar em Dev Notes ao fazer `*draft` de cada story):

| Story | Referências obrigatórias em Dev Notes |
|-------|----------------------------------------|
| 1.1 | PRD §4 Technical Assumptions; arch doc §9 Source Tree |
| 1.2 | arch doc §5.1 (dataclasses), §6.3 (interface contracts), §10.1 (exception hierarchy) |
| 1.3 | arch doc §5.1 (SourceDescriptor, ExtractedMetadata), §6.3 (contratos `build`/`save`) |
| 1.4 | arch doc §7.2 (JSON contract), **§7.3 (content negotiation — AC9)**, §10.2 (ERROR_CATALOG) |
| 1.5 | **`docs/architecture/2026-04-18_frontend-spec_docling-extractor.md` v1.1** (insumo canônico: tokens, primitivos, HTML skeleton, partials Jinja); arch §7.3 (Accept header) |
| 1.6 | arch §10.4 (corner case table); PRD §6 Story 1.6 ACs |

Inicie `*draft` da **Story 1.1: Project Scaffolding & Configuration**. Stories são sequenciais — nenhuma deve ser iniciada antes da anterior estar em status `Done`. Preserve integralmente os acceptance criteria deste PRD; eles são a fonte autoritativa do "definition of done". Quando chegar à Story 1.5, o frontend-spec substitui "improvisar UX" — copie/referencie os 13 primitivos (§5 do spec) como checklist dentro do arquivo da story.

---

*PRD v1.3 — sessão de planejamento original pelo PM (Morgan); consolidações de design (Uma) + arquitetura (Aria) aplicadas em 2026-04-18 via handoffs documentados em `.aiox/handoffs/`.*
