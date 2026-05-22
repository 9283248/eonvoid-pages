# Pollinations MCP Server

MCP сервер для генерации картинок через [Pollinations.ai](https://pollinations.ai) — бесплатно, без API ключа.

## Установка

```bash
cd mcp-pollinations
pip install -r requirements.txt
```

## Подключение к Claude Desktop

Открой файл конфига Claude Desktop:

- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Добавь блок:

```json
{
  "mcpServers": {
    "pollinations": {
      "command": "python",
      "args": ["/ПОЛНЫЙ/ПУТЬ/ДО/server.py"]
    }
  }
}
```

Замени `/ПОЛНЫЙ/ПУТЬ/ДО/server.py` на реальный путь, например:
`/Users/username/projects/mcp-pollinations/server.py`

Перезапусти Claude Desktop.

## Использование

После подключения просто напиши в чате:

> "Сгенерируй картинку: закат над горами в стиле аниме"

Картинки сохраняются в `~/Pictures/pollinations/`.

## Параметры инструмента `generate_image`

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `prompt` | string | — | Описание картинки |
| `width` | int | 1024 | Ширина в пикселях |
| `height` | int | 1024 | Высота в пикселях |
| `model` | string | `flux` | Модель: `flux`, `flux-realism`, `turbo` |
| `seed` | int | — | Сид для воспроизводимости |
