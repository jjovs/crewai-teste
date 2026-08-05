# Equipe de agentes — evolução de interface

Time de seis agentes nomeados que trabalha em rodadas sobre um projeto de rede social de avaliação de experiências. Diferente do exemplo editorial (`main.py`), aqui há **loop de revisão**: a chefe pode devolver o trabalho.

## O time

| Nome | Papel | Escopo exclusivo |
|------|-------|------------------|
| **Caio** | Caçador de Ideias | Extrai princípios de BeReal, Instagram e Letterboxd e propõe aplicações |
| **Vera** | Chefe e Revisora | Define a pauta com critérios de aceite; aprova ou devolve com correções |
| **Iris** | Diretora de Interface | Estrutura, navegação, hierarquia, estados de tela (vazio/carregando/erro) |
| **Theo** | Diretor Visual | Cor, tipografia, espaçamento, ritmo, micro-interações |
| **Lila** | Persona ativa | 24 anos, posta muito, com pressa, quer resposta |
| **Rui** | Persona lurker | 31 anos, lê tudo, quase nunca publica — o usuário que redes sociais perdem em silêncio |

Íris e Theo têm escopos que **não se cruzam** de propósito: dois agentes editando o mesmo arquivo é colisão garantida. Quando um precisa de algo do outro, registra pendência em vez de decidir sozinho.

## Fluxo

```
Caio (ideias) → Vera (pauta) → Iris + Theo (design) → Lila + Rui (sessão)
                                    ↑                        ↓
                                    └──── devolve ──── Vera (revisa)
                                                             ↓
                                                        aprova → entrega
```

Implementado com `crewai.flow`: `@router` emite `"refazer"` e a etapa de design escuta `or_(definir_pauta, "refazer")`.

> **Cuidado ao mexer:** se mais de um método escutar `"refazer"`, a etapa dispara duas vezes por rodada. Foi exatamente esse bug que apareceu no primeiro teste do loop.

## Painel ao vivo

```bash
python rodar_equipe.py --demo     # aciona o painel sem gastar API
```

O painel (`http://localhost:8777`) mostra um cartão por agente, atualizando via SSE:

- estado (ocioso / trabalhando / concluído / erro), tarefa e ferramenta atuais
- tempo trabalhado, execuções, tokens de entrada/saída, erros
- **aprovação de primeira** pela Vera — a métrica que realmente mede desempenho
- atritos encontrados, para Lila e Rui
- linha do tempo da rodada

Não instrumenta nada dentro dos agentes: o `role` de cada um começa pelo nome próprio, e todo evento do CrewAI carrega `agent_role`. Trocar um nome em `equipe/agentes.py` troca o nome no painel.

Servidor em biblioteca padrão (`http.server` + SSE), sem FastAPI nem uvicorn.

## Como rodar

```bash
# ConnoSr, modo proposta (padrão): leem o código, não editam nada
python rodar_equipe.py "fazer o feed parecer vivo no primeiro acesso" \
    --projeto connosr --repo ../connosr

# ConnoSr, modo código: Íris e Theo editam os arquivos de verdade
python rodar_equipe.py "onboarding do primeiro post" \
    --projeto connosr --repo ../connosr --modo codigo

# projeto qualquer, cercas na mão
python rodar_equipe.py "melhorar a descoberta de avaliações" \
    --repo ../outro-projeto --ui src/components src/styles \
    --url-app http://localhost:3000
```

### Modo proposta vs modo código

O padrão é `--modo proposta`, e ele **não** significa trabalhar às cegas: Íris e Theo mantêm as ferramentas de leitura (`listar`, `ler`, `buscar`) e são instruídos a conferir o código antes de propor. A ferramenta de escrita simplesmente não é construída — não há o que dar errado. Proposta que cita o arquivo e o trecho exato vale muito mais que proposta genérica.

`--modo codigo` acrescenta `escrever_arquivo`, sempre dentro da cerca.

