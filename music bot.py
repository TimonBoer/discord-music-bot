import discord
from discord.ext import commands, tasks
from discord.utils import get
from discord import FFmpegPCMAudio
from youtube_dl import YoutubeDL
import time
import threading
import spotipy
import random
import os.path
import json
from spotipy.oauth2 import SpotifyClientCredentials

# check voor config bestand
file_exists = os.path.exists('config.json')
if os.path.exists('config.json') == False:
    # maak bestand aan
    print("There is no config file. Making a file...")
    config = {"bottoken": "???", "spotify-id": "???", "SpotifySecret": "???", "prefix": "."}
    with open('config.json', 'w') as f:
        json.dump(config, f)
    print("Setup the config file and restart python")
    exit()

# opening config file to read tokens
with open('config.json', 'r') as f:
    config = json.load(f)
    ## bottoken is dus config["bottoken"]


client = commands.Bot(command_prefix=config["prefix"])  # prefix our commands with '.'
token = config["bottoken"]

sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=config["spotify-id"], client_secret=config["SpotifySecret"]))

@client.event  # check if bot is ready
async def on_ready():
    global pause
    pause = False

    global queue
    queue = []

    global now
    now = -1

    global loop
    loop = True

    global end
    end = True

    global cnl
    cnl = ''

    global smsg
    smsg = ''

    print('Logged in as {0.user}'.format(client))


def convduration(duration):
    try:
        duration = int(duration)
        if duration < 3600:
            return time.strftime('%M:%S', time.gmtime(duration))
        elif duration < 3600*24:
            return time.strftime('%H:%M:%S', time.gmtime(duration))
        else:
            return time.strftime('%D:%H:%M:%S', time.gmtime(duration))
    except:
        return duration



def create_embed(title, color, info):
    embed = discord.Embed(title=title, description=f"[{info['title']}]({info['webpage_url']})", color=color) \
        .add_field(name='Duration', value=convduration(info['duration'])) \
        .add_field(name='Uploader', value=f"[{info['uploader']}]({info['uploader_url']})") \
        .set_thumbnail(url=info['thumbnail'])
    return embed


def download_task(song, item):
    global queue
    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}
    with YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info("ytsearch:%s" % song, download=False)['entries'][0]
    queue[item] = {'title': info['title'], 'duration': info['duration'], 'uploader': info['uploader'],
                  'webpage_url': info['webpage_url'], 'url': info['url'], 'thumbnail': info['thumbnail'],
                  'uploader_url': info['uploader_url']}



@tasks.loop(seconds=1)
async def SongPlayer(ctx):
    global pause
    global loop
    global queue
    global end
    global now
    global smsg
    global cnl
    FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
    voice = get(client.voice_clients, guild=ctx.guild)
    print('e')
    if voice:
        if len(queue) > 0:
            if now == len(queue) - 1:
                end = True
            else:
                end = False
            if not (end and not loop):
                try:
                    if not pause:
                        if end:
                            voice.play(FFmpegPCMAudio(queue[0]['url'], **FFMPEG_OPTIONS))
                            now = 0
                        else:
                            voice.play(FFmpegPCMAudio(queue[now + 1]['url'], **FFMPEG_OPTIONS))
                            now += 1

                        if smsg != '':
                            await smsg.delete()
                        smsg = await cnl.send(embed=create_embed(f'Now playing - {now + 1}', discord.Color.green(), queue[now]))
                        print('Playing: ' + queue[now]['title'])
                except:
                    ""
            # else:
            # print('End of queue')
        else:
            now = -1
    else:
        SongPlayer.stop()


# command for bot to join the channel of the user, if the bot has already joined and is in a different channel, it will move to the channel the user is in
@client.command(aliases=['j'])
async def join(ctx):
    global cnl
    cnl = ctx.message.channel
    try:
        channel = ctx.message.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            await channel.connect()
            SongPlayer.start(ctx)
    except:
        await ctx.message.channel.send('You are not connected to a voice channel')


