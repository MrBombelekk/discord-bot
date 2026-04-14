import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queue = []
loop_mode = False
current = None  # 🔥 aktualna piosenka

ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0'
    },
    'extractor_args': {
        'youtube': {
            'player_client': ['web']
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

# 🔎 YouTube
def search_youtube(query):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if 'entries' in info:
            return info['entries'][0]['url'], info['entries'][0]['title']
        else:
            return info['url'], info['title']

# ▶️ następna piosenka
async def play_next(ctx):
    global loop_mode, current

    if loop_mode and current:
        url, title = current
    else:
        if len(queue) == 0:
            await ctx.send("⏹️ Kolejka pusta")
            return
        current = queue.pop(0)
        url, title = current

    source = await discord.FFmpegOpusAudio.from_probe(url, **ffmpeg_options)

    def after_playing(error):
        fut = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        try:
            fut.result()
        except:
            pass

    ctx.voice_client.play(source, after=after_playing)

    await ctx.send(f"▶️ Teraz gra: **{title}**")

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

    url, title = search_youtube(query)
    queue.append((url, title))

    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ Dodano: **{title}**")

# ⏭️ skip
@bot.command()
async def skip(ctx):
    global loop_mode
    loop_mode = False  # 🔥 wyłącz loop przy skipie

    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏭️ Pominięto")

# 🔁 loop
@bot.command()
async def loop(ctx):
    global loop_mode
    loop_mode = not loop_mode
    await ctx.send(f"🔁 Loop: {'ON' if loop_mode else 'OFF'}")

# 🚪 leave
@bot.command()
async def leave(ctx):
    global queue, loop_mode, current

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queue.clear()
        loop_mode = False
        current = None
        await ctx.send("👋 Wyszedłem")

# 🚀 START
bot.run(os.getenv("TOKEN"))
