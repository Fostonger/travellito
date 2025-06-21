# Overview

# Build & run

0. Запустить docker daemon (через терминал или просто установить Docker Desktop)
1. В BotFather:
    1. Создать бота (для клиентов), его токен и юзернейм указать в .env:
        ```bash
        BOT_TOKEN=12345:example
        BOT_ALIAS=example_bot
        ```
    2. Создать бота для менеджеров, указать его токен там же:
        ```bash
        MANAGER_BOT_TOKEN=12345:example
        ```
    3. Запустить сервис для веб-страницы в боте командой `cloudflared tunnel --url http://127.0.0.1:5173`, назначенный url указать в .env файле:
        ```bash
        WEBAPP_URL=https://example.trycloudflare.com
        ```
    и отправить в BotFather командой /setdomain для клиентского бота
2. Запустить еще один сервис для обработки команды /start у ботов командой `cloudflared tunnel --url http://127.0.0.1:8080` и завязать на полученный url webhook клиентского бота командой:
    ```bash
    curl -X POST \                                  
        "https://api.telegram.org/bot{YOUR_TELEGRAM_BOT_TOKEN}/setWebhook" \
        -d "url=https://example.trycloudflare.com/webhook/{YOUR_TELEGRAM_BOT_TOKEN}"
    ```
3. Сгенерировать секретный ключ командой `python3 -c "import secrets,base64,os;print(secrets.token_urlsafe(32))"` и полученную строку созранить в .env:
    ```bash
    SECRET_KEY=yoursecretkey
    ```
4. Добавить необходимые переменные для S3 и redis:
    ```bash
    S3_ENDPOINT=minio:9000
    S3_ACCESS_KEY=minioadmin
    S3_SECRET_KEY=minioadminsecret
    S3_BUCKET=tour-images

    REDIS_DSN=redis://redis:6379/0
    ```
5. Перейти в папку bot/webapp и в ней запустить: `npm install` потом `npm run dev` (в отдельном терминале)
6. `docker-compose up -d -build`