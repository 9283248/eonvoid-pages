# 🌐 Games — GitHub Pages

Юридические страницы (Privacy Policy, Terms of Use, Support) для всех игр.

**Сайт:** [9283248.github.io/eonvoid-pages](https://9283248.github.io/eonvoid-pages/)

## Структура

```
github-pages/
├── index.html         # Главная — список всех игр
├── neonvoid/          # Neon Void
│   ├── index.html     # Хаб: Privacy + Terms + Support
│   ├── privacy.html   # Политика конфиденциальности
│   ├── terms.html     # Условия использования
│   └── support.html   # Страница поддержки
└── <new-game>/        # Новые игры добавлять по шаблону
    ├── index.html
    ├── privacy.html
    ├── terms.html
    └── support.html
```

## URL-схема

Для каждой игры страницы доступны по адресам:
- `https://9283248.github.io/eonvoid-pages/<game>/privacy.html` — Privacy Policy
- `https://9283248.github.io/eonvoid-pages/<game>/terms.html` — Terms of Use
- `https://9283248.github.io/eonvoid-pages/<game>/support.html` — Support
- `https://9283248.github.io/eonvoid-pages/<game>/` — Хаб с ссылками

## Деплой

```bash
cd github-pages
git add .
git commit -m "Update pages"
git push
```

GitHub Pages автоматически публикует из ветки `main`.

## Добавление новой игры

1. Создать папку `<game-name>/`
2. Скопировать шаблон из `neonvoid/`
3. Заменить название игры, email, описание
4. Добавить ссылку на новую игру в корневой `index.html`
5. Закоммитить и push
