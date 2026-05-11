from aiohttp import web
from aiohttp.web import Request, Response
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter
from botbuilder.schema import Activity
from bot.candidate_pool_bot import CandidatePoolBot
from bot.config import settings
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,
    app_password=settings.MICROSOFT_APP_PASSWORD,
)
adapter = BotFrameworkAdapter(adapter_settings)
bot = CandidatePoolBot()


async def on_error(context, error: Exception):
    logger.exception("Unhandled bot error", exc_info=error)
    await context.send_activity("An unexpected error occurred. Please try again.")


adapter.on_turn_error = on_error


async def messages(request: Request) -> Response:
    if request.content_type != "application/json":
        return Response(status=415)

    body = await request.json()
    activity = Activity().deserialize(body)

    auth_header = request.headers.get("Authorization", "")

    response = await adapter.process_activity(activity, auth_header, bot.on_turn)
    if response:
        return Response(
            status=response.status,
            body=json.dumps(response.body),
            content_type="application/json",
        )
    return Response(status=201)


app = web.Application()
app.router.add_post("/api/messages", messages)
app.router.add_get("/health", lambda r: Response(text="ok"))

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=3978)
