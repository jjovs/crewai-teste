# crewai-teste

Exemplo simples de [CrewAI](https://github.com/crewAIInc/crewAI) com dois agentes:

- **Pesquisador**: busca informações sobre um tema.
- **Redator**: transforma essas informações em um resumo de 3 parágrafos.

O projeto usa a API da Anthropic (Claude) como LLM, via a variável de ambiente `ANTHROPIC_API_KEY`.

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

## Como rodar

```bash
python main.py "Tema que você quer pesquisar"
```

Se nenhum tema for passado como argumento, o script usa um tema padrão ("Inteligência Artificial na educação").

O resultado final (resumo de 3 parágrafos) é exibido no terminal ao final da execução.

## Como funciona

1. O agente **Pesquisador** recebe o tema e levanta os principais fatos e pontos relevantes.
2. O agente **Redator** recebe essa pesquisa como contexto e escreve um resumo de exatamente 3 parágrafos.
3. O `Crew` executa as duas tarefas em sequência (`Process.sequential`) e retorna o resultado final.

Por padrão, o modelo usado é o `claude-opus-4-8`. Para trocar de modelo, edite a linha `llm = LLM(model="anthropic/claude-opus-4-8")` em `main.py`.