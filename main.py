import discord
import subprocess
import asyncio
import a2s
import re
import sys
import socket
import os
import random
from datetime import datetime
from discord import app_commands
from discord.ext import commands, tasks
from tinydb import TinyDB, Query
from tinydb.operations import add, subtract
from dotenv import load_dotenv
from mcstatus import JavaServer

# --- HOMELAB CONFIGURATION ---
SERVER_IP = "192.168.1.135"
SERVER_MAC = "b4:2e:99:9e:db:7e"
MC_PORT = 25565
PZ_PORT = 16261

HOMELAB_USER = "hosting" 
MC_START_CMD = "screen -dmS mc /home/hosting/minecraft/start-server.sh"
PZ_START_CMD = "screen -dmS zomboid /home/hosting/pzserver/start-server.sh"
# -----------------------------

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

dbUsers = TinyDB('dbUsers.json')
dbBetsAmm = TinyDB('dbBetsAmm.json')
dbBets = TinyDB('dbBets.json')
User = Query()

myintents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Tracking for auto-shutdowns
activity_state = {
    "mc_empty_mins": 0,
    "pz_empty_mins": 0,
    "homelab_offline_mins": 0
}

# ----- BETTING & ECONOMY UTILITIES -----
def powershell():
    dbUsers.truncate()
    dbBets.truncate()
    dbBetsAmm.truncate()

def insert(userx):
    dbUsers.insert({'userID': userx, 'money': 0})

def addmoney(moneya, userx):
    dbUsers.update(add('money', moneya), User.userID == userx)

def submoney(moneya, userx):
    dbUsers.update(subtract('money', moneya), User.userID == userx)

def show(userx):
    current = dbUsers.get(User.userID == userx)
    return str(current['money'])

def check(moneya, userx):
    if dbUsers.search((User.userID == userx) & (User.money >= moneya)):
        return True
    else:
        return False

def priority(roles):
    priority = False
    for el in roles:
        if str(el) == 'Admins':
            priority = True
    if priority:
        return True
    else:
        return False

# ----- ASYNC NETWORK UTILITIES -----
async def run_ssh_command(command: str):
    cmd = f"ssh {HOMELAB_USER}@{SERVER_IP} \"{command}\""
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.communicate()

async def is_host_online(ip: str, timeout_seconds: int = 1) -> bool:
    command = f"ping -c 2 -W {timeout_seconds} {ip}"
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.communicate()
    return process.returncode == 0

def send_wol(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> None:
    cleaned_mac = re.sub(r"[:\.-]", "", mac_address)
    if len(cleaned_mac) != 12:
        raise ValueError(f"Invalid MAC address format")
    mac_bytes = bytes.fromhex(cleaned_mac)
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (broadcast_ip, port))

def is_mc_open(ip: str, port: int, timeout_seconds: int = 1) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_seconds)
        result = sock.connect_ex((ip, port)) 
        return result == 0

def is_zomboid_open(ip: str, port: int, timeout_seconds: int = 1) -> bool:
    payload = b'\xff\xff\xff\xffTSource Engine Query\x00'
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout_seconds)
        try:
            sock.sendto(payload, (ip, port))
            data, _ = sock.recvfrom(1024)
            return len(data) > 0
        except socket.timeout:
            return False
        except Exception:
            return False

# ----- BACKGROUND MONITORING TASK -----
@tasks.loop(minutes=1.0)
async def server_monitor():
    if not await is_host_online(SERVER_IP):
        activity_state["homelab_offline_mins"] = 0
        activity_state["mc_empty_mins"] = 0
        activity_state["pz_empty_mins"] = 0
        return

    mc_players = -1
    try:
        if is_mc_open(SERVER_IP, MC_PORT):
            mc_server = JavaServer.lookup(f"{SERVER_IP}:{MC_PORT}")
            mc_players = mc_server.status().players.online
    except Exception:
        pass

    pz_players = -1
    try:
        if is_zomboid_open(SERVER_IP, PZ_PORT):
            info = a2s.info((SERVER_IP, PZ_PORT), timeout=2.0)
            pz_players = info.player_count
    except Exception:
        pass

    if mc_players == 0:
        activity_state["mc_empty_mins"] += 1
        if activity_state["mc_empty_mins"] >= 10:
            print("Minecraft inactive for 10 mins. Stopping...")
            await run_ssh_command("screen -S mc -X stuff 'stop\n'")
            activity_state["mc_empty_mins"] = -999 
    elif mc_players > 0:
        activity_state["mc_empty_mins"] = 0

    if pz_players == 0:
        activity_state["pz_empty_mins"] += 1
        if activity_state["pz_empty_mins"] >= 10:
            print("Zomboid inactive for 10 mins. Stopping...")
            await run_ssh_command("screen -S zomboid -X stuff 'quit\n'")
            activity_state["pz_empty_mins"] = -999
    elif pz_players > 0:
        activity_state["pz_empty_mins"] = 0

    if mc_players == -1 and pz_players == -1:
        activity_state["homelab_offline_mins"] += 1
        if activity_state["homelab_offline_mins"] >= 15:
            print("Servers offline for 15 minutes. Shutting down homelab...")
            await run_ssh_command("sudo shutdown now")
            activity_state["homelab_offline_mins"] = 0
    else:
        activity_state["homelab_offline_mins"] = 0

