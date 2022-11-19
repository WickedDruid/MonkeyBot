import discord

from discord import app_commands
from tinydb import TinyDB, Query
from tinydb.operations import add, subtract

dbUsers = TinyDB('dbUsers.json')
dbBetsAmm = TinyDB('dbBetsAmm.json')
dbBets = TinyDB('dbBets.json')
User = Query()

myintents = discord.Intents.all()

class client(discord.Client):
    async def startup(self):
        await self.wait_until_ready()
        print('start')
        await tree.sync(guild = discord.Object(id = 826383276888686602))

aclient = client(intents=myintents)
tree = app_commands.CommandTree(aclient)

def powershell():
    dbUsers.truncate()


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


@aclient.event
async def on_ready():
    print('ready')

@aclient.event
async def on_message(msg):
    if msg.author == aclient.user:
        return
    priority = False
    for el in msg.author.roles:
        if (el.name == 'Admins'):
            priority = True
    if msg.content.startswith('$balance'):
        strq = msg.content
        if (len(strq) > 21):
            strq = strq[:len(strq) - 1]
            strq = strq[12:]
            if len(strq) == 18:
                if dbUsers.search(User.userID == int(strq)):
                    await msg.channel.send('This accounts balance is ' +
                                           show(int(strq)))
                else:
                    insert(int(strq))
                    await msg.channel.send('That accounts balance is ' +
                                           show(int(strq)))
            else:
                await msg.channel.send('Incorrect syntax, check again!'
                                       )  #syntax error
        else:
            strq = msg.author.id
            if dbUsers.search(User.userID == int(strq)):
                await msg.channel.send('Your accounts balance is ' +
                                       show(int(strq)))
            else:
                insert(int(strq))
                await msg.channel.send('Your accounts balance is ' +
                                       show(int(strq)))
    elif msg.content.startswith('$add'):
        if (priority):
            strq = msg.content
            strid = strq[:len(strq) - 1]
            strid = strid[len(strid) - 18:]
            stri = strq[:len(strq) - 22]
            stri = stri[5:]
            if dbUsers.search(User.userID == int(strid)):
                addmoney(int(stri), int(strid))  #add money to @ person
                await msg.channel.send(
                    stri + ' currency got added to the specified user')
            else:
                insert(int(strid))
                addmoney(int(stri), int(strid))  #add money to @ person
                await msg.channel.send(
                    stri + ' currency got added to the specified user')
        else:
            await msg.channel.send('Permission DENIED')
    elif msg.content.startswith('$subtract'):
        if (priority):
            strq = msg.content
            strid = strq[:len(strq) - 1]
            strid = strid[len(strid) - 18:]
            stri = strq[:len(strq) - 23]
            stri = stri[10:]
            if dbUsers.search(User.userID == int(strid)):
                submoney(int(stri), int(strid))  #subtract money from @ person
                await msg.channel.send(
                    stri + ' currency got removed from the specified user')
            else:
                insert(int(strid))
                submoney(int(stri), int(strid))  #subtract money from @ person
                await msg.channel.send(
                    stri + ' currency got removed from the specified user')
        else:
            await msg.channel.send('Permission DENIED')
    elif msg.content.startswith('$transfer'):
        strq = msg.content
        strid = strq[:len(strq) - 1]
        strid = strid[len(strid) - 18:]
        stri = strq[:len(strq) - 23]
        stri = stri[10:]
        if check(int(stri), int(msg.author.id)):
            addmoney(int(stri), int(strid))
            submoney(int(stri), int(msg.author.id))
        else:
            await msg.channel.send('Not enough currency')
    elif msg.content.startswith('$createbet') & priority:
        strq = msg.content
        strq = strq[11:]
        chunks = strq.split(' ')
        team1 = chunks[0]
        team2 = chunks[1]
        i = 0
        newbetid = 0
        while i <= 9:
            if (dbBets.search(User.ID == i)):
                i += 1
            else:
                newbetid = i
                break
        dbBets.insert({
            'value1': 0,
            'value2': 0,
            'ID': newbetid,
            'team1': team1,
            'team2': team2
        })
        embed = discord.Embed(
            title=team1 + ' vs ' + team2,
            description='The ID of this bet is: ' + str(newbetid) +
            ', remember you can not cancel your bet once placed. Betting after the match starts is prohibited and will result in a warning. Contact admins if neccesary.',
            color=0x464eb8)
        embed.add_field(name=team1,
                        value='to bet on this team, type "$bet ' +
                        str(newbetid) + ' X ' + team1 +
                        '", X being the amount you want to bet')
        embed.add_field(name=team2,
                        value='to bet on this team, type "$bet ' +
                        str(newbetid) + ' X ' + team2 +
                        '", X being the amount you want to bet')
        embed.set_author(name=msg.author.display_name,
                         icon_url=msg.author.avatar_url)
        await msg.channel.send(embed=embed)
    elif msg.content.startswith('$closebet') & priority:
        strq = msg.content
        strq = strq[10:]
        closeteam = strq[2:]
        betcloseid = int(strq[:1])
        currentbet = dbBets.get(User.ID == betcloseid)
        if (closeteam == currentbet['team1']):
            rightvalue = 'value1'
            leftvalue = 'value2'
        else:
            rightvalue = 'value2'
            leftvalue = 'value1'
        for bet in dbBetsAmm.search(User.betID == betcloseid):
            if (closeteam == bet['team']):
                newper = (bet['ammount'] / currentbet[rightvalue]) * 100
                newamm = (newper / 100) * currentbet[leftvalue]
                newamm = newamm + bet['ammount']
                dbUsers.update(add('money', int(newamm)),
                               User.userID == bet['playerID'])
            dbBetsAmm.remove(User.playerID == bet['playerID'])
        dbBets.remove(User.ID == betcloseid)
        await msg.channel.send('Bet ' + str(betcloseid) + ': ' + closeteam +
                               ' won, the rewards got sent')
    elif msg.content.startswith('$bet'):
        strq = msg.content
        strq = strq[5:]
        betID = int(strq[0])
        strq = strq[2:]
        exp = ''
        for el in strq:
            if el != ' ':
                exp = exp + el
            else:
                break
        bett = strq[len(exp) + 1:]
        betam = int(exp)
        playerID = int(msg.author.id)
        if dbBets.search((User.ID == betID)
                         & ((User.team1 == bett) | (User.team2 == bett))):
            if dbUsers.search((User.money >= int(betam))
                              & (User.userID == msg.author.id)):
                if dbBetsAmm.search(User.playerID == msg.author.id):
                    await msg.channel.send(
                        'You already have a bet placed on this match, please close that bet and try again'
                    )
                else:
                    bet = dbBets.get(User.ID == betID)
                    if bett == bet['team1']:
                        dbBets.update(add('value1', betam), User.ID == betID)
                    else:
                        dbBets.update(add('value2', betam), User.ID == betID)
                    submoney(betam, msg.author.id)
                    dbBetsAmm.insert({
                        'ammount': betam,
                        'betID': betID,
                        'playerID': playerID,
                        'team': bett
                    })
                    await msg.channel.send('Bet placed: ' + str(betam) +
                                           ' on team ' + bett)
            else:
                await msg.channel.send(
                    'Not enough currency to bet, no bet has been placed')
        else:
            await msg.channel.send(
                'ID or Team name is wrong, no bet has been placed')
    elif msg.content.startswith('$cancelbet') & priority:
        strq = msg.content
        strq = strq[11:]
        betID = int(strq)
        bet = dbBets.get(User.ID == betID)
        acc = dbBetsAmm.get(User.playerID == msg.author.id)
        addmoney(int(acc['ammount']), msg.author.id)
        if acc['team'] == bet['team1']:
            dbBets.update(subtract('value1', acc['ammount']), User.ID == betID)
        else:
            dbBets.update(subtract('value2', acc['ammount']), User.ID == betID)
        dbBetsAmm.remove((User.playerID == msg.author.id)
                         & (User.betID == betID))
        await msg.channel.send('Cancelled bet on match id: ' + str(betID))
    elif msg.content.startswith('$powershell') & priority:
        powershell()

@tree.command(guild = discord.Object(id = 826383276888686602), name = "balance", description = "Check your account balance")
async def balance(interaction: discord.Interaction):
  priority = False;
  for el in interaction.user.roles:
    if el.name == 'Admins':
      priority = True
  await interaction.channel.send('This accounts balance is ' + show(int(interaction.user.id)))


#replace token with bot token
aclient.run('token')
