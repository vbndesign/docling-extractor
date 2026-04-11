# Framework de Conhecimento Pessoal
*Sistema de gestão e síntese de conhecimento baseado em Zettelkasten + Obsidian*

---

## Visão Geral

Este framework é uma infraestrutura intelectual pessoal — não um arquivo, não uma biblioteca. É um ambiente vivo onde conhecimento externo, interpretação pessoal e experiência prática se acumulam, se conectam e se tornam consultáveis ao longo do tempo.

A lógica central é de **camadas progressivas de elaboração**: o conhecimento entra bruto, é fragmentado em unidades com identidade própria, é interpretado na voz do autor, e eventualmente se organiza em visões de domínio e registros de aplicação real.

A navegação acontece pelos **links semânticos entre notas**, não pela hierarquia de pastas. As pastas são trilhos operacionais. O grafo é o conhecimento.

---

## Princípios do Sistema

**Atomicidade** — cada nota trata de uma única ideia. Notas longas que cobrem múltiplos conceitos perdem capacidade de conexão.

**Fidelidade de camada** — cada tipo de nota tem uma função específica e não acumula funções de outra camada. A mistura dilui o valor de cada tipo.

**Voz progressiva** — o conhecimento externo entra sem interpretação. A voz do autor aparece gradualmente, sendo plena apenas nas Permanent Notes e acima.

**Captura sem fricção** — nenhuma ideia deve ser perdida por falta de estrutura no momento. O Inbox existe para isso.

**Revisão como prática** — o sistema só funciona com ritual periódico de processamento. Sem revisão, o Inbox vira cemitério e as conexões param de crescer.

**Navegação por metadados, não por pastas** — nas camadas de conhecimento, a organização acontece via links, tags e campos YAML, não por subpastas de domínio. Uma Permanent Note pode pertencer a múltiplos domínios simultaneamente — qualquer subpasta seria uma hierarquia falsa que oculta conexões reais. Subpastas são reservadas para a camada operacional `/40`, que é Top-Down por natureza.

**Nota isolada como sinal intelectual** — uma Permanent Note sem conexões não é uma falha de organização. É um sinal que merece atenção: ou o conhecimento ainda não amadureceu o suficiente para revelar suas conexões, ou a nota foi criada de forma ampla demais e precisa ser quebrada em algo mais atômico. A ausência de conexão é o sistema funcionando — ele força a pergunta *com o que isso se conecta?*, que é exatamente o processo cognitivo que instala o conhecimento na memória de longo prazo.

---

## Estrutura de Pastas

```
/00 - Inbox

/10 - Literatura
    /10.1 - Documentos
    /10.2 - Conceitos

/20 - Permanent Notes

/30 - Síntese
    /30a - MOC
    /30b - Experiências

/40 - Operacional
    /40a - Clientes
        /[Nome do Cliente]
            /[Nome do Projeto]
    /40b - Negócio
        /Comercial
        /Financeiro
        /Posicionamento
        /Processos
        /Projetos Internos
            /[Nome do Projeto Interno]
```

---

## As Camadas e suas Funções

---

### Inbox `/00`
**Pergunta que responde:** *O que eu preciso não perder agora?*

Zona de captura bruta. Recebe qualquer tipo de conteúdo sem exigência de formato, links ou categorização. Pode ser um insight, uma observação de campo, uma conexão que surgiu numa conversa, uma ideia ainda não desenvolvida.

A única regra do Inbox é ser revisitado periodicamente. Cada nota ali tem três destinos possíveis: vira Permanent Note, vira Experiência, ou é descartada.

O Inbox é a entrada de todo conhecimento que nasce da experiência própria — aquilo que não vem de fonte externa, mas de síntese interna em tempo real.

**Formato:** livre. Sem template.

---

### Documento / Trecho `1.1` — `/10/10.1`
**Pergunta que responde:** *O que essa fonte diz, integralmente?*

