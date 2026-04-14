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

ydl_opts = {
    'format': 'bestaudio',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
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

# 🔎 szukanie yt
def search_youtube(query):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if 'entries' in info:
            return info['entries'][0]['url'], info['entries'][0]['title']
        else:
            return info['url'], info['title']

# ▶️ odtwarzanie kolejnego
async def play_next(ctx):
    global loop

    if loop and ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.play(
            ctx.voice_client.source,
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        )
        return

    if len(queue) > 0:
        url, title = queue.pop(0)

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

    url, title = search_youtube(query)
    queue.append((url, title))

    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ Dodano do kolejki: **{title}**")

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
    global queue, loop

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queue.clear()
        loop = False
        await ctx.send("👋 Wyszedłem z kanału")

# 🔄 AUTO RESTART (24/7)
async def keep_alive():
    while True:
        await asyncio.sleep(300)
        print("Bot działa...")

bot.loop.create_task(keep_alive())

bot.run(os.getenv("TOKEN"))
