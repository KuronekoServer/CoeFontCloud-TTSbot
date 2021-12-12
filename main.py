import os
import json
import re
import traceback
import hmac
import hashlib

import nextcord
import requests
from nextcord.ext import commands
from nextcord.player import FFmpegPCMAudio
from collections import defaultdict, deque
from io import BytesIO
from tinydb import TinyDB, Query
from pathlib import Path

IS_PREMIUM = False
PREFIX = "r!"
TOKEN = 'TOKEN'
CF_KEY = 'COEFONT API KEY'
CF_SECRET = 'COEFONT API SECRET'
FFMEPG_LOCATION = '/usr/bin/ffmpeg'
ADMINS_ID = [
]

FREE_COEFONTS = {
    "アリアル": "432f4a8f-f95e-4536-ae36-70417af539c3",
    "アベルーニ": "e0898f09-11ce-4644-9552-c418228e79b9"
}
PREMIUM_COEFONTS = {
    "遊音一莉": "e5e3fe14-f9f0-478d-a094-b5868bc41c6c",
    "ミリアル": "c28adf78-d67d-4588-a9a5-970a76ca6b07"
}
DEFAULT_COEFONT = "アリアル"
dicts = TinyDB("dict.json")
voices = TinyDB("voices.json")
qwy = Query()

if IS_PREMIUM:
    premium = TinyDB("premium.json")

bot = commands.Bot(command_prefix=PREFIX)

chs = {}
queue_dict = defaultdict(deque)


@bot.event
async def on_command_error(ctx, error):
    orig_error = getattr(error, "original", error)
    error_msg = ''.join(traceback.TracebackException.from_exception(orig_error).format())
    print(error_msg)
    await ctx.send(":x: 内部エラーが発生しました。")


def get_voice(guild_id):
    if voices.search(qwy.id == guild_id):
        return voices.search(qwy.id == guild_id)[0]['voice']
    else:
        return FREE_COEFONTS[DEFAULT_COEFONT]


@bot.event
async def on_message(message):
    if IS_PREMIUM and not premium.search(qwy.id == message.guild.id) and not message.content.startswith(
            PREFIX + "premium"):
        return

    if message.channel.id in chs and message.guild.voice_client:
        if message.author.bot:
            return
        text = filter_str(message, message.guild)
        file = coefontTTS(text, get_voice(message.guild.id))
        if file:
            enqueue(message.guild.voice_client, message.guild, FFmpegPCMAudio(source=file, executable=FFMEPG_LOCATION))

    await bot.process_commands(message)


def filter_str(message, guild):
    text = message.content

    for a in message.mentions:
        text = text.replace(f'<@!{a.id}>', f'アットマーク{a.display_name}')
        text = text.replace(f'<@{a.id}>', f'アットマーク{a.display_name}')

    for a in dicts.table(str(guild.id)).all():
        text = text.replace(a['key'], a['value'])

    for a in dicts.all():
        text = text.replace(a['key'], a['value'])

    text = re.sub('https?://.+$', "リンク省略", text)

    return text


def is_admin(id):
    return id in ADMINS_ID


def play(voice_client, queue):
    if not queue or voice_client.is_playing():
        return
    source = queue.popleft()
    voice_client.play(source, after=lambda e: play(voice_client, queue))


def enqueue(voice_client, guild, source):
    queue = queue_dict[guild.id]
    queue.append(source)
    if not voice_client.is_playing():
        play(voice_client, queue)


@bot.event
async def on_ready():
    print('Ready!')
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name=f'{PREFIX}help | {len(client.guilds)}サーバーで稼働中'))

@bot.event
async def on_guild_join(guild):
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name=f'{PREFIX}help | {len(client.guilds)}サーバーで稼働中'))

@bot.event
async def on_guild_leave(guild):
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name=f'{PREFIX}help | {len(client.guilds)}サーバーで稼働中'))

@bot.command(name='help')
async def help(ctx):
    helpEmbed = discord.Embed(title="Help / ヘルプ",description="")
    helpEmbed.add_field(
        name = "v!ping",
        value = "応答速度を測定します。"
    )
    helpEmbed.add_field(
        name = "v!help",
        value = "ヘルプを表示します。"
    )
    helpEmbed.add_field(
        name = "v!invite",
        value = "招待リンクを表示します。"
    )
    helpEmbed.add_field(
        name = "v!join",
        value = "VCに参加します。"
    )
    helpEmbed.add_field(
        name = "v!dc",
        value = "VCから切断します。"
    )
    helpEmbed.add_field(
        name = "v!setvoice [ボイス名]",
        value = "喋る人を変更します。ボイス名なしでボイス一覧を表示します。"
    )
    helpEmbed.add_field(
        name = "v!dict add [テキスト] [読み上げ]",
        value = "辞書に単語を追加します。"
    )
    helpEmbed.add_field(
        name = "v!gdict add [テキスト] [読み上げ]",
        value = "全体辞書に単語を追加します。※運営のみ"
    )
    helpEmbed.add_field(
        name = "v!premium add [サーバーID]",
        value = "有料サーバーを追加します。※運営のみ"
    )
    embed.set_footer(text="Developed by cron",
                     icon_url="https://cdn.discordapp.com/avatars/731503872098697226/f4aeb81ec1d493ed2b491aaed9103f9c.png")
    ctx.message.channel.send(embed=helpEmbed)

