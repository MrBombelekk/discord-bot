import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queue = []
loop = False
current = None

# 🔥 YTDLP FIX (NAJWAŻNIEJSZE)
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'ignoreerrors': True,
    'nocheckcertificate': True,

    'http_headers': {
        'User-Agent': 'Mozilla/5.0'
    },

    'extractor_args': {
        'youtube': {
            'player_client': ['android']
        }
    }
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")

# 🔎 pobieranie audio (NAPRAWIONE)
def get_audio(query):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)

        if not info or 'entries' not in info:
            raise Exception("Brak wyników")

        video = info['entries'][0]

        if not video:
            raise Exception("Brak video")

        formats = video.get("formats", [])

        audio_url = None

        for f in formats:
            if f.get("acodec") != "none":
                audio_url = f.get("url")
                break

        if not audio_url:
            raise Exception("Brak audio")

        title = video.get("title", "Nieznany")

        return audio_url, title

# ▶️ następna piosenka
async def play_next(ctx):
    global current, loop

    if loop and current:
        queue.insert(0, current)

    if len(queue) > 0:
        url, title = queue.pop(0)
        current = (url, title)

        source = await discord.FFmpegOpusAudio.from_probe(url, **ffmpeg_options)

        ctx.voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        )

        await ctx.send(f"▶️ Teraz gra: **{title}**")
    else:
        await ctx.send("⏹️ Kolejka pusta")

# ▶️ play
@bot.command()
async def p(ctx, *, query):
    if not ctx.author.voice:
        await ctx.send("❌ Musisz być na kanale głosowym")
        return

    channel = ctx.author.voice.channel

    if not ctx.voice_client:
        await channel.connect()

    await ctx.send("🔎 Szukam...")

    try:
        url, title = get_audio(query)
    except Exception as e:
        await ctx.send(f"❌ Błąd: {e}")
        return

    queue.append((url, title))

    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ Dodano: **{title}**")

# ⏭️ skip
@bot.command()
async def skip(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏭️ Pominięto")

# 🔁 loop
@bot.command()
async def loop(ctx):
    global loop
    loop = not loop
    await ctx.send(f"🔁 Loop: {'ON' if loop else 'OFF'}")

# 🚪 leave
@bot.command()
async def leave(ctx):
    global queue, loop, current

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queue.clear()
        current = None
        loop = False
        await ctx.send("👋 Wyszedłem")

bot.run(os.getenv("TOKEN"))
