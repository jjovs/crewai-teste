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
# modo proposta: Iris e Theo entregam especificação, Lila e Rui simulam a sessão
python rodar_equipe.py "melhorar a descoberta de avaliações no feed"

# modo completo: edição de código real + app rodando
python rodar_equipe.py "onboarding do primeiro post" \
    --repo ../rede-social \
    --ui src/components src/styles \
    --url-app http://localhost:3000
```

| Opção | Efeito |
|-------|--------|
| `--repo` | Raiz do projeto alvo. Sem ela, Íris e Theo trabalham em modo proposta |
| `--ui` | Diretórios que Íris e Theo podem editar — funciona como cerca; nada é escrito fora |
| `--url-app` | App rodando. Sem ela, Lila e Rui simulam a sessão |
| `--rodadas` | Quantas vezes a Vera pode devolver antes de encerrar (padrão 3) |
| `--porta` | Porta do painel (padrão 8777) |
| `--demo` | Aciona o painel com dados falsos, sem chamar a API |

Quando falta configuração, `Config.validar()` avisa e a rodada **degrada em vez de quebrar** — modo proposta e modo simulação são caminhos legítimos, não erros.

## Estado da implementação

Pronto e verificado contra o CrewAI 1.15.11:

- os seis agentes, o fluxo com loop de revisão e os contratos Pydantic
- o painel: métricas por agente a partir de eventos reais do barramento, servidor SSE e interface

Ainda **não** implementado, porque depende do repositório alvo:

- **ferramentas de código** para Íris e Theo (leitura/escrita cercada em `--ui`, branch + PR)
- **ferramentas de navegador** para Lila e Rui (Playwright ou API do app, autenticação, dados de teste)

Sem essas duas peças o time roda em modo proposta/simulação, que já produz pauta, design especificado, sessão simulada e parecer da Vera.
