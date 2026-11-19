# Чекліст запуску без платних API

## Потрібно зробити у твоїх облікових записах

- [ ] Створити безкоштовний акаунт GitHub.
- [ ] Створити репозиторій `liudiane-maibutnie` (рекомендовано Public для безкоштовного GitHub Actions).
- [ ] Завантажити в корінь репозиторію всі файли з розпакованої папки `ai-for-humanity`, зберігши `.github/workflows/update-feed.yml`.
- [ ] Відкрити GitHub → Actions → Daily RSS update; за потреби увімкнути workflow.
- [ ] Запустити workflow вручну кнопкою Run workflow.
- [ ] Переконатися, що запуск успішний; новий коміт створюється лише за наявності нових матеріалів.
- [ ] Увійти у Vercel через GitHub.
- [ ] Імпортувати репозиторій у Vercel, Framework Preset `Other`, Root Directory `./`, без build command.
- [ ] Натиснути Deploy і зберегти адресу `*.vercel.app`.
- [ ] Після першого нового коміту перевірити, що Vercel автоматично зробив deployment.

## Чого НЕ потрібно

- OpenAI API key або баланс OpenAI.
- GitHub Personal Access Token.
- Vercel Cron.
- База даних.
- Платні RSS-сервіси або платні Python-пакети.

## Редакційні межі без ШІ API

Поточна автоматизація — це тематичний RSS-агрегатор: вона не генерує авторські аналітичні тексти й не проводить повноцінний фактчекінг. Вона відбирає нові записи за датою, доменом і ключовими словами, показує короткий опис джерела та дає посилання на оригінал. Особливо важливо відрізняти препринти arXiv від рецензованих статей.

## Ресурси

- GitHub: https://github.com/
- GitHub Desktop: https://desktop.github.com/
- Vercel: https://vercel.com/
- GitHub Actions schedule: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Vercel Hobby: https://vercel.com/docs/plans/hobby