Documento Markdown gerado a partir de uma fonte externa — apostila, artigo, capítulo de livro, página web. O texto é da fonte. A contribuição do autor é a seleção (o que vale extrair) e os metadados (de onde vem). A conversão para Markdown é feita via script Python com a biblioteca Docling, e o arquivo resultante entra diretamente nesta camada — não existe etapa intermediária de armazenamento.

Um mesmo livro pode gerar múltiplos documentos 1.1, um por capítulo ou trecho relevante. Todos linkam de volta para a mesma origem nos metadados. Fontes sem documento digital — como livros físicos — geram uma nota de referência simples dentro desta mesma camada, contendo apenas os metadados de origem para fins de linkagem.

Esta camada existe para que o autor nunca precise reabrir a fonte original para consultar o que ela disse. O 1.1 é o arquivo de referência — não é para navegar, é para existir e ser citado.

**Metadados obrigatórios:** fonte, autor, ano, localização (capítulo, página, URL).

---

### Nota de Conceito `1.2` — `/10/10.2`
**Pergunta que responde:** *Qual é a unidade atômica de conhecimento que essa fonte contém?*

Fragmento ainda fiel à fonte, mas com identidade própria. Um conceito específico extraído do 1.1 e promovido a nó independente. O texto ainda é da fonte — sem interpretação — mas a nota tem nome, domínio, e começa a criar links com outros conceitos da mesma camada.

Um único 1.1 pode gerar múltiplos 1.2. A decisão de o que merece virar nó próprio é o primeiro filtro intelectual do sistema — e precisa ser do autor, não delegada.

Os links entre notas 1.2 são descritivos: "esse conceito é pré-requisito para aquele", "esses dois conceitos aparecem juntos na fonte", "esses dois autores tratam o mesmo conceito de formas diferentes".

**Metadados obrigatórios:** fonte (link para o 1.1 de origem), domínio, links para outros 1.2 relacionados.

---

### Permanent Note `2` — `/20`
**Pergunta que responde:** *O que eu penso sobre esse conceito?*

Primeira camada em voz própria. O autor escreve sua interpretação de um conceito atômico — sem resumir a fonte, sem descrever o que o livro disse. A nota responde o que o autor entende, onde discorda, como aquilo se conecta com outro conhecimento que já possui.

A Permanent Note não exige fonte externa. Ideias originais, insights lapidados a partir do Inbox e reflexões próprias também vivem aqui — são tão válidas quanto notas derivadas de literatura. A diferença está no campo de origem, não na estrutura da nota.

A Permanent Note parte do 1.2 quando tem origem externa, ou do Inbox quando tem origem própria. Em ambos os casos vai além do ponto de partida: pode conectar conceitos de fontes diferentes, pode tensionar autores, pode registrar uma dúvida ainda não resolvida.

É escrita para ser lida no futuro pelo próprio autor — deve fazer sentido fora de contexto, sem depender da memória do momento em que foi escrita.

**Metadados obrigatórios:** origem, links para os 1.2 que embasam (quando houver), links para outras Permanent Notes relacionadas, domínio.

O campo origem tem três valores possíveis:
- `fonte externa` — nota derivada de literatura, embasada por 1.2
- `ideia própria` — nasceu do Inbox, sem fonte externa
- `misto` — ideia própria que se conecta com conceitos externos sem ter vindo deles

---

### MOC — Mapa de Conteúdo `3a` — `/30/30a`
**Pergunta que responde:** *Como eu entendo esse domínio como um todo?*

Nota de nível superior que agrega Permanent Notes de um mesmo domínio ou tema. Não é índice — é um texto argumentativo escrito pelo autor que explica como os conceitos se relacionam, onde há tensão, o que ainda está em aberto.

O MOC é o estado atual do entendimento do autor sobre um domínio. Ele evolui conforme novas Permanent Notes são criadas e linkadas.

