# 🌐 Games — GitHub Pages

Юридические страницы (Privacy Policy, Terms of Use, Support) для всех игр.

**Сайт:** [igry.tw1.ru](https://igry.tw1.ru)  
**GitHub Pages:** `9283248.github.io` → кастомный домен `igry.tw1.ru`

## Структура

```
github-pages/
├── CNAME              # Кастомный домен igry.tw1.ru
├── index.html         # Главная — список всех игр
├── neonvoid/          # Neon Void
│   ├── index.html     # Хаб: Privacy + Terms
│   ├── privacy.html   # Политика конфиденциальности
│   └── terms.html     # Условия использования
└── <new-game>/        # Новые игры добавлять по шаблону
    ├── index.html
    ├── privacy.html
    └── terms.html
```

## URL-схема

Для каждой игры страницы доступны по адресам:
- `https://igry.tw1.ru/<game>/privacy.html` — Privacy Policy
- `https://igry.tw1.ru/<game>/terms.html` — Terms of Use  
- `https://igry.tw1.ru/<game>/` — Хаб с ссылками

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