# command to play sound from a youtube URL
@client.command(aliases=['p'])
async def play(ctx, *search):
    global end
    global queue
    global cnl
    cnl = ctx.message.channel
    search = ' '.join(search)

    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}
    voice = get(client.voice_clients, guild=ctx.guild)

    if not voice or not voice.is_connected():
        await join(ctx)
        voice = get(client.voice_clients, guild=ctx.guild)

    if voice:
        async with ctx.typing():
            code = search.split('/')[-1]
            links = []

            if search.lower() == 'radio 2':
                info = {'title': 'Radio 2', 'duration': 'Groter dan je moeder', 'uploader': 'Le interwebs',
                              'webpage_url': 'https://www.nporadio2.nl/', 'url': 'https://icecast.omroep.nl/radio2-bb-mp3',
                              'thumbnail': 'https://cdn.onlineradiobox.com/img/logo/6/9676.png', 'uploader_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}
                queue.append(info)
                await ctx.send(embed=create_embed('Added to queue', discord.Color.purple(), info))


            else:
                if "open.spotify.com/album" in search:
                    results = sp.album_tracks(code)
                    info = {'title': results['name'], 'uploader': results['owner']['display_name'],
                            'uploader_url': results['owner']['external_urls']['spotify'],
                            'webpage_url': results['external_urls']['spotify'],
                            'thumbnail': results['images'][0]['url'],
                            'duration': 0}
                    results = results['tracks']
                    tracks = results['items']

                    while results['next']:
                        results = sp.next(results)
                        tracks.extend(results['items'])

                    links = []

                    for track in tracks:
                        try:
                            links.append([track['name']])
                            for artist in track['artists']:
                                links[-1].append(artist['name'])
                        except:
                            pass

                if "open.spotify.com/playlist" in search:
                    results = sp.playlist_items(code)
                    info = {'title': results['name'], 'uploader': results['owner']['display_name'],
                            'uploader_url': results['owner']['external_urls']['spotify'],
                            'webpage_url': results['external_urls']['spotify'],
                            'thumbnail': results['images'][0]['url'],
                            'duration': 0}
                    results = results['tracks']
                    tracks = results['items']
                    while results['next']:
                        results = sp.next(results)
                        tracks.extend(results['items'])

                    links = []
                    for track in tracks:
                        try:
                            links.append([track['track']['name']])
                            for artist in track['track']['artists']:
                                links[-1].append(artist['name'])
                            info['duration'] += track['track']['duration_ms']
                        except:
                            pass
                    info['duration'] = info['duration']/1000
                    print(info)



                if links == []:
                    try:
                        with YoutubeDL(YDL_OPTIONS) as ydl:
                            info = ydl.extract_info("ytsearch:%s" % search, download=False)['entries'][0]

                        queue.append({'title': info['title'], 'duration': info['duration'], 'uploader': info['uploader'],
                                      'webpage_url': info['webpage_url'], 'url': info['url'],
                                      'thumbnail': info['thumbnail'], 'uploader_url': info['uploader_url']})

                        await ctx.send(embed=(create_embed('Added to queue', discord.Color.purple(), info)))
                        print(f"Added {info['title']}")
                    except Exception:
                        print('Error')
                else:
                    threads=[]
                    for track in links:
                        song = ' '.join(track)
                        thread = threading.Thread(target=download_task, args=(song, len(queue)))
                        threads.append(thread)
                        queue.append('')

                    for thread in threads:
                        thread.start()

                        # Wait for all the downloads to complete
                    for thread in threads:
                        thread.join()
                    await ctx.send(embed=create_embed('Added to queue', discord.Color.purple(), info))

@client.command(aliases=['radio'])
async def radio2(ctx, search):
    channel = ctx.message.author.voice.channel
    global player
    info = {'title': "Radio"}
    voice = get(client.voice_clients, guild=ctx.guild)

    if search == "radio2" :
        player.play(FFmpegPCMAudio('https://icecast.omroep.nl/radio2-bb-mp3'))

    elif search == "Qmusic" :
        player.play(FFmpegPCMAudio('https://23833.live.streamtheworld.com/QMUSICNLAAC_96.aac'))

    await ctx.message.add_reaction('📻')


@client.command()
async def jump(ctx, item):
    global now
    global pause
    global cnl
    cnl = ctx.message.channel
    voice = get(client.voice_clients, guild=ctx.guild)
    now = int(item) - 2
    pause = False
    voice.stop()
    await ctx.message.add_reaction('⤵️')



# command to resume voice if it is paused
@client.command()
async def resume(ctx):
    global pause
    global cnl
    cnl = ctx.message.channel
    voice = get(client.voice_clients, guild=ctx.guild)

    if not voice.is_playing():
        pause = False
        voice.resume()
        await ctx.message.add_reaction('⏯')


@client.command(aliases=['l'])
async def loop(ctx):
    global loop
    global cnl
    cnl = ctx.message.channel
    if loop:
        loop = False
        await ctx.message.add_reaction('❌')
    else:
        loop = True
        await ctx.message.add_reaction('🔁')


# command to pause voice if it is playing
@client.command(aliases=['stop'])
async def pause(ctx):
    global pause
    global cnl
    cnl = ctx.message.channel
    voice = get(client.voice_clients, guild=ctx.guild)

    if voice.is_playing():
        pause = True
        voice.pause()
        await ctx.message.add_reaction('⏸')


@client.command(aliases=['die'])
async def leave(ctx):
    global queue
    global smsg
    if smsg != '':
        await smsg.delete()
    smsg = ''
    queue = []
    voice = get(client.voice_clients, guild=ctx.guild)
    if voice:
        voice.stop()
        await voice.disconnect()
        SongPlayer.stop()
        await ctx.message.add_reaction('💀')


@client.command(aliases=['c'])
async def clear(ctx):
    global pause
    global queue
    global cnl
    global smsg
    cnl = ctx.message.channel
    queue = []
    if smsg != '':
        await smsg.delete()
    smsg = ''

    global now
    now = -1

    voice = get(client.voice_clients, guild=ctx.guild)
    if voice:
        pause = False
        voice.stop()
        await ctx.message.add_reaction('⏹')


@client.command(aliases=['now'])
async def current(ctx):
    global queue
    global now
    global cnl
    global smsg
    if smsg !='':
        smsg.delete()
    cnl = ctx.message.channel
    print(now)
    if now == -1:
        await ctx.message.channel.send('Not playing anything')
    else:
        smsg = await ctx.message.channel.send(
            embed=create_embed(f'Now playing - {now + 1}', discord.Color.green(), queue[now]))


@client.command(aliases=['skip', 'n'])
async def next(ctx):
    global pause
    global cnl
    cnl = ctx.message.channel
    voice = get(client.voice_clients, guild=ctx.guild)
    voice.stop()
    pause = False
    await ctx.message.add_reaction('⏯')


@client.command(aliases=['b'])
async def back(ctx):
    global pause
    global loop
    global queue
    global now
    global end
    global cnl
    cnl = ctx.message.channel

    if now != -1:
        if now == 0:
            if loop:
                now = len(queue) - 2
        else:
            now -= 2
            end = False

        voice = get(client.voice_clients, guild=ctx.guild)
        voice.stop()

        pause = False
        await ctx.message.add_reaction('◀️')


@client.command(aliases=['queue', 'q'])
async def queuereq(ctx):
    global queue
    global now
    global cnl
    cnl = ctx.message.channel
    msg = ''
    if len(queue) < 20:
        for x, info in enumerate(queue):
            if x == now:
                msg = msg + '**' + str(x + 1) + ' - ' + f"[{info['title']}]({info['webpage_url']})" + '**' + '\n'
            else:
                msg = msg + str(x + 1) + ' - ' + f"[{info['title']}]({info['webpage_url']})" + '\n'
    else:
        msg = '...\n'
        for x in range(now - 4, now + 16):
            if x == now:
                msg = msg + '**' + str(x + 1) + ' - ' + f"[{queue[x]['title']}]({queue[x]['webpage_url']})" + '**' + '\n'
            elif x > len(queue) - 1:
                msg = msg + str(x - len(queue) + 1) + ' - ' + f"[{queue[x - len(queue)]['title']}]({queue[x - len(queue)]['webpage_url']})" + '\n'
            elif x < 0:
                msg = msg + str(x + len(queue) + 1) + ' - ' + f"[{queue[x]['title']}]({queue[x]['webpage_url']})" + '\n'
            else:
                msg = msg + str(x + 1) + ' - ' + f"[{queue[x]['title']}]({queue[x]['webpage_url']})" + '\n'
        msg = msg + '...'

    if msg == '':
        await ctx.message.channel.send('Empty queue')
    else:
        await ctx.message.channel.send(
            embed=discord.Embed(title=f"Queue - {len(queue)}", description=msg, color=discord.Color.purple()))


@client.command()
async def remove(ctx, item):
    global cnl
    cnl = ctx.message.channel
    try:
        item = int(item)
        global queue
        global now
        voice = get(client.voice_clients, guild=ctx.guild)
        await ctx.message.channel.send(embed=create_embed('Removed song', discord.Color.red(), queue[item - 1]))
        del queue[item - 1]
        if now == item - 1:
            now -= 1
            voice.stop()
        elif now > item - 1:
            now -= 1
    except:
        return


@client.command(aliases=['sh'])
async def shuffle(ctx):
    global queue
    global now
    global cnl
    cnl = ctx.message.channel
    song = queue[now]['webpage_url']
    random.shuffle(queue)
    for x, info in enumerate(queue):
        if info['webpage_url'] == song:
            now = x
            await ctx.message.add_reaction('🔀')
            return


@client.command()
async def search(ctx, *search):
    search = ' '.join(search)
    global queue
    global cnl
    cnl = ctx.message.channel
    for x, info in enumerate(queue):
        if search.lower() in info['title'].lower():
            await ctx.send(embed=create_embed(f"Found at {x + 1}", discord.Color.blue(), info))
            return
    await ctx.send(f"{search} not found")

client.run(token)