import asyncio
import logging
import os
import shutil
import tempfile
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import discord
import yt_dlp
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("botmuzyczny")
COOKIE_FILE = None


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"botmuzyczny online\n")

    def log_message(self, format, *args):
        logger.debug("Health check: " + format, *args)


def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check działa na porcie %s", port)


def require_ffmpeg():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "Nie znaleziono ffmpeg. Na hostingu musisz dodać ffmpeg do systemowych zależności."
        )


def setup_youtube_cookies():
    global COOKIE_FILE

    cookie_path = os.getenv("YOUTUBE_COOKIES_FILE")
    cookie_text = os.getenv("YOUTUBE_COOKIES")

    if cookie_path:
        COOKIE_FILE = cookie_path
        logger.info("yt-dlp użyje cookies z pliku: %s", cookie_path)
        return

    if not cookie_text:
        return

    COOKIE_FILE = os.path.join(tempfile.gettempdir(), "youtube_cookies.txt")
    with open(COOKIE_FILE, "w", encoding="utf-8") as file:
        file.write(cookie_text.replace("\\n", "\n"))

    logger.info("yt-dlp użyje cookies ze zmiennej YOUTUBE_COOKIES")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queue = deque()
loop_enabled = False
current_track = None
skip_requested = False
MAX_TITLE_LENGTH = 45


def short_title(title):
    title = " ".join(title.split())
    if len(title) <= MAX_TITLE_LENGTH:
        return title

    return title[: MAX_TITLE_LENGTH - 3].rstrip() + "..."

def get_ydl_options():
    options = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "default_search": "ytsearch1",
        "skip_download": True,
        "ignoreerrors": True,
        "extract_flat": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 15,
        "cachedir": False,
        "source_address": "0.0.0.0",
        "http_headers": {
            "User-Agent": os.getenv(
                "YTDLP_USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            )
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

    if COOKIE_FILE:
        options["cookiefile"] = COOKIE_FILE

    return options

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -loglevel warning",
}


@bot.event
async def on_ready():
    logger.info("Zalogowano jako %s", bot.user)


def _extract_audio(query):
    try:
        with yt_dlp.YoutubeDL(get_ydl_options()) as ydl:
            info = ydl.extract_info(query, download=False)
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc)
        if "429" in message or "Sign in to confirm" in message or "not a bot" in message:
            raise ValueError(
                "YouTube zablokował IP hostingu. Dodaj cookies do zmiennej "
                "YOUTUBE_COOKIES albo użyj innego hostingu/IP."
            ) from exc
        raise

    if not info:
        raise ValueError("Brak wyników")

    if "entries" in info:
        info = next((entry for entry in info["entries"] if entry), None)

    if not info:
        raise ValueError("Brak wyników")

    url = info.get("url")
    title = info.get("title") or "Nieznany tytuł"

    if not url:
        raise ValueError("Nie udało się pobrać adresu audio")

    return url, title


async def get_audio(query):
    return await asyncio.to_thread(_extract_audio, query)


def schedule_next(ctx, error=None):
    if error:
        logger.warning("Błąd odtwarzania: %s", error)

    future = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
    future.add_done_callback(log_task_error)


def log_task_error(future):
    try:
        future.result()
    except Exception:
        logger.exception("Błąd w play_next")


async def play_next(ctx):
    global current_track, skip_requested

    voice_client = ctx.voice_client
    if not voice_client or not voice_client.is_connected():
        current_track = None
        skip_requested = False
        return

    if loop_enabled and current_track and not skip_requested:
        queue.appendleft(current_track)

    skip_requested = False

    if not queue:
        current_track = None
        await ctx.send("⏹️ Kolejka pusta")
        return

    url, title = queue.popleft()
    current_track = (url, title)

    try:
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        voice_client.play(source, after=lambda error: schedule_next(ctx, error))
    except Exception as exc:
        logger.exception("Nie udało się uruchomić odtwarzania")
        await ctx.send(f"❌ Nie udało się uruchomić audio: {exc}")
        await play_next(ctx)
        return

    await ctx.send(f"▶️ **{short_title(title)}**")


@bot.command()
async def p(ctx, *, query):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ Wejdź na kanał głosowy")
        return

    channel = ctx.author.voice.channel

    try:
        if not ctx.voice_client:
            await channel.connect(timeout=20, reconnect=True)
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
    except discord.ClientException as exc:
        await ctx.send(f"❌ Nie mogę wejść na kanał głosowy: {exc}")
        return
    except asyncio.TimeoutError:
        await ctx.send("❌ Discord za długo nie odpowiadał przy łączeniu z kanałem")
        return

    message = await ctx.send("🔎")

    try:
        url, title = await get_audio(query)
    except Exception as exc:
        logger.exception("Błąd pobierania audio dla zapytania: %s", query)
        await message.edit(content=f"❌ Błąd wyszukiwania: {exc}")
        return

    queue.append((url, title))

    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        await message.edit(content="✅")
        await play_next(ctx)
    else:
        await message.edit(content=f"➕ **{short_title(title)}**")


@bot.command()
async def skip(ctx):
    global skip_requested

    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("❌ Nie jestem na kanale głosowym")
        return

    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        await ctx.send("❌ Nic teraz nie gra")
        return

    skip_requested = True
    ctx.voice_client.stop()
    await ctx.send("⏭️ Pominięto")


@bot.command(name="loop")
async def loop_command(ctx):
    global loop_enabled

    loop_enabled = not loop_enabled
    await ctx.send(f"🔁 Loop: {'ON' if loop_enabled else 'OFF'}")


@bot.command(name="queue", aliases=["q", "kolejka"])
async def queue_command(ctx):
    if not current_track and not queue:
        await ctx.send("Kolejka jest pusta")
        return

    lines = []
    if current_track:
        lines.append(f"▶️ **{short_title(current_track[1])}**")

    if queue:
        upcoming = list(queue)[:10]
        lines.extend(
            f"{index}. {short_title(title)}"
            for index, (_, title) in enumerate(upcoming, start=1)
        )

        if len(queue) > 10:
            lines.append(f"...i jeszcze {len(queue) - 10}")

    await ctx.send("\n".join(lines))


@bot.command()
async def leave(ctx):
    global loop_enabled, current_track, skip_requested

    if not ctx.voice_client:
        await ctx.send("❌ Nie jestem na kanale głosowym")
        return

    await ctx.voice_client.disconnect(force=True)
    queue.clear()
    current_track = None
    loop_enabled = False
    skip_requested = False
    await ctx.send("👋 Wyszedłem")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Użycie: `!p nazwa albo link do piosenki`")
        return

    if isinstance(error, commands.CommandNotFound):
        return

    logger.exception("Błąd komendy", exc_info=error)
    await ctx.send(f"❌ Błąd komendy: {error}")


require_ffmpeg()
setup_youtube_cookies()
start_health_server()

token = os.getenv("TOKEN")
if not token:
    raise RuntimeError("Brak zmiennej środowiskowej TOKEN")

bot.run(token)

