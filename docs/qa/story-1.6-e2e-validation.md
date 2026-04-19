# Story 1.6 — Manual E2E Validation Checklist

> **AC7:** O autor executa manualmente 5 fluxos reais de ponta a ponta
> (3 tipos de fonte + fallback de path + 1 caso de erro) e confirma que
> cada um produz o resultado esperado.

Rodar o servidor antes de iniciar:

```bash
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Abrir <http://127.0.0.1:8000>. Para cada fluxo, anotar `[x]` no checklist
e, se algo desviou do esperado, registrar na seção **Observações**
abaixo.

## Fluxo 1 — URL HTML (artigo público)

- Exemplo sugerido: `https://en.wikipedia.org/wiki/Markdown` ou um post de blog
- [ ] Resposta aparece em `#result` sem reload (HTMX)
- [ ] Arquivo criado em `./output/<slug>.md`
- [ ] Frontmatter YAML válido com `note_type: literature_document`,
      `generated_by: docling`, `source_type: url_html`, URL preservada,
      `extracted_at`, `created`
- [ ] `source_title` corresponde ao `<title>` da página
- [ ] Corpo markdown não-vazio, sem tags `<img>` nem `![...](...)`
      (v1 ignora imagens)

## Fluxo 2 — URL PDF remoto (paper público)

- Exemplo sugerido: qualquer PDF público pequeno (<10 MB) — arXiv,
  IETF RFC, etc. Ex: `https://arxiv.org/pdf/1706.03762v7.pdf`
- [ ] Download acontece (olho no console do uvicorn)
- [ ] Arquivo criado em `./output/<slug>.md`
- [ ] Frontmatter com `source_type: url_pdf` e URL original
- [ ] Corpo markdown tem as seções do paper (abstract, etc.)

## Fluxo 3 — Upload PDF via drag-and-drop

- Usar um PDF próprio pequeno (qualquer PDF com texto — pode ser um
  recibo, um livro scan com OCR, um artigo)
- [ ] Drag-and-drop dispara a conversão automaticamente (sem precisar
      clicar `Extract`)
- [ ] Arquivo criado em `./output/<slug>.md`
- [ ] Frontmatter com `source_type: pdf_upload` e `original_filename`
- [ ] Corpo markdown corresponde ao conteúdo do PDF

## Fluxo 4 — `local_path` fallback

- Usar o "Copy as path" do Windows Explorer (ou equivalente) em um PDF
  local. Colar no campo `local_path` (inclusive com aspas — o backend
  strip-a).
- [ ] Campo aceita tanto `C:\...\file.pdf` quanto `"C:\...\file.pdf"`
- [ ] Arquivo criado em `./output/<slug>.md`
- [ ] Frontmatter com `source_type: pdf_local_path` e o caminho resolvido

## Fluxo 5 — Caso de erro

Escolher UM dos dois:

### 5a — URL 404

- Ex: `https://example.com/pagina-que-nao-existe-404`
- [ ] Aparece `result-card--error` em `#result`
- [ ] HTTP status do envelope é 502
- [ ] `code`: `SOURCE_FETCH_FAILED`
- [ ] `message` claro (menciona a URL ou o status 404)
- [ ] `hint` preenchido

### 5b — PDF scanned (sem OCR)

- Usar um PDF com páginas só-imagem (scan antigo sem OCR)
- [ ] Aparece `result-card--error` em `#result`
- [ ] HTTP status do envelope é 422
- [ ] `code`: `CONVERSION_FAILED`
- [ ] `message` menciona "OCR is not enabled in v1"
- [ ] Nenhum `.md` criado em `./output/` para este caso (erro antes do
      `save`)

## Observações

- **2026-04-19 — Timeout real observado com PDF grande (fora do checklist):**
  autor tentou converter um PDF denso de 7,3 MB (livro do Christopher
  Alexander, ~100 páginas) via Flow 3. Com `REQUEST_TIMEOUT_SECONDS=300`
  no `.env`, o request ficou pendurado por >5 min. O PDF é legitimamente
  pesado para Docling em CPU — fora do escopo da v1, bom candidato para
  o backlog E-001 (GPU acceleration). Após `Ctrl+C` + restart do
  `uvicorn` e troca para PDFs menores, todos os 5 fluxos rodaram
  normalmente. Isto **não é um defeito** — é limitação conhecida
  documentada no README (seção Limitações v1 + Troubleshooting).

---

**Data de execução:** 2026-04-19
**Executado por:** Vinicius Bispo (autor)
**Verdict:** [x] PASS  [ ] ISSUES FOUND

Todos os 5 fluxos (URL HTML, URL PDF remoto, upload PDF,
`local_path` fallback, caso de erro) executaram com sucesso usando
PDFs pequenos conforme recomendado pelo checklist.
