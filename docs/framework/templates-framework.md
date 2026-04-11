# Templates do Framework de Conhecimento Pessoal
*Referência para criação de notas no Obsidian*

---

> **Como usar este arquivo**
> Cada seção contém um template completo com YAML frontmatter e estrutura de corpo.
> Copie o template correspondente ao tipo de nota que você vai criar.
> Campos marcados com `# obrigatório` não podem ficar vazios.
> Campos marcados com `# opcional` podem ser omitidos se não houver valor relevante.

---

## Template 1 — Inbox

```yaml
---
note_type: inbox
created: YYYY-MM-DD
context: "" # obrigatório | de onde veio: conversa, leitura, observação, sessão de trabalho, etc.
status: unprocessed # valor fixo ao criar | não alterar manualmente
---
```

```markdown
[Escreva aqui o que precisa não perder. Sem estrutura, sem formatação obrigatória. 
Pode ser uma frase, um parágrafo, um fragmento de ideia.]
```

---

**Regras de processamento:**
Ao revisar o Inbox, substitua `status: unprocessed` por um dos valores abaixo e mova a nota para o destino correto:

| Status | Destino |
|---|---|
| `promoted_to_permanent` | `/20 - Permanent Notes` |
| `promoted_to_experience` | `/30 - Síntese/30b - Experiências` |
| `discarded` | Apagar a nota |

---

## Template 2 — Documento 1.1

```yaml
---
note_type: literature_document
created: YYYY-MM-DD
title: "" # obrigatório | título do documento, capítulo ou trecho
source_title: "" # obrigatório | título completo da obra de origem
source_type: "" # obrigatório | apostila | artigo | livro | pagina_web | curso | outro
author: "" # obrigatório | nome do autor ou autores
year: YYYY # obrigatório | ano de publicação ou acesso
location: "" # obrigatório | capítulo, páginas, URL ou seção
domain: [] # obrigatório | lista de domínios: ex. [ux, pesquisa, liderança, design]
generated_by: docling # valor fixo para documentos gerados via script
concepts_extracted: [] # opcional | links para os 1.2 gerados a partir deste documento
---
```

```markdown
[Conteúdo Markdown gerado pelo Docling a partir da fonte original.
Texto fiel à fonte — sem interpretação, sem alteração de conteúdo.
Formatação pode ser ajustada para legibilidade, mas o conteúdo é da fonte.]
```

---

**Nota para fontes sem documento digital:**
Livros físicos ou fontes inacessíveis digitalmente geram uma nota 1.1 simplificada — apenas o frontmatter preenchido, sem corpo de texto. O campo `generated_by` deve ser omitido.

---

## Template 3 — Nota de Conceito 1.2

```yaml
---
note_type: literature_concept
created: YYYY-MM-DD
title: "" # obrigatório | nome do conceito — deve ser específico e autoexplicativo
source_document: "" # obrigatório | link para o 1.1 de origem [[nome-do-documento]]
source_title: "" # obrigatório | título da obra de origem (para leitura rápida sem abrir o link)
author: "" # obrigatório | autor da fonte
domain: [] # obrigatório | lista de domínios: ex. [ux, pesquisa, liderança, design]
related_concepts: [] # opcional | links para outros 1.2 relacionados [[conceito-a]], [[conceito-b]]
relationship_notes: "" # opcional | descrição textual de como os conceitos relacionados se conectam
---
```

```markdown
## Definição

[Texto fiel à fonte descrevendo o conceito. Pode ser longo — o conceito tem começo, meio e fim.
Sem interpretação própria. Sem julgamento. A voz é da fonte.]

## Contexto na Fonte

[Opcional. Em que contexto esse conceito aparece na obra? 
É um conceito central ou secundário? Aparece em que parte do argumento do autor?]
```

---

## Template 4 — Permanent Note

```yaml
---
note_type: permanent_note
created: YYYY-MM-DD
updated: YYYY-MM-DD
title: "" # obrigatório | enunciado da ideia em forma de afirmação ou pergunta — não apenas um substantivo
origin: "" # obrigatório | fonte_externa | ideia_propria | misto
domain: [] # obrigatório | lista de domínios: ex. [ux, pesquisa, liderança, design]
source_concepts: [] # obrigatório se origin = fonte_externa ou misto | links para os 1.2 que embasam
related_notes: [] # opcional | links para outras Permanent Notes relacionadas
moc: [] # opcional | links para MOCs onde esta nota está referenciada
status: active # active | archived | draft
---
```

```markdown
## Ideia

[Escreva em primeira pessoa e em voz própria. Esta nota deve fazer sentido 
quando lida no futuro sem depender da memória do momento em que foi escrita.
Responda: o que você pensa sobre isso? Onde discorda? Como conecta com outro conhecimento?
Não resuma a fonte — vá além dela.]

## Conexões

[Opcional. Descreva em prosa como esta nota se conecta com outras Permanent Notes 
ou conceitos do sistema. Não é lista de links — é raciocínio sobre as conexões.]

## Questões em Aberto

[Opcional. O que ainda não está resolvido no seu entendimento sobre isso?
Dúvidas, tensões, contradições que merecem investigação futura.]
```

---

## Template 5 — MOC (Mapa de Conteúdo)

```yaml
---
note_type: moc
created: YYYY-MM-DD
updated: YYYY-MM-DD
title: "" # obrigatório | nome do domínio ou tema agregado
domain: [] # obrigatório | lista de domínios cobertos por este MOC
permanent_notes: [] # obrigatório | links para todas as Permanent Notes referenciadas
related_mocs: [] # opcional | links para outros MOCs que se conectam com este
status: active # active | archived
---
```

