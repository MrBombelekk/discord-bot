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
current = None

# 🔥 yt-dlp FIX (omija blokady YouTube)
ydl_opts = {
    'format': 'bestaudio',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
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


def get_audio(query):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)

        if 'entries' in info:
            info = info['entries'][0]

        return info['url'], info['title']


async def play_next(ctx):
    global current

    if loop_mode and current:
        url, title = current
    elif queue:
        current = queue.pop(0)
        url, title = current
    else:
        await ctx.send("⏹️ Kolejka pusta")
        return

    source = await discord.FFmpegOpusAudio.from_probe(url, **ffmpeg_options)

    ctx.voice_client.play(
        source,
        after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
    )

    await ctx.send(f"▶️ Teraz gra: **{title}**")


@bot.command()
async def p(ctx, *, query):
    if not ctx.author.voice:
        await ctx.send("❌ Wejdź na kanał głosowy")
        return

    channel = ctx.author.voice.channel

    if not ctx.voice_client:
        await channel.connect()

    await ctx.send("🔎 Szukam...")

    try:
        url, title = get_audio(query)
    except Exception as e:
        await ctx.send("❌ YouTube blokuje — spróbuj inną piosenkę")
        print(e)
        return

    queue.append((url, title))

    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ Dodano: **{title}**")


@bot.command()
async def skip(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skip")


@bot.command()
async def loop(ctx):
    global loop_mode
    loop_mode = not loop_mode
    await ctx.send(f"🔁 Loop: {'ON' if loop_mode else 'OFF'}")


@bot.command()
async def leave(ctx):
    global queue, current, loop_mode

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queue.clear()
        current = None
        loop_mode = False
        await ctx.send("👋 Wyszedłem")


bot.run(os.getenv("TOKEN"))