Os links dentro do MOC não são apenas referências — são acompanhados de uma frase que explica o papel de cada conceito na visão geral.

**Estrutura:** texto argumentativo + lista de conceitos centrais com papel explicitado + questões em aberto.

---

### Experiência `3b` — `/30/30b`
**Pergunta que responde:** *Como esse conhecimento apareceu na prática?*

Registro de uma situação real onde conceitos do sistema foram ativados. Ancora o abstrato no concreto e cria evidência da evolução do autor ao longo do tempo.

A Experiência é o tipo de nota mais rico em conexões: linka Permanent Notes que foram ativadas, linka MOCs que guiaram a abordagem, e frequentemente gera novas Permanent Notes — insights que não vieram de nenhuma fonte, mas da prática.

Pode ser originada de um projeto profissional, de uma conversa relevante, de uma decisão tomada. O critério é: houve ativação de conhecimento que merece ser registrada?

**Fluxo bidirecional:** a nota de Experiência permanece sempre na camada 3b — sua posição no sistema não muda. O que é bidirecional é o fluxo de conhecimento que ela gera.

Ao escrever uma Experiência, você ativa conceitos existentes e os linka — esse é o fluxo esperado, de cima pra baixo. Mas ao escrever, você frequentemente percebe algo que nenhuma nota do sistema ainda captura: um insight que nasceu da prática, não de nenhuma fonte externa. Esse insight não tem casa ainda.

Esse insight vai para o Inbox. A partir do Inbox, é processado e vira uma Permanent Note nova — que pode ser linkada de volta à Experiência que o originou e potencialmente influenciar um MOC existente.

A prática não só consome o que está no sistema. Ela também produz conhecimento novo que alimenta o sistema de volta.

```
3b Experiência
[ao escrever, surge insight que nenhuma nota ainda captura]
        ↓
     Inbox
[captura bruta do insight, sem estrutura]
        ↓
  2 Permanent Note
[insight processado, em voz própria]
        ↓
[linka de volta à 3b que o originou + alimenta MOC existente]
```

**Estrutura:** contexto da situação + conceitos ativados (com links e observação de como apareceram) + o que a prática revelou que ainda não estava em nenhuma nota.

---

### Operacional `40` — `/40`
**Pergunta que responde:** *O que precisa ser executado e rastreado?*

Camada Top-Down. Abriga documentos operacionais de execução — não são conhecimento, são contexto. Organizada em dois universos distintos:

**Clientes `/40a`** — um diretório por cliente ou projeto. Contém escopo, cronograma, briefings, decisões, referências externas e entregas. O conhecimento gerado a partir de um projeto de cliente não fica aqui — ele entra no framework via Inbox e se torna patrimônio permanente do sistema.

**Negócio `/40b`** — documentos do próprio negócio, organizados por área funcional contínua (Comercial, Financeiro, Posicionamento, Processos) e por projetos internos pontuais. Segue a mesma lógica dos projetos de clientes: o operacional fica aqui, o conhecimento gerado vai para o framework.

**A ponte com o framework:** quando conceitos são aplicados num contexto operacional, uma nota 3b Experiência é criada em `/30b`. Ela linka as Permanent Notes ativadas e referencia o projeto ou área de origem. Na pasta operacional, fica apenas um link para essa Experiência — o conhecimento vive no sistema, não na pasta do projeto.

```
/40 - Operacional/40a - Clientes/Projeto X
    → link para [[3b - Experiência Projeto X]]

/30 - Síntese/30b - Experiências
    → [[3b - Experiência Projeto X]]
        → linka [[Permanent Note A]], [[Permanent Note B]]
        → referencia /40a - Clientes/Projeto X
```

---

## O Fluxo Completo

O sistema tem dois fluxos de entrada — conhecimento externo (fontes) e conhecimento próprio (experiência e insights) — e uma camada operacional paralela que consome e gera conhecimento, mas não o armazena.

