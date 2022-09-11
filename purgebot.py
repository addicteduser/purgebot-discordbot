import asyncio
import os

import disnake
import disnake.ui
from disnake.ext import commands
from disnake.ui import Button, View
from dotenv import load_dotenv
from time import mktime
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()


command_prefix = commands.when_mentioned
description = "Salutations! I'm here to help clean up your rooms!"
intents = disnake.Intents.default()
bot = commands.Bot(
    case_insensitive=True,
    command_prefix=command_prefix,
    description=description,
    help_command=None,
    intents=intents,
    testguilds=[679218449024811067],
)

###################
## PURGE COMMAND ##
###################

(delay_in_seconds, delay_in_words) = (86400, "24 hours")
# (delay_in_seconds, delay_in_words) = (120, "2 minutes")


@bot.slash_command(default_member_permissions=disnake.Permissions(manage_channels=True))
async def purge(
    inter: disnake.MessageCommandInteraction,
    delay: bool = commands.Param(
        description=f"Delete channel in {delay_in_words}? (default: False)",
        default=False,
    ),
):
    """Deletes the current channel"""

    # Build UI
    btn_no = Button(style=disnake.ButtonStyle.secondary, label="No", custom_id="NO")
    btn_yes = Button(
        style=disnake.ButtonStyle.danger,
        label="Yes",
        emoji="⚠️",
        custom_id=f"YES_{str(delay)}",
    )
    component = View()
    component.add_item(btn_no)
    component.add_item(btn_yes)

    # Build bot reply
    bot_reply = f"Are you sure you want to delete <#{inter.channel_id}>"
    if delay:
        bot_reply = bot_reply + f" in {delay_in_words}"

    bot_reply = (
        bot_reply + "?\n\n*(Note: Once you click `Yes`, this cannot be cancelled!)*"
    )

    # Send response
    await inter.send(bot_reply, view=component, ephemeral=True)


#############################
## SET_LOG_CHANNEL COMMAND ##
#############################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def set_log_channel(
    inter: disnake.CommandInteraction,
    channel: disnake.TextChannel = commands.Param(
        description="The channel you want to send the PurgeBot logs to"
    ),
):
    """Sets which channel to send the PurgeBot logs"""
    set_log_channel_id(channel.id)
    await inter.send(f"PurgeBot logs will be sent to <#{channel.id}>!")


###################
## HELPER: PURGE ##
###################
def is_channel_valid_for_deletion(category_id):
    category_ids = os.getenv("CATEGORY_IDS")
    category_ids = category_ids.split(",")
    return str(category_id) in category_ids


async def delete_channel(inter: disnake.MessageInteraction, delay):
    if delay:
        await asyncio.sleep(delay_in_seconds)
    else:
        await asyncio.sleep(3)

    # Log event
    log_channel_id = get_log_channel_id()
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        embed = disnake.Embed(
            title=f"PurgeBot is done cleaning!",
            description=f"[{inter.author.mention}] #{inter.channel.name} has been deleted!",
        )
        await log_channel.send(embed=embed)

    await inter.channel.delete()


#####################
## HELPER: LOGGING ##
#####################
def get_log_channel_file():
    if os.path.exists("test_channel.txt"):
        return "test_channel.txt"
    else:
        return "channel.txt"


def get_log_channel_id():
    try:
        with open(get_log_channel_file(), "r") as f:
            channel_id = int(f.read())
    except:
        channel_id = None
    finally:
        return channel_id


def set_log_channel_id(channel_id):
    with open(get_log_channel_file(), "w") as f:
        f.write(str(channel_id))


############
## HELPER ##
############
def get_duration():
    # tomorrow = datetime.now() + timedelta(hours=24)
    tomorrow = datetime.now() + timedelta(minutes=2)
    unix = int(mktime(tomorrow.timetuple()))
    return f"<t:{unix}:R>"


########################
## DISCORD BOT EVENTS ##
########################
@bot.event
async def on_button_click(inter: disnake.MessageInteraction):
    # Handle "YES"
    if "YES" in inter.component.custom_id:

        # Check if channel is valid for deletion
        if is_channel_valid_for_deletion(inter.channel.category_id):
            delay = False
            if str(True) in inter.component.custom_id:
                delay = True

            message = f"Deleting #{inter.channel.name} (<#{inter.channel_id}>) "
            if delay:
                message = message + f"{get_duration()}"
            else:
                message = message + "in a few seconds"

            # Log event
            log_channel_id = get_log_channel_id()
            if log_channel_id:
                log_channel = bot.get_channel(log_channel_id)
                embed = disnake.Embed(
                    title=f"PurgeBot will clean soon...",
                    description=f"[{inter.author.mention}] {message}",
                )
                await log_channel.send(embed=embed)

            # Formulate and send reply
            bot_reply = f"Understood, {inter.author.mention}! {message}..."
            await inter.send(bot_reply)

            await delete_channel(inter, delay)
        else:
            await inter.send(
                f"Sorry, {inter.author.mention}. I'm not allowed to delete <#{inter.channel_id}>.",
                ephemeral=True,
            )

    # Handle "NO"
    elif inter.component.custom_id == "NO":
        await inter.send(
            f"Okay, {inter.author.mention}! I will **not** delete <#{inter.channel_id}>!",
            ephemeral=True,
        )


@bot.event
async def on_connect():
    print(f"{bot.user.name} has connected to Discord!")
    await bot.change_presence(
        activity=disnake.Activity(
            name="room purge! | /purge",
            type=disnake.ActivityType.playing,
        )
    )


@bot.event
async def on_ready():
    print(f"{bot.user.name} is live!")


#############
## TESTING ##
#############
# @bot.slash_command(guild_ids=[679218449024811067])
# async def test(inter: disnake.CommandInteraction):
#     """TEST"""
#     await inter.send(f"HELLO {get_duration()}")


#######################
## DISCORD BOT START ##
#######################
if __name__ == "__main__":
    token = os.getenv("PURGEBOT_DISCORD_TOKEN")
    bot.run(token)
