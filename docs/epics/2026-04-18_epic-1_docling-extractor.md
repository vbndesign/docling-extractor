# Epic 1 — Docling Extractor v1 (Local MVP)

> **Epic ID:** 1
> **Status:** Ready for execution (awaiting @sm `*draft` of Story 1.1)
> **Owner:** @pm (Morgan) — delegated to @sm (River) for story drafting
> **PRD de referência:** `docs/prd/docling-extractor-prd.md` v1.3 §6 (authoritative ACs)
> **Arquitetura:** `docs/architecture/2026-04-18_architecture_docling-extractor.md` v1.2
> **Design System:** `docs/architecture/2026-04-18_frontend-spec_docling-extractor.md` v1.1
> **Criado via:** `*shard-prd` em 2026-04-18
> **Execução:** 6 stories estritamente sequenciais; zero paralelismo

---

## 1. Goal

Entregar, de forma incremental, uma ferramenta local com interface browser que aceita URLs (HTML/PDF) e uploads de PDF, converte via Docling, gera arquivo `.md` com frontmatter mínimo no diretório de output e exibe o resultado ao usuário. Ao final do Epic 1, o usuário deve conseguir abrir `http://localhost:8000`, submeter qualquer uma das três modalidades de entrada suportadas, e receber um arquivo `.md` no diretório de output, pronto para ser movido manualmente para o vault Obsidian e completado como nota `1.1 Documento`.

---

## 2. Story Index

| # | Story | Status | ACs | PRD Ref | Dependências | Insumo Primário para Dev Notes |
|---|-------|--------|-----|---------|--------------|-------------------------------|
| 1.1 | Project Scaffolding & Configuration | Ready | 9 | PRD §6 Story 1.1 | — | PRD §4 + arch §9 |
| 1.2 | Core Docling Extraction Service | Ready | 9 | PRD §6 Story 1.2 | 1.1 | arch §5.1, §6.3, §10.1, §2.2 R1/R3 |
| 1.3 | Frontmatter Builder & File Writer | Draft | 9 | PRD §6 Story 1.3 | 1.2 | arch §5.1, §6.3, §2.2 R5–R6 |
| 1.4 | Extraction API Endpoint | Draft | 9 (AC9 new em v1.3) | PRD §6 Story 1.4 | 1.3 | arch §7.2, **§7.3** (AC9), §10.2 |
| 1.5 | Browser Frontend with HTMX | Draft | 9 | PRD §6 Story 1.5 | 1.4 | **frontend-spec v1.1** (canônico) + arch §7.3 |
| 1.6 | QA Hardening & Documentation | Draft | 7 | PRD §6 Story 1.6 | 1.5 | arch §10.4, §12 |
| 1.7 | Large-PDF Chunked Extraction & Partial-Success Visibility | Ready | 9 | Post-v1 bugfix (out-of-PRD) | 1.6 | arch §2.2 R1, §5.1, §10.2–§10.4 + @dev probe report 2026-04-19 |
| 1.8 | DOCX Input Support — Brownfield Addition | Ready | 10 | Post-v1 format expansion (out-of-PRD) | 1.7 | arch §5.1, §6.3, §7.2, §10.1–§10.2 + Story 1.8 Story Context (scope locks) |

**Total:** 8 stories / 71 ACs (Story 1.7 added 2026-04-19 as post-v1 hardening extension; Story 1.8 added 2026-04-24 as post-v1 format-expansion brownfield story — `.docx` input via upload + `local_path`).

**Status lifecycle:** `Draft pending` → `Draft` → `Ready` → `InProgress` → `InReview` → `Done`.
Atualizar esta tabela a cada transição.

---

## 3. Execution Sequence

```
1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 (post-v1 hardening) → 1.8 (post-v1 format expansion)
```

**Regra invariante (PRD §5):** cada story DEVE estar em status `Done` antes da próxima iniciar `*draft`. Justificativa: não há paralelismo real — backend precede frontend, testes precedem QA hardening.

---

## 4. Definition of Done (Epic-level)

Epic 1 é considerado `Done` quando:

- [ ] Todas as 6 stories em status `Done`
- [ ] Todos os 52 ACs do PRD §6 validados
- [ ] Suíte de testes roda em <60s (PRD NFR5 + Story 1.6 AC5)
- [ ] Linter `ruff` passa sem erros (Story 1.6 AC4)
- [ ] `README.md` completo e atualizado (Story 1.6 AC3)
- [ ] QA Gate em `PASS` ou `CONCERNS` — nunca `FAIL` (Story 1.6 AC6)
- [ ] 5 fluxos E2E validados manualmente pelo autor (Story 1.6 AC7)

---

## 5. Handoff Chain