| Opção | Efeito |
|-------|--------|
| `--projeto connosr` | Aplica o preset do ConnoSr (cercas, URL, login) |
| `--modo` | `proposta` (padrão) ou `codigo` |
| `--repo` | Raiz do projeto alvo. Sem ela, Íris e Theo propõem sem ver o código |
| `--ui` | Diretórios que Íris e Theo podem editar — funciona como cerca; nada é escrito fora |
| `--ui-iris` / `--ui-theo` | Cercas separadas por designer (ver abaixo) |
| `--url-app` | App rodando. Sem ela, Lila e Rui simulam a sessão |
| `--rodadas` | Quantas vezes a Vera pode devolver antes de encerrar (padrão 3) |
| `--porta` | Porta do painel (padrão 8777) |
| `--demo` | Aciona o painel com dados falsos, sem chamar a API |

Quando falta configuração, `Config.validar()` avisa e a rodada **degrada em vez de quebrar** — modo proposta e modo simulação são caminhos legítimos, não erros.

## A cerca

O projeto alvo pertence a outra pessoa, então as ferramentas de código de Íris e Theo são cercadas: toda leitura e escrita resolve o caminho real (`Path.resolve()`) e é recusada se cair fora dos diretórios autorizados. Testado contra `../`, caminho absoluto, `..` no meio do caminho e **symlink apontando para fora** — todos recusados. O que a leitura recusa também não aparece na listagem.

Cada designer tem a **sua própria** cerca e o **seu próprio** registro:

```bash
--ui-iris src/components --ui-theo src/styles
```

Com isso a divisão de escopo deixa de ser instrução no prompt e vira regra técnica: Íris não alcança os arquivos do Theo nem por engano. E como o registro de escrita é por instância, dá para saber quem tocou o quê — o `arquivos_tocados` de cada entrega vem do registro da ferramenta, não do auto-relato do agente, que pode se enganar.

Sem `--ui`, nenhuma escrita é permitida. É o padrão: a cerca é opt-in.

## As personas no app de verdade

Lila e Rui interagem dentro do app rodando, cada uma com **login próprio**. É o que permite a Lila publicar uma avaliação e o Rui encontrar aquele post no feed dele e comentar.

Ferramentas de cada persona: `abrir_pagina`, `ver_tela`, `clicar`, `preencher`, `rolar`. Viewport de celular (390×844) — é assim que se usa uma rede social.

Detalhe técnico que custou um bug: **um único Chromium, um contexto por persona**. Chamar `sync_playwright().start()` duas vezes no mesmo processo morre com *"Sync API inside the asyncio loop"*. Contexto do Playwright já isola cookies e storage, então cada persona tem sessão de login real de verdade.

```bash
pip install playwright && playwright install chromium
```

Sem Playwright instalado, `sessoes_de_navegador` devolve `None` e as personas caem em modo simulação. Se você já tem um Chromium em outro lugar, aponte `PLAYWRIGHT_EXECUTABLE_PATH` para ele em vez de baixar outro.

## Preset do ConnoSr

`Config.para_connosr(repo)` já vem configurado para o projeto:

| | |
|---|---|
| Cerca do **Theo** | `apps/web/src/components`, `packages/ui/src` |
| Cerca da **Íris** | `apps/web/src/pages`, `apps/web/src/layouts` |
| App | `http://localhost:5173` |
| Login | placeholders `Email` / `Senha`, botão `Entrar`, rota `/login` |
| Personas | Lila = `alice@example.com`, Rui = `bruno@example.com` (usuários de seed) |

A divisão por pasta, e não por "estrutura vs visual", é deliberada: no ConnoSr os estilos são objetos inline dentro dos componentes, então não existe fronteira de arquivo entre layout e aparência. Separando por pasta, os dois trabalham em paralelo sem se sobrescrever.

## Estado da implementação

Pronto e verificado contra o CrewAI 1.15.11:

- os seis agentes, o fluxo com loop de revisão e os contratos Pydantic
- o painel: métricas por agente a partir de eventos reais do barramento, servidor SSE e interface
- as ferramentas de código cercadas (listar, ler, buscar, escrever com diff)
- as ferramentas de navegador, verificadas com duas personas logadas em contextos separados: Lila publicou e Rui viu o post dela

Ainda **não** implementado:

- **branch + PR** ao fim da rodada — depende de acesso de escrita ao repositório alvo e da convenção que o time usa

Nunca foi executada uma rodada real de ponta a ponta: isso consome API da Anthropic e o app alvo precisa estar no ar. O que está verificado é cada peça isoladamente, contra o CrewAI e o Playwright de verdade.
