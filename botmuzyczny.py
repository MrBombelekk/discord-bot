import discord
from discord.ext import commands
import wavelink
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queue = []
loop_mode = False


# ================== READY ==================
@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")

    nodes = [
        wavelink.Node(
            uri="http://lava.link:80",
            password="youshallnotpass"
        )
    ]

    await wavelink.Pool.connect(nodes=nodes, client=bot)


# ================== PLAY NEXT ==================
async def play_next(ctx):
    global loop_mode

    vc: wavelink.Player = ctx.voice_client

    if loop_mode and vc.current:
        await vc.play(vc.current)
        return

    if queue:
        track = queue.pop(0)
        await vc.play(track)
        await ctx.send(f"▶️ Teraz gra: **{track.title}**")
    else:
        await ctx.send("⏹️ Kolejka pusta")


# ================== PLAY ==================
@bot.command()
async def p(ctx, *, query):
    global queue

    if not ctx.author.voice:
        await ctx.send("❌ Musisz być na kanale głosowym")
        return

    channel = ctx.author.voice.channel

    if not ctx.voice_client:
        vc = await channel.connect(cls=wavelink.Player)
    else:
        vc: wavelink.Player = ctx.voice_client

    await ctx.send("🔎 Szukam...")

    tracks = await wavelink.Playable.search(query)

    if not tracks:
        await ctx.send("❌ Nie znaleziono")
        return

    track = tracks[0]

    if not vc.playing:
        await vc.play(track)
        await ctx.send(f"▶️ Teraz gra: **{track.title}**")
    else:
        queue.append(track)
        await ctx.send(f"➕ Dodano do kolejki: **{track.title}**")


# ================== EVENT KONIEC PIOSENKI ==================
@bot.event
async def on_wavelink_track_end(payload):
    player = payload.player
    ctx = player.ctx

    if ctx:
        await play_next(ctx)


# ================== SKIP ==================
@bot.command()
async def skip(ctx):
    vc: wavelink.Player = ctx.voice_client

    if vc and vc.playing:
        await vc.stop()
        await ctx.send("⏭️ Pominięto")


# ================== LOOP ==================
@bot.command()
async def loop(ctx):
    global loop_mode
    loop_mode = not loop_mode
    await ctx.send(f"🔁 Loop: {'ON' if loop_mode else 'OFF'}")


# ================== LEAVE ==================
@bot.command()
async def leave(ctx):
    global queue, loop_mode

    vc: wavelink.Player = ctx.voice_client

    if vc:
        await vc.disconnect()
        queue.clear()
        loop_mode = False
        await ctx.send("👋 Wyszedłem")


# ================== FIX CTX ==================
@bot.event
async def on_wavelink_track_start(payload):
    payload.player.ctx = payload.player.client.get_channel(payload.player.channel.id).last_message.channel


# ================== RUN ==================
bot.run(os.getenv("TOKEN"))
