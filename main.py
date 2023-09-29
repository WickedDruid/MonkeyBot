import discord
import random
from discord import app_commands
from discord.ext import commands
from tinydb import TinyDB, Query
from tinydb.operations import add, subtract

dbUsers = TinyDB('dbUsers.json')
dbBetsAmm = TinyDB('dbBetsAmm.json')
dbBets = TinyDB('dbBets.json')
User = Query()

myintents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

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


@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready")
    try:
        sync = await bot.tree.sync()
        print(f"{bot.user.name} synced {len(sync)} commands")
    except Exception as e:
        print(e)

@bot.tree.command(name="balance")
async def balance(interaction: discord.Interaction):
    user = interaction.user.name
    log_file = open("log.txt", "a")
    log_file.write(f"\nbalance from {user}")
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
    log_file.write(f"\nlookup from {interaction.user.name}, target: {target}")
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
    log_file.write(f"\nadd from {interaction.user.name}, target: {target}, amount: {amount}")
    log_file.close()
    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command.')
        return
    if dbUsers.search(User.userID == target):
        addmoney(amount, target)  # add money to user
    else:
        insert(target)
        addmoney(amount, target)  # create account and add money to user
    await interaction.response.send_message(f"{amount} currency got added to {target}.")

@bot.tree.command(name="subtract")
@app_commands.describe(target="Target")
@app_commands.describe(amount="Amount")
async def sub_money(interaction: discord.Interaction, target: str, amount: int):
    log_file = open("log.txt", "a")
    log_file.write(f"\nsubtract from {interaction.user.name}, target: {target}, amount: {amount}")
    log_file.close()
    if not priority(interaction.user.roles):
        await interaction.response.send_message('You do not have the privileges to use this command')
        return
    if dbUsers.search(User.userID == target):
        submoney(amount, target)  # subtract money from user
    else:
        insert(target)
        submoney(amount, target)  # create account and subtract money from user
    await interaction.response.send_message(f"{amount} currency got removed from {target}.")

@bot.tree.command(name="transfer")
@app_commands.describe(target="Target")
@app_commands.describe(amount="Amount")
async def transfer_money(interaction: discord.Interaction, target: str, amount: int):
    Author = interaction.user.name
    log_file = open("log.txt", "a")
    log_file.write(f"\ntransfer from {Author}, target: {target}, amount: {amount}")
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
    log_file.write(f"\ncreate_bet from {interaction.user.name}, team1: {team1}, team2: {team2}")
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
    log_file.write(f"\nbalance from {interaction.user.name}, id: {id}, winner: {winner}")
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
            add_money(winnings, bet['userID'])
    dbBetsAmm.remove(User.betID == id)
    dbBets.remove(User.ID == id)
    await interaction.response.send_message('Bet ' + str(id) + ' : ' + winner + ' won, the rewards have been sent.')

@bot.tree.command(name="clear_data")
async def clear_data(interaction:discord.Interaction):
    log_file = open("log.txt", "a")
    log_file.write(f"\nclear_data from {interaction.user.name}")
    log_file.close()
    if interaction.user.name == 'wickedre':
        powershell()
        await interaction.response.send_message('Purged the database.')
    else:
        await interaction.response.send_message('Good try!')

#replace token with bot token
bot.run('ODI2MzgwNDAyNTIzNTA0NjQw.G6DmZ9.O66R57E46YlsVuylneua2lLiLJep0K4RG9G258')
