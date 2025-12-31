# Auto Download Estratégia Concursos

Ferramenta para baixar automaticamente os materiais dos cursos do Estratégia Concursos.

## Requisitos

- Python 3.10+
- Google Chrome instalado
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes Python)

## Instalação

```bash
# Instalar dependências com uv
uv sync
```

## Uso

```bash
# Executar com uv
uv run python main.py

# Especificar diretório de download
uv run python main.py -d /caminho/para/downloads

# Ajustar tempo de espera para login (padrão: 60 segundos)
uv run python main.py -w 120

# Resetar progresso e começar do início
uv run python main.py --reset
```

## Argumentos

| Argumento           | Descrição                             | Padrão                   |
| ------------------- | ------------------------------------- | ------------------------ |
| `-d`, `--dir`       | Diretório onde os cursos serão salvos | `~/Downloads/Estrategia` |
| `-w`, `--wait-time` | Tempo em segundos para login manual   | `60`                     |
| `-r`, `--reset`     | Ignora o progresso salvo e recomeça   | `false`                  |

## Retomada Automática

O script salva o progresso em `.progress.json` dentro do diretório de download. Se o script for
interrompido, basta executá-lo novamente e ele continuará de onde parou.

## Como Funciona

1. O script abre o Chrome e navega para a página de login
2. Você faz o login manualmente no navegador
3. Após o tempo de espera, o script baixa automaticamente todos os materiais dos seus cursos

## Licença

MIT