| Timestamp | From | To | Artifact |
|-----------|------|-----|----------|
| 2026-04-11 | @pm (original) | — | PRD v1.0 (draft inicial) |
| 2026-04-18 | @po (Pax) | @pm | PRD v1.1 (M1, M2 resolved) |
| 2026-04-18 | @architect (Aria) | @pm | PRD v1.2 (S1–S4 resolved via arch v1.1) |
| 2026-04-18 14:30 | @ux-design-expert (Uma) | @architect | Frontend-spec questions (dual-format + hint field) |
| 2026-04-18 14:30 | @architect (Aria) | @ux-design-expert | Arch v1.2 + 6 decisions (arch §7.3, §10.2) |
| 2026-04-18 14:45 | @ux-design-expert (Uma) | — | Frontend-spec v1.1 (tokens + 13 primitives) |
| 2026-04-18 15:00 | @pm (Morgan) | @sm | PRD v1.3 + handoff YAML |
| 2026-04-18 15:15 | @pm (Morgan) | — | **Epic 1 sharded (this file)** |
| 2026-04-18 15:45 | @sm (River) | @po | **6 stories drafted** em `docs/stories/1.1`…`1.6` (plural request from user — deviation from PRD §5 strict-sequential-draft invariant). Pronto para `*validate-story-draft` começando pela 1.1. |
| 2026-04-18 | @po (Pax) | @dev | **Story 1.1 validated: GO (10/10, readiness 9.5/10)**. Status Draft → Ready. Ready para `@dev *develop 1.1`. |
| 2026-04-18 | @po (Pax) | @dev | **Story 1.2 validated: GO (10/10, readiness 9.5/10)**. Status Draft → Ready. Should-Fix advisory: AC5 image-absence test assertion (non-blocking). Ready para `@dev *develop 1.2`. |
| 2026-04-19 | @po (Pax) | @dev | **Story 1.7 validated: GO (10/10, readiness 9/10)**. Status Draft → Ready. 3 advisory should-fix items (non-blocking) — ver Change Log da story 1.7. Ready para `@dev *develop 1.7`. |
| 2026-04-24 | @po (Pax) | @dev | **Story 1.8 validated: GO (10/10, readiness 9/10, High confidence)**. Status Draft → Ready. 4 advisory should-fix items (non-blocking) — ver Change Log da story 1.8. Ready para `@dev *develop 1.8`. |

---

## 6. Normative References (per story)

> Veja também `docs/prd/docling-extractor-prd.md` §8 "SM Prompt" — tabela completa com `critical_warnings` por story.

- **`docs/prd/docling-extractor-prd.md` v1.3** — ACs autoritativos (single source of truth)
- **`docs/architecture/2026-04-18_architecture_docling-extractor.md` v1.2** — contratos técnicos (dataclasses, interfaces, `ERROR_CATALOG`, content negotiation)
- **`docs/architecture/2026-04-18_frontend-spec_docling-extractor.md` v1.1** — design tokens + 13 primitivos + HTML skeleton (input principal de Story 1.5)

---

## 7. Out of Scope (v2 deferred)

Conforme PRD §3 e §8 "Next Steps":

- OCR (PDFs escaneados)
- Batch processing (múltiplas fontes por requisição)
- Image extraction com descrições via LLM
- Deploy online (HuggingFace Spaces / Fly.io)
- Autenticação, multi-user, controle de acesso
- Mobile responsive / PWA
- Escrita direta no vault Obsidian (intencional — autor move manualmente)

---

## 8. Risks & Mitigations (inherited from arch §2.2)

| # | Risco | Severidade | Mitigação | Story |
|---|-------|-----------|-----------|-------|
| R1 | Docling CPU-bound vs FastAPI async | HIGH | `asyncio.to_thread` no endpoint | 1.4 |
| R2 | Primeiro boot baixa modelos (~600MB) | MEDIUM | Lifespan singleton + doc no README | 1.1, 1.6 |
| R3 | HEAD request falha silenciosamente | MEDIUM | Fallback magic bytes | 1.2 |
| R7 | `httpx` sem UA/timeout explícitos | MEDIUM | AC9 Story 1.2 (S3 PO) | 1.2 |
| R8 | Binding 0.0.0.0 vs 127.0.0.1 | MEDIUM | Default `127.0.0.1` + doc | 1.1, 1.6 |

Demais riscos (R4, R5, R6, R9) = LOW, mitigados inline nas stories.

---

*Epic shard criado por Morgan (@pm) em 2026-04-18T15:15 via `*shard-prd`. Os ACs permanecem no PRD como single source of truth; este arquivo é o control document de execução (status, progresso, handoff chain, DoD).*
