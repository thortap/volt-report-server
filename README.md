# Volt Report Generator — Servidor

## Estrutura de pastas

```
volt-server/
├── app.py
├── requirements.txt
├── Procfile
├── fonts/
│   ├── StageGrotesk-Regular.ttf
│   ├── StageGrotesk-Medium.ttf
│   ├── StageGrotesk-Bold.ttf
│   ├── StageGrotesk-ExtraBold.ttf
│   └── StageGrotesk-Black.ttf
└── assets/
    ├── volt_logo_transparent.png
    └── volt_icon_green.png
```

## Deploy no Render (gratuito)

1. Suba esta pasta para um repositório GitHub chamado `volt-report-server`
2. Acesse render.com e faça login com GitHub
3. Clique em **New > Web Service**
4. Selecione o repositório `volt-report-server`
5. Configure:
   - **Name:** volt-report-server
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`
6. Clique em **Create Web Service**
7. Aguarde o deploy (2-3 min)
8. Copie a URL gerada (ex: `https://volt-report-server.onrender.com`)
9. Cole essa URL no formulário (arquivo `index.html`) na variável `API_URL`

## Endpoint

`POST /generate` — recebe multipart/form-data com todos os campos + foto