@bot.command(name='invite')
async def invite(ctx):
    ctx.send(INVITE_LINK)

@bot.command(name='ping')
async def ping(ctx):
    ctx.send(f"Ping: {round(bot.latency * 1000)}ms")


@bot.command(name='premium')
async def prem(ctx, arg, arg2):
    if not is_admin(ctx.message.author.id):
        return
    if arg == "add" and arg2:
        premium.insert({'id': arg2})
        await ctx.send("追加しました。")

@bot.command(name='setvoice')
async def setvoice(ctx, *args):
    if not args:
        await ctx.send("選択肢は以下の通りです。\n無料版: "+", ".join(FREE_COEFONTS)+"\n有料版: "+", ".join(PREMIUM_COEFONTS))
    else:
        if args[0] in FREE_COEFONTS:
            if voices.search(qwy.id == ctx.message.guild.id):
                voices.update({"voice": FREE_COEFONTS[args[0]]}, qwy.id == ctx.message.guild.id)
            else:
                voices.insert({"id": ctx.message.guild.id, "voice": FREE_COEFONTS[args[0]]})
            await ctx.send("設定しました。")
        elif args[0] in PREMIUM_COEFONTS:
            if IS_PREMIUM:
                if voices.search(qwy.id == ctx.message.guild.id):
                    voices.update({"voice": PREMIUM_COEFONTS[args[0]]}, qwy.id == ctx.message.guild.id)
                else:
                    voices.insert({"id": ctx.message.guild.id, "voice": PREMIUM_COEFONTS[args[0]]})
            else:
                await ctx.send("有料版でのみお使いいただけます。")
            await ctx.send("設定しました。")
        else:
            await ctx.send("選択肢は以下の通りです。\n無料版: " + ", ".join(FREE_COEFONTS) + "\n有料版: " + ", ".join(PREMIUM_COEFONTS))

@bot.command(name='dict')
async def dict(ctx, arg, arg2, arg3):
    if arg == "add":
        if arg2 and arg3:
            if dicts.table(str(ctx.guild.id)).search(qwy.key == arg2):
                dicts.table(str(ctx.guild.id)).update({"value": arg3}, qwy.key == arg2)
                await ctx.send("辞書を変更しました。")
            else:
                dicts.table(str(ctx.guild.id)).insert({"key": arg2, "value": arg3})
                await ctx.send("辞書に追加しました。")
        else:
            await ctx.send("引数が足りません。")


@bot.command(name='gdict')
async def gdict(ctx, arg, arg2, arg3):
    if not is_admin(ctx.message.author.id):
        return
    if arg == "add":
        if arg2 and arg3:
            if dicts.search(qwy.key == arg2):
                dicts.update({"value": arg3}, qwy.key == arg2)
                await ctx.send("辞書を変更しました。")
            else:
                dicts.insert({"key": arg2, "value": arg3})
                await ctx.send("辞書に追加しました。")
        else:
            await ctx.send("引数が足りません。")


@bot.command(name='join')
async def cmd_join(ctx):
    if ctx.message.guild:
        if ctx.message.author.voice is None:
            pass
        elif ctx.message.guild.voice_client:
            await ctx.message.guild.voice_client.move_to(ctx.message.author.voice.channel)
            chs[ctx.message.channel.id] = ctx.message.author.voice.channel
            await ctx.message.channel.send('VCに参加しました。')

            file = coefontTTS("接続しました。", get_voice(ctx.message.guild.id))
            if file:
                enqueue(ctx.message.guild.voice_client, ctx.message.guild,
                        FFmpegPCMAudio(source=file, executable=FFMEPG_LOCATION))
        else:
            await ctx.message.author.voice.channel.connect()
            chs[ctx.message.channel.id] = ctx.message.author.voice.channel
            await ctx.message.channel.send('VCに参加しました。')

            file = coefontTTS("接続しました。", get_voice(ctx.message.guild.id))
            if file:
                enqueue(ctx.message.guild.voice_client, ctx.message.guild,
                        FFmpegPCMAudio(source=file, executable=FFMEPG_LOCATION))


@bot.command(name='dc')
async def cmd_dc(ctx):
    if ctx.message.guild:
        if ctx.message.guild.voice_client is None:
            return await ctx.message.channel.send("VCに参加していません")
        else:
            try:
                await ctx.message.guild.voice_client.disconnect()
            except:
                await ctx.message.channel.send("VCから切断できませんでした")
            else:
                chs[ctx.message.channel.id] = None
                await ctx.message.channel.send("切断しました")


def coefontTTS(text, voice):
    hash = sha256(text)

    Path(f'voices/{voice}').mkdir(parents=True, exist_ok=True)

    if os.path.exists(f'voices/{voice}/{hash}.wav'):
        return f'voices/{voice}/{hash}.wav'
    else:
        signature = hmac.new(bytes(CF_SECRET, 'utf-8'), text.encode('utf-8'), hashlib.sha256).hexdigest()
        url = 'https://api.coefont.cloud/text2speech'
        response = requests.post(url, data=json.dumps({
            'coefont': voice,
            'text': text,
            'accesskey': CF_KEY,
            'signature': signature
        }), headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            with open(f'voices/{voice}/{sha256(text)}.wav', 'wb') as f:
                f.write(response.content)
            return f'voices/{voice}/{sha256(text)}.wav'
        else:
            return None


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


bot.run(TOKEN)