@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready")
    
    if not server_monitor.is_running():
        server_monitor.start()

    try:
        sync = await bot.tree.sync()
        print(f"{bot.user.name} synced {len(sync)} commands")
    except Exception as e:
        print(e)


# ----- ECONOMY & BETTING COMMANDS -----
@bot.tree.command(name="balance")
async def balance(interaction: discord.Interaction):
    user = interaction.user.name
    log_file = open("log.txt", "a")
    log_file.write(f"\nbalance from {user}, {str(datetime.now())}")
    log_file.close()
    if dbUsers.search(User.userID == user):
        await interaction.response.send_message(f"Your accounts balance is {show(user)}.")
    else:
        insert(user)
        await interaction.response.send_message(f"Your accounts balance is {show(user)}.")

@bot.tree.command(name="lookup")
@app_commands.describe(target="Target")
async def look_up(interaction: discord.Interaction, target: str):
    log_file = open("log.txt", "a")
    log_file.write(f"\nlookup from {interaction.user.name}, target: {target}, {str(datetime.now())}")
    log_file.close()
    if dbUsers.search(User.userID == target):
        await interaction.response.send_message(f"This accounts balance is {show(target)}.")
    else:
        insert(target)
        await interaction.response.send_message(f"This accounts balance is {show(target)}.")

@bot.tree.command(name="add")
@app_commands.describe(target="Target")
@app_commands.describe(amount="Amount")
async def add_money(interaction: discord.Interaction, target: str, amount: int):
    log_file = open("log.txt", "a")
    log_file.write(f"\nadd from {interaction.user.name}, target: {target}, amount: {amount}, {str(datetime.now())}")
    log_file.close()
    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command.')
        return
    if dbUsers.search(User.userID == target):
        addmoney(amount, target)  
    else:
        insert(target)
        addmoney(amount, target)  
    await interaction.response.send_message(f"{amount} currency got added to {target}.")

@bot.tree.command(name="subtract")
@app_commands.describe(target="Target")
@app_commands.describe(amount="Amount")
async def sub_money(interaction: discord.Interaction, target: str, amount: int):
    log_file = open("log.txt", "a")
    log_file.write(f"\nsubtract from {interaction.user.name}, target: {target}, amount: {amount}, {str(datetime.now())}")
    log_file.close()
    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command')
        return
    if dbUsers.search(User.userID == target):
        submoney(amount, target)  
    else:
        insert(target)
        submoney(amount, target)  
    await interaction.response.send_message(f"{amount} currency got removed from {target}.")

@bot.tree.command(name="transfer")
@app_commands.describe(target="Target")
@app_commands.describe(amount="Amount")
async def transfer_money(interaction: discord.Interaction, target: str, amount: int):
    Author = interaction.user.name
    log_file = open("log.txt", "a")
    log_file.write(f"\ntransfer from {Author}, target: {target}, amount: {amount}, {str(datetime.now())}")
    log_file.close()
    if not dbUsers.search(User.userID == Author):
        insert(Author)
        await interaction.response.send_message('Not enough currency!')
    else:
        if check(amount, Author):
            if not dbUsers.search(User.userID == target):
                insert(target)
            submoney(amount, Author)
            addmoney(amount, target)
            await interaction.response.send_message(f"{amount} transferred to {target}.")
        else:
            await interaction.response.send_message('Not enough currency!')

@bot.tree.command(name="create_bet")
@app_commands.describe(team1="First team")
@app_commands.describe(team2="Second team")
async def create_bet(interaction: discord.Interaction, team1: str, team2: str):
    log_file = open("log.txt", "a")
    log_file.write(f"\ncreate_bet from {interaction.user.name}, team1: {team1}, team2: {team2}, {str(datetime.now())}")
    log_file.close()
    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command.')
        return
    i = 0
    bet_id = -1
    while 1:
        if dbBets.search(User.ID == i):
            i += 1
        else:
            bet_id = i
            break
    dbBets.insert({
        'team1_totals': 0,
        'team2_totals': 0,
        'ID': bet_id,
        'team1': team1,
        'team2': team2
    })
    announcement = discord.Embed(
        title=team1 + ' vs ' + team2,
        description='To bet on this match, use the following ID: ' + str(bet_id),
        color=0xBDE038
    )
    announcement.set_author(name=interaction.user.name, icon_url=interaction.user.avatar)
    await interaction.response.send_message(embed=announcement)