```markdown
## Visão do Domínio

[Texto argumentativo escrito em voz própria. Explique como você entende este domínio
como um todo — não liste conceitos, construa um argumento.
Este texto deve evoluir conforme novas Permanent Notes são adicionadas ao MOC.]

## Conceitos Centrais

[Para cada Permanent Note referenciada, uma linha explicando seu papel neste domínio.
Formato: [[Nome da Nota]] — [por que ela é central aqui e como se relaciona com as demais]]

## Tensões e Divergências

[Opcional. Onde os conceitos deste domínio se contradizem ou tensionam entre si?
Onde autores diferentes divergem? Essas tensões são o terreno mais fértil para insights.]

## Questões em Aberto

[O que ainda não está resolvido no seu entendimento deste domínio?
O que falta estudar? Que perguntas este mapa ainda não consegue responder?]
```

---

## Template 6 — Experiência 3b

```yaml
---
note_type: experience
created: YYYY-MM-DD
title: "" # obrigatório | nome do projeto, situação ou evento
context_type: "" # obrigatório | projeto_cliente | projeto_interno | decisao | conversa | outro
operational_ref: "" # opcional | link para pasta ou documento em /40 - Operacional
activated_notes: [] # obrigatório | links para Permanent Notes ativadas nesta experiência
activated_mocs: [] # opcional | links para MOCs que guiaram a abordagem
domain: [] # obrigatório | lista de domínios envolvidos
generated_insights: [] # opcional | links para novas Permanent Notes geradas a partir desta experiência
status: active # active | archived
---
```

```markdown
## Contexto

[Descreva a situação real — o que era o projeto ou evento, qual era o desafio,
quem estava envolvido, qual era o objetivo. Sem julgamento ainda — apenas contexto.]

## Conceitos Ativados

[Para cada Permanent Note linkada no frontmatter, descreva como ela apareceu na prática.
Formato: [[Nome da Nota]] — [como esse conceito se manifestou nesta situação concreta]]

## O que a Prática Revelou

[O que você aprendeu que não estava em nenhuma nota do sistema antes desta experiência?
Esses insights são candidatos a novas Permanent Notes — registre-os aqui antes de processá-los.]

## Resultado

[Opcional. Qual foi o desfecho? O conhecimento aplicado funcionou como esperado?
O que faria diferente? Esta seção ancora a evolução do autor ao longo do tempo.]
```

---

## Referência Rápida — Valores Controlados

### `note_type`
| Valor | Template |
|---|---|
| `inbox` | Inbox |
| `literature_document` | Documento 1.1 |
| `literature_concept` | Nota de Conceito 1.2 |
| `permanent_note` | Permanent Note |
| `moc` | MOC |
| `experience` | Experiência 3b |

### `origin` (Permanent Note)
| Valor | Significado |
|---|---|
| `fonte_externa` | Derivada de literatura, embasada por 1.2 |
| `ideia_propria` | Nasceu do Inbox, sem fonte externa |
| `misto` | Ideia própria conectada a conceitos externos |

### `status`
| Valor | Aplicável a |
|---|---|
| `unprocessed` | Inbox |
| `promoted_to_permanent` | Inbox (após processamento) |
| `promoted_to_experience` | Inbox (após processamento) |
| `discarded` | Inbox (após processamento) |
| `draft` | Permanent Note em construção |
| `active` | Permanent Note, MOC, Experiência |
| `archived` | Permanent Note, MOC, Experiência obsoletos |

### `source_type` (Documento 1.1)
`apostila` · `artigo` · `livro` · `pagina_web` · `curso` · `outro`

### `context_type` (Experiência 3b)
`projeto_cliente` · `projeto_interno` · `decisao` · `conversa` · `outro`

---

## Convenção de Referências Visuais

Imagens não têm template próprio — são evidências que suportam notas existentes. Uma imagem sozinha não é conhecimento: o conhecimento é o que você extrai dela e registra na nota que ela apoia.

**Armazenamento:** todas as imagens ficam em `/assets/imagens`. O Obsidian pode ser configurado para mover anexos automaticamente para essa pasta. O nome do arquivo deve ser descritivo: `hierarquia-visual-exemplo-apple.jpg` é melhor que `screenshot-001.jpg`.

**Inserção na nota:**
```markdown
![[nome-da-imagem.jpg]]
```

**Onde imagens aparecem em cada template:**

| Template | Quando usar imagem | Onde inserir |
|---|---|---|
| 1.2 Nota de Conceito | Ilustrar o conceito descrito | Após a Definição |
| Permanent Note | Evidenciar o argumento próprio | Após o trecho que a imagem suporta |
| MOC | Referências visuais que definem um estilo ou direção | Seção própria "Referências Visuais" |
| Experiência 3b | Decisões visuais tomadas no projeto | Dentro de "Conceitos Ativados" ou "Resultado" |
| Operacional /40 | Briefings, moodboards, entregas visuais | Livre — sem convenção rígida |

**Uso com LLMs:** imagens anexadas a notas podem ser passadas diretamente para modelos multimodais. O fluxo recomendado é passar a imagem com a pergunta *"que princípios de design essa referência aplica?"* ou *"como esse layout resolve o problema de hierarquia?"*, revisar a resposta, e escrever a Permanent Note em voz própria a partir desse ponto de partida. O processo cognitivo de interpretação permanece seu — a LLM acelera a articulação inicial.

**Campo opcional nos templates que suportam imagem:**
```yaml
visual_refs: [] # opcional | lista de nomes de arquivo: [imagem-a.jpg, imagem-b.jpg]
```
Adicione este campo ao frontmatter de qualquer nota que contenha referências visuais relevantes. Isso permite que uma LLM identifique quais notas têm suporte visual sem precisar abrir o corpo do documento.

---

*Templates gerados em sessão de design de sistema — Abril 2026*
