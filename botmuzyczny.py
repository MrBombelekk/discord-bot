import discord
from discord.ext import commands
import yt_dlp
import asyncio

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

queue = []
loop = False

ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
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


def is_spotify(url):
    return "spotify.com" in url


def search_youtube(query):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)['entries'][0]
        return info['webpage_url']


async def play_next(ctx):
    global queue, loop

    if loop and len(queue) > 0:
        url = queue[0]
    elif len(queue) > 0:
        url = queue.pop(0)
    else:
        return

    vc = ctx.voice_client

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if 'entries' in info:
                info = info['entries'][0]

            audio_url = info['url']
            title = info.get('title', 'Nieznany')

    except Exception as e:
        print(e)
        return

    source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)

    def after_playing(error):
        coro = play_next(ctx)
        asyncio.run_coroutine_threadsafe(coro, bot.loop)

    vc.play(source, after=after_playing)

    asyncio.run_coroutine_threadsafe(
        ctx.send(f"🎵 Gram: {title}"),
        bot.loop
    )


@bot.command()
async def p(ctx, *, url):
    global queue

    if not ctx.author.voice:
        await ctx.send("Wejdź na kanał głosowy!")
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client:
        vc = ctx.voice_client
    else:
        vc = await channel.connect()

    if is_spotify(url):
        await ctx.send("🔍 Szukam na YouTube...")
        url = search_youtube(url)

    queue.append(url)

    if not vc.is_playing():
        await play_next(ctx)
    else:
        await ctx.send("➕ Dodano do kolejki")


@bot.command()
async def s(ctx):  # skip
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Pominięto")


@bot.command()
async def l(ctx):  # loop
    global loop
    loop = not loop
    await ctx.send(f"🔁 Loop: {'ON' if loop else 'OFF'}")


@bot.command()
async def leave(ctx):
    global queue, loop

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queue.clear()
        loop = False
        await ctx.send("👋 Wyszedłem z kanału")


# 🔐 TU WKLEJ TOKEN
bot.run("nWFdIYi1VslduVvrPiAlBJjcLL4Sdfb_")