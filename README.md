# Auto Download Estratégia Concursos

Baixador automático de cursos do Estratégia Concursos com anti-detecção, downloads paralelos e
integração com Google Drive.

## ✨ Funcionalidades

- 🛡️ **Anti-detecção** — SeleniumBase UC Mode evita bloqueios
- ⚡ **Downloads paralelos** — Até 3 downloads simultâneos em background
- ☁️ **Google Drive** — Upload automático com verificação e limpeza local
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

## Configuração do Google Drive (Opcional)

Para usar a integração com o Google Drive:

1. Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/).
2. Ative a **Google Drive API**.
3. Crie credenciais do tipo **OAuth client ID** -> **Desktop App**.
4. Baixe o JSON e salve como `client_secret.json` na raiz do projeto.

## Uso

```bash
# Executar normalmente (apenas download local)
uv run python main.py

# Download local + Upload para Google Drive (e apagar local após sucesso)
uv run python main.py --drive

# Download local + Upload para Google Drive (e MANTER local)
uv run python main.py --drive --keep-local

# Especificar diretório de download
uv run python main.py -d /caminho/para/downloads

# Ajustar tempo de espera para login (padrão: 60s)
uv run python main.py -w 120

# Resetar progresso
uv run python main.py --reset
```

## Argumentos

| Argumento           | Descrição                          | Padrão                   |
| ------------------- | ---------------------------------- | ------------------------ |
| `-d`, `--dir`       | Diretório de download local        | `~/Downloads/Estrategia` |
| `-w`, `--wait-time` | Tempo para login manual (segundos) | `60`                     |
| `-r`, `--reset`     | Ignora progresso e recomeça        | `false`                  |
| `--headless`        | Executa sem interface gráfica      | `false`                  |
| `--no-parallel`     | Desativa downloads paralelos       | `false`                  |
| `--drive`           | Ativa upload para Google Drive     | `false`                  |
| `--keep-local`      | Mantém arquivos locais após upload | `false`                  |

## Como Funciona

1. O script abre o Chrome (com anti-detecção)
2. Você faz login manualmente
3. Após o tempo de espera, baixa automaticamente todos os materiais
4. Se `--drive` estiver ativo:
   - Cria estrutura de pastas `Curso > Aula` no Drive
   - Faz upload dos arquivos (suporta vídeos grandes)
   - Remove o arquivo local apenas se o upload for confirmado (a menos que use `--keep-local`)

## Licença

MIT
