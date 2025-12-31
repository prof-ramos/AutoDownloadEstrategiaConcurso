# Auto Download Estratégia Concursos

Baixador automático de cursos do Estratégia Concursos com anti-detecção e downloads paralelos.

## ✨ Funcionalidades

- 🛡️ **Anti-detecção** — SeleniumBase UC Mode evita bloqueios
- ⚡ **Downloads paralelos** — Até 3 downloads simultâneos
- 🔄 **Retry automático** — Backoff exponencial em caso de falha
- 📊 **Barras de progresso** — tqdm com visual colorido
- 💾 **Retomada automática** — Salva progresso e continua de onde parou

## Requisitos

- Python 3.10+
- Google Chrome instalado
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes Python)

## Instalação

```bash
uv sync
```

## Uso

```bash
# Executar normalmente
uv run python main.py

# Especificar diretório de download
uv run python main.py -d /caminho/para/downloads

# Ajustar tempo de espera para login (padrão: 60s)
uv run python main.py -w 120

# Resetar progresso
uv run python main.py --reset

# Desativar downloads paralelos
uv run python main.py --no-parallel
```

## Argumentos

| Argumento           | Descrição                          | Padrão                   |
| ------------------- | ---------------------------------- | ------------------------ |
| `-d`, `--dir`       | Diretório de download              | `~/Downloads/Estrategia` |
| `-w`, `--wait-time` | Tempo para login manual (segundos) | `60`                     |
| `-r`, `--reset`     | Ignora progresso e recomeça        | `false`                  |
| `--headless`        | Executa sem interface gráfica      | `false`                  |
| `--no-parallel`     | Desativa downloads paralelos       | `false`                  |

## Como Funciona

1. O script abre o Chrome (com anti-detecção)
2. Você faz login manualmente
3. Após o tempo de espera, baixa automaticamente todos os materiais
4. Progresso é salvo em `.progress.json`

## Licença

MIT