```
ENTRADA EXTERNA                        ENTRADA PRÓPRIA
───────────────                        ───────────────
Fonte (PDF, livro, artigo, web)        Experiência vivida / Insight
        ↓                                      ↓
   1.1 Documento                            Inbox
   [extração fiel]                    [captura bruta, sem estrutura]
        ↓                                      ↓
   1.2 Nota de Conceito               [processamento periódico]
   [fragmentação atômica]                      ↓
        └──────────────┬───────────────────────┘
                       ↓
               2 Permanent Note
               [interpretação própria]
                       ↓
            ┌──────────┴──────────┐
            ↓                    ↓
         3a MOC            3b Experiência
    [visão de domínio]     [aplicação real]
                                  ↑  ↓
                         /40 Operacional
                    ┌─────────────────────────┐
                    │ /40a Clientes            │
                    │ /40b Negócio             │
                    │   Comercial              │
                    │   Financeiro             │
                    │   Posicionamento         │
                    │   Processos              │
                    │   Projetos Internos      │
                    └─────────────────────────┘
                    [gera insights → Inbox → ciclo recomeça]
                    [recebe links ← 3b Experiência]
```

---

## Papel da LLM no Sistema

A LLM é uma ferramenta de apoio, não de delegação. O sistema preserva intencionalmente os processos cognitivos que instalam conhecimento na memória de longo prazo.

| Etapa | Autor | LLM |
|---|---|---|
| Decidir o que extrair do PDF | ✓ | — |
| Propor fragmentação em conceitos | — | ✓ (proposta) |
| Aprovar ou rejeitar fragmentação | ✓ | — |
| Escrever Permanent Notes | ✓ | — |
| Validar raciocínio ou conexões | — | ✓ (confronto) |
| Identificar conexões com notas existentes | — | ✓ (sugestão) |
| Decidir onde o Inbox entry vai parar | ✓ | — |
| Articular o que uma referência visual comunica | — | ✓ (proposta) |
| Interpretar e escrever a nota a partir da imagem | ✓ | — |

---

## Referências Visuais

Imagens não são unidades de conhecimento — são evidências que suportam notas existentes. O conhecimento é o que o autor extrai da imagem e registra na nota que ela apoia.

Referências visuais aparecem em diferentes contextos no sistema, sempre como suporte:

**Em notas de conhecimento** — uma imagem pode ilustrar um conceito de design numa 1.2, evidenciar um argumento numa Permanent Note, ou compor um MOC visual que define uma direção estética ou um conjunto de princípios.

**Em notas operacionais** — dentro de `/40 Operacional`, referências visuais aparecem em briefings, moodboards e registros de decisão visual de projetos. Quando uma decisão visual é tomada num projeto e conecta com conhecimento do sistema, ela entra na Experiência 3b correspondente.

**Com LLMs multimodais** — imagens podem ser passadas diretamente para modelos com visão para articular quais princípios de design estão sendo aplicados ou como um layout resolve um problema específico. Esse output serve como ponto de partida para o autor escrever a Permanent Note em voz própria — a interpretação final é sempre do autor.

Todas as imagens ficam armazenadas em `/assets/imagens` com nomes descritivos. O campo `visual_refs` nos templates identifica quais notas têm suporte visual, permitindo rastreabilidade sem abrir o corpo do documento.

---

## Ritual de Revisão

O sistema exige dois rituais periódicos para permanecer vivo:

**Processamento do Inbox** — frequência sugerida: semanal. Cada nota do Inbox é lida e recebe um destino: Permanent Note, Experiência ou descarte.

**Revisão de MOCs** — frequência sugerida: mensal ou ao concluir um ciclo de estudo. Os MOCs são atualizados para refletir novas Permanent Notes criadas no período e novas questões em aberto identificadas.

---

*Framework desenvolvido em sessão de design de sistema — Abril 2026*
