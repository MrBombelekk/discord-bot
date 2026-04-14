import discord
from discord.ext import commands
import wavelink
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queue = []
loop_mode = False
current = None


@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")

    # 🔥 połączenie z Lavalink
    node = wavelink.Node(
        uri="lavalink-v4-idle.up.railway.app:443",  # darmowy node
        password="youshallnotpass",
        secure=True
    )

    await wavelink.Pool.connect(nodes=[node], client=bot)


# ▶️ PLAY
@bot.command()
async def p(ctx, *, query: str):
    global current

    if not ctx.author.voice:
        return await ctx.send("❌ Wejdź na kanał głosowy")

    player: wavelink.Player

    if not ctx.voice_client:
        player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    else:
        player = ctx.voice_client

    tracks = await wavelink.YouTubeTrack.search(query)

    if not tracks:
        return await ctx.send("❌ Nic nie znaleziono")

    track = tracks[0]

    queue.append(track)

    if not player.playing:
        await play_next(ctx)

    await ctx.send(f"➕ Dodano: **{track.title}**")


# ▶️ NEXT
async def play_next(ctx):
    global current, loop_mode

    player: wavelink.Player = ctx.voice_client

    if loop_mode and current:
        track = current
    else:
        if not queue:
            return await ctx.send("⏹️ Kolejka pusta")
        track = queue.pop(0)
        current = track

    await player.play(track)
    await ctx.send(f"▶️ Teraz gra: **{track.title}**")


# ⏭️ SKIP
@bot.command()
async def skip(ctx):
    global loop_mode
    loop_mode = False

    if ctx.voice_client:
        await ctx.voice_client.stop()
        await play_next(ctx)


# 🔁 LOOP
@bot.command()
async def loop(ctx):
    global loop_mode
    loop_mode = not loop_mode
    await ctx.send(f"🔁 Loop: {'ON' if loop_mode else 'OFF'}")


# 📜 QUEUE
@bot.command()
async def q(ctx):
    if not queue:
        return await ctx.send("📭 Kolejka pusta")

    msg = "\n".join([f"{i+1}. {t.title}" for i, t in enumerate(queue[:10])])
    await ctx.send(f"📜 Kolejka:\n{msg}")


# 🚪 LEAVE
@bot.command()
async def leave(ctx):
    global queue, loop_mode, current

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queue.clear()
        loop_mode = False
        current = None
        await ctx.send("👋 Wyszedłem")


bot.run(os.getenv("TOKEN"))
