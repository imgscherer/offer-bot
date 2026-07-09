# Automação: rodando a cada 10 minutos de verdade

O `schedule:` nativo do GitHub Actions **não é confiável** abaixo de ~1h —
o próprio GitHub avisa que agendamentos são adiados em períodos de carga
alta, e na prática intervalos de 5-10min viraram runs a cada 2-4h neste
projeto. Por isso o workflow (`.github/workflows/run.yml`) só tem
`workflow_dispatch:` — ele é disparado de fora, via API, por um serviço
de cron externo gratuito.

## Setup (cron-job.org)

1. **Criar um Personal Access Token (fine-grained)** só pra isso:
   - GitHub → foto de perfil → `Settings` → `Developer settings` →
     `Personal access tokens` → `Fine-grained tokens` → `Generate new token`
   - Repository access: **Only select repositories** → `offer-bot`
   - Permissions: **Actions** → `Read and write` (só essa, mais nada)
   - Copie o token (`github_pat_...`) — só aparece uma vez.

2. **Criar conta em [cron-job.org](https://cron-job.org)** (grátis).

3. **Criar um cronjob novo:**
   - URL: `https://api.github.com/repos/imgscherer/offer-bot/actions/workflows/run.yml/dispatches`
   - Method: `POST`
   - Headers:
     - `Authorization: Bearer SEU_TOKEN_AQUI`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - Body: `{"ref":"main"}`
   - Schedule: a cada 10 minutos

4. Salve e teste manualmente ("Run now" no cron-job.org) — deve aparecer
   um novo run em `Actions` no GitHub, disparado via `workflow_dispatch`.

## Por que não usar GITHUB_TOKEN do próprio workflow

O `GITHUB_TOKEN` automático só existe *durante* um run — não dá pra usar
ele pra disparar o *próximo* run de fora. Por isso precisa de um PAT
separado, escopado só a esse repo e só à permissão de Actions.
