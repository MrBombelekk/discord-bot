import asyncio
import os
from collections import deque

import discord
import yt_dlp
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queue = deque()
loop_enabled = False
current_track = None

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "default_search": "ytsearch1",
    "skip_download": True,
    "ignoreerrors": True,
    "extract_flat": False,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")


def _extract_audio(query):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(query, download=False)

    if not info:
        raise ValueError("Brak wyników")

    if "entries" in info:
        info = next((entry for entry in info["entries"] if entry), None)

    if not info:
        raise ValueError("Brak wyników")

    url = info.get("url")
    title = info.get("title", "Nieznany tytuł")

    if not url:
        raise ValueError("Nie udało się pobrać adresu audio")

    return url, title


async def get_audio(query):
    return await asyncio.to_thread(_extract_audio, query)


def schedule_next(ctx, error=None):
    if error:
        print(f"Błąd odtwarzania: {error}")

    asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)


async def play_next(ctx):
    global current_track

    voice_client = ctx.voice_client
    if not voice_client or not voice_client.is_connected():
        current_track = None
        return

    if loop_enabled and current_track:
        queue.appendleft(current_track)

    if not queue:
        current_track = None
        await ctx.send("⏹️ Kolejka pusta")
        return

    url, title = queue.popleft()
    current_track = (url, title)
    source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)

    voice_client.play(source, after=lambda error: schedule_next(ctx, error))
    await ctx.send(f"▶️ Teraz gra: **{title}**")


@bot.command()
async def p(ctx, *, query):
    if not ctx.author.voice:
        await ctx.send("❌ Wejdź na kanał głosowy")
        return

    channel = ctx.author.voice.channel

    if not ctx.voice_client:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)

    await ctx.send("🔎 Szukam...")

    try:
        url, title = await get_audio(query)
    except Exception as exc:
        await ctx.send(f"❌ Błąd: {exc}")
        return

    queue.append((url, title))

    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ Dodano: **{title}**")


@bot.command()
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.send("❌ Nic teraz nie gra")
        return

    ctx.voice_client.stop()
    await ctx.send("⏭️ Pominięto")


@bot.command(name="loop")
async def loop_command(ctx):
    global loop_enabled

    loop_enabled = not loop_enabled
    await ctx.send(f"🔁 Loop: {'ON' if loop_enabled else 'OFF'}")


@bot.command()
async def leave(ctx):
    global loop_enabled, current_track

    if not ctx.voice_client:
        await ctx.send("❌ Nie jestem na kanale głosowym")
        return

    await ctx.voice_client.disconnect()
    queue.clear()
    current_track = None
    loop_enabled = False
    await ctx.send("👋 Wyszedłem")


token = os.getenv("TOKEN")
if not token:
    raise RuntimeError("Brak zmiennej środowiskowej TOKEN")

bot.run(token)