@bot.tree.command(name="close_bet")
@app_commands.describe(id="ID")
@app_commands.describe(winner="winner")
async def close_bet(interaction: discord.Interaction, id: int, winner: str):
    log_file = open("log.txt", "a")
    log_file.write(f"\nbalance from {interaction.user.name}, id: {id}, winner: {winner}, {str(datetime.now())}")
    log_file.close()
    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command.')
        return
    standing_bet = dbBets.get(User.ID == id)
    if winner == standing_bet['team1']:
        winning_pot = 'team1_totals'
        losing_pot = 'team2_totals'
    else:
        winning_pot = 'team2_totals'
        losing_pot = 'team1_totals'
    for bet in dbBetsAmm.search(User.betID == id):
        if winner == bet['team']:
            percentage = bet['ammount'] / standing_bet[winning_pot]
            winnings = percentage * standing_bet[losing_pot]
            addmoney(winnings, bet['userID'])
    dbBetsAmm.remove(User.betID == id)
    dbBets.remove(User.ID == id)
    await interaction.response.send_message('Bet ' + str(id) + ' : ' + winner + ' won, the rewards have been sent.')

@bot.tree.command(name="clear_data")
async def clear_data(interaction:discord.Interaction):
    log_file = open("log.txt", "a")
    log_file.write(f"\nclear_data from {interaction.user.name}, {str(datetime.now())}")
    log_file.close()
    if interaction.user.name == 'wickedre':
        powershell()
        await interaction.response.send_message('Purged the database.')
    else:
        await interaction.response.send_message('Good try!')


# ----- SERVER MANAGEMENT COMMANDS -----
@bot.tree.command(name="startpz", description="Starts the Project Zomboid server")
async def start_pz(interaction: discord.Interaction):
    log_file = open("log.txt", "a")
    log_file.write(f"\nstartpz from {interaction.user.name}, {str(datetime.now())}")
    log_file.close()

    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command')
        return

    if await is_host_online(SERVER_IP):
        if is_zomboid_open(SERVER_IP, PZ_PORT):
            await interaction.response.send_message("The server is already running or currently booting up")
        else:
            await interaction.response.send_message("Starting Project Zomboid server! It should be online in a minute or two.")
            await run_ssh_command(PZ_START_CMD)
    else:
        # 1. Acknowledge immediately so the Discord command doesn't time out
        await interaction.response.send_message("Powering on the HomeLab! The Zomboid server will start automatically in 2 minutes.")
        
        # 2. Send the Wake-on-LAN packet
        send_wol(SERVER_MAC)
        
        # 3. Wait asynchronously for 120 seconds (does not freeze the bot)
        await asyncio.sleep(120)
        
        # 4. Start the server
        await run_ssh_command(PZ_START_CMD)
        
        # 5. Ping the user so they know it's ready
        await interaction.followup.send(f"{interaction.user.mention}, the HomeLab is booted and Project Zomboid is starting!")

@bot.tree.command(name="startmc", description="Starts the Craftoria Minecraft server") 
async def start_mc(interaction: discord.Interaction):
    log_file = open("log.txt", "a")
    log_file.write(f"\nstartmc from {interaction.user.name}, {str(datetime.now())}")
    log_file.close()

    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command')
        return

    if await is_host_online(SERVER_IP):
        if is_mc_open(SERVER_IP, MC_PORT): 
            await interaction.response.send_message('The HomeLab is ONLINE. The MC Server is also ONLINE')
        else:
            await interaction.response.send_message('The HomeLab is ONLINE. Starting MC server now...')
            await run_ssh_command(MC_START_CMD)
    else:
        # 1. Acknowledge immediately so the Discord command doesn't time out
        await interaction.response.send_message('Powering on the HomeLab! The Minecraft server will start automatically in 2 minutes.')
        
        # 2. Send the Wake-on-LAN packet
        send_wol(SERVER_MAC)
        
        # 3. Wait asynchronously for 120 seconds (does not freeze the bot)
        await asyncio.sleep(120)
        
        # 4. Start the server
        await run_ssh_command(MC_START_CMD)
        
        # 5. Ping the user so they know it's ready
        await interaction.followup.send(f"{interaction.user.mention}, the HomeLab is booted and Minecraft is starting!")

bot.run(TOKEN)