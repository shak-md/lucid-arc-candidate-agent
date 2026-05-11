# Candidate Pool Agent - Teams Bot

Microsoft Teams bot that provides the recruiter-facing interface for the candidate pool agent.
Connects to the agent core service via HTTP.

## Project structure

```
candidate_pool_teams_bot/
  app.py                          # aiohttp entry point, Teams webhook receiver
  bot/
    candidate_pool_bot.py         # All Teams activity handling and routing
    cards.py                      # Adaptive Card builders (dropdown, confirm, errors, success)
    agent_client.py               # HTTP client for the agent core service
    session_store.py              # Maps Teams conversation ID to agent session ID
    config.py                     # Settings loaded from .env
  teams_app_manifest/
    manifest.json                 # Teams app manifest for sideloading
  tests/
    test_bot.py                   # Unit tests for cards and session store
  requirements.txt
  .env.example
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD, and AGENT_SERVICE_URL
```

## Run

Make sure the agent core service is running first, then:

```bash
python app.py
```

Bot listens on port 3978. Teams requires a public HTTPS endpoint.
For local development use ngrok:

```bash
ngrok http 3978
```

Copy the ngrok HTTPS URL into your Azure Bot registration as the messaging endpoint:
`https://<your-ngrok-id>.ngrok.io/api/messages`

## Run tests

```bash
pytest tests/
```

## Registering the bot in Azure

1. Go to Azure Portal > Create a resource > Azure Bot
2. Set the messaging endpoint to your deployed URL + `/api/messages`
3. Copy the App ID and App Password into your .env file
4. Under Channels, add Microsoft Teams

## Deploying to Teams

1. Edit `teams_app_manifest/manifest.json` and replace `YOUR_MICROSOFT_APP_ID` with your real App ID
2. Add `color.png` (192x192) and `outline.png` (32x32) icons to the manifest folder
3. Zip the manifest folder contents
4. In Teams > Apps > Upload a custom app, upload the zip
5. Or submit to your org's Teams app catalog for broader rollout

## Recruiter flow in Teams

1. Recruiter opens the bot in Teams personal chat
2. Uploads LinkedIn Recruiter export (.xlsx)
3. Bot shows a pool selection dropdown (Adaptive Card)
4. Recruiter selects the pool and clicks Select Pool
5. Bot shows a confirmation card with pool name and candidate count
6. Recruiter clicks Confirm
7. Bot shows a success card with counts and an option to load another file

## Scaling notes

- Session store maps Teams conversation ID to agent session ID in memory.
  Swap the dict in `bot/session_store.py` for a Redis client to support multiple bot instances.
- The bot itself is stateless beyond the session map — all business logic lives in the agent core service.
