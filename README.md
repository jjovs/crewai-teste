# crewai-teste

Um time de **7 agentes de IA** ([CrewAI](https://github.com/crewAIInc/crewAI)) que produz conteúdo editorial de ponta a ponta — do briefing à versão publicável, com auditoria de fatos e crítica adversarial pelo caminho.

O projeto usa a API da Anthropic (Claude) como LLM, via a variável de ambiente `ANTHROPIC_API_KEY`.

## O time

| # | Agente | Responsabilidade | Entrega |
|---|--------|------------------|---------|
| 1 | **Estrategista de Conteúdo** | Transforma um tema vago em recorte específico: público, ângulo, perguntas-chave, estrutura e critérios de aprovação | `BriefingEditorial` |
| 2 | **Pesquisador Sênior** | Responde cada pergunta-chave com fatos e números, declarando confiança, origem, controvérsias e lacunas | `DossieDePesquisa` |
| 3 | **Auditor de Fatos** | Julga afirmação por afirmação (verificado / plausível / duvidoso / não verificável) e decide o que pode ser publicado | `RelatorioDeAuditoria` |
| 4 | **Redator** | Escreve o artigo seguindo a estrutura do briefing, usando **apenas** material aprovado pela auditoria | Artigo em Markdown |
| 5 | **Especialista em Descoberta e SEO** | Título, meta description, slug, palavras-chave e chamada para redes — dentro dos limites reais de caracteres | `PacoteDeDescoberta` |
| 6 | **Crítico Adversarial** | Ataca o texto: conclusões frágeis, generalizações, ressalvas ignoradas, contra-argumentos ausentes | `RelatorioDeCritica` |
| 7 | **Editor-Chefe** | Integra SEO e críticas, confere os critérios de sucesso e assina a versão publicável | Documento final + notas do editor |

Cada etapa intermediária devolve um objeto **Pydantic** (ver `models.py`), não texto livre. Isso obriga cada agente a entregar exatamente o que o próximo espera, e deixa o resultado de cada etapa inspecionável pelo código.

## Fluxo

```
1. briefing     Estrategista
        ↓
2. pesquisa     Pesquisador Sênior          ← 1
        ↓
3. auditoria    Auditor de Fatos            ← 1, 2
        ↓
4. redação      Redator                     ← 1, 2, 3
        ↓
   ┌────┴────┐   (executam em paralelo)
5. seo      6. crítica
   Especialista   Crítico Adversarial
   ← 1, 4         ← 1, 3, 4
   └────┬────┘
        ↓
7. fechamento   Editor-Chefe                ← tudo
```

As etapas 5 e 6 dependem só do texto do redator e não dependem uma da outra, então rodam em paralelo (`async_execution=True`). O editor-chefe espera as duas.

## Pré-requisitos

- Python 3.10+
- Uma chave de API da Anthropic ([console.anthropic.com](https://console.anthropic.com))

## Instalação

```bash
# Criar e ativar um ambiente virtual (opcional, mas recomendado)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Instalar dependências
pip install -r requirements.txt
```

## Configuração

### Caminho rápido (Windows)

`preparar_e_rodar.ps1` faz tudo de uma vez: atualiza o repositório, pede a chave
e grava no `.env`, cria o `.venv`, instala as dependências, clona o ConnoSr,
confirma que o `python-dotenv` realmente carregou a chave e dispara a rodada.
Cada etapa é idempotente — rodar de novo não refaz o que já está pronto.

```powershell
.\preparar_e_rodar.ps1              # prepara e roda
.\preparar_e_rodar.ps1 -SoPreparar  # só prepara, sem gastar API
```

O passo a passo manual, para quem preferir, é o resto desta seção.

### Manual

Crie um arquivo `.env` na raiz do projeto com sua chave da Anthropic:

```
ANTHROPIC_API_KEY=sk-ant-sua-chave-aqui
```

Alternativamente, defina a variável de ambiente diretamente no terminal:

```bash
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-sua-chave-aqui"

# Linux/Mac
export ANTHROPIC_API_KEY="sk-ant-sua-chave-aqui"
```

Os dois métodos acima são de máquina local — o `.env` está no `.gitignore` e o
`$env:` vale só para aquele terminal. Em uma sessão do Claude Code na web, nenhum
dos dois alcança o container: lá a chave se define nas variáveis de ambiente do
*environment* remoto ([documentação](https://code.claude.com/docs/en/claude-code-on-the-web)).

### Variáveis opcionais

| Variável | Efeito |
|----------|--------|
| `CREWAI_MODELO` | Troca o modelo do time (padrão: `anthropic/claude-sonnet-5`) |
| `SERPER_API_KEY` | Ativa busca web real no Pesquisador (requer `pip install crewai-tools`) |
| `CREWAI_TEMPERATURA` | `0` nunca envia `temperature` à API, `1` sempre. Sem ela, o projeto decide pelo modelo — a família Claude 5 recusa o parâmetro |

Sem `SERPER_API_KEY`, o time roda normalmente usando apenas o conhecimento do modelo — e o Pesquisador é instruído a marcar a origem como `conhecimento do modelo`, o que faz o Auditor de Fatos exigir ressalvas no texto em vez de fingir que houve checagem.

## Como rodar

```bash
python main.py "Tema que você quer trabalhar"
```

Com opções:

```bash
python main.py "Reforma tributária" \
  --publico "contadores de pequenas empresas" \
  --tom "técnico, mas sem juridiquês" \
  --palavras-chave "reforma tributária, split payment, IBS" \
  --saida artigos/reforma.md
```

| Opção | Padrão |
|-------|--------|
| `tema` (posicional) | `"Inteligencia Artificial na educacao"` |
| `--publico` | público geral sem formação técnica na área |
| `--tom` | informativo, direto e acessível |
| `--palavras-chave` | nenhuma obrigatória |
| `--saida` | `saida/<slug>-<data>.md` |
| `--silencioso` | mostra só o resultado, sem o passo a passo dos agentes |

## Saída

O documento final é impresso no terminal e salvo em Markdown (por padrão em `saida/`, que é ignorado pelo git). Ele contém:

1. **Bloco de metadados** — título, slug, meta description, palavras-chave, público, tom, contagem de palavras.
2. **Artigo final** — já com as correções da crítica aplicadas.
3. **Notas do editor** — prestação de contas: critérios de sucesso atendidos ou não, críticas aplicadas, críticas descartadas *com a justificativa*, afirmações que ainda precisam de fonte externa e lacunas de pesquisa em aberto.

## Arquivos

| Arquivo | Conteúdo |
|---------|----------|
| `main.py` | CLI e ponto de entrada |
| `crew.py` | Montagem do `Crew` |
| `agents.py` | Os 7 agentes (papel, objetivo, backstory) |
| `tasks.py` | As 7 tarefas e como se encadeiam |
| `models.py` | Esquemas Pydantic das saídas estruturadas |
