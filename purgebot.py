import asyncio
import os

import disnake
import disnake.ui
from disnake.ext import commands
from disnake.ui import Button, View
from dotenv import load_dotenv

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
@bot.slash_command(
    default_member_permissions=disnake.Permissions(create_public_threads=True)
)
async def purge(
    inter: disnake.MessageCommandInteraction,
    delay: bool = commands.Param(
        description="Delay channel deletion by 24 hours? (default: False)",
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
        bot_reply = bot_reply + " in 24 hours"

    bot_reply = bot_reply + "?\n\n*(Note: This cannot be cancelled!)*"

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


############
## HELPER ##
############
async def delete_channel(channel: disnake.TextChannel, delay):
    if delay:
        await asyncio.sleep(36000)  # 10 hours
    else:
        await asyncio.sleep(3)

    log_channel_id = get_log_channel_id()
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        await log_channel.send(f"{channel.name} deleted!")

    await channel.delete()


def is_valid_for_deletion(category_id):
    category_ids = os.getenv("CATEGORY_IDS")
    category_ids = category_ids.split(",")
    return str(category_id) in category_ids


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


########################
## DISCORD BOT EVENTS ##
########################
@bot.event
async def on_button_click(inter: disnake.MessageInteraction):
    # Handle "YES"
    if "YES" in inter.component.custom_id:
        # Check if channel is valid for deletion
        if is_valid_for_deletion(inter.channel.category_id):
            delay = False
            if str(True) in inter.component.custom_id:
                delay = True

            # Log event
            log_channel_id = get_log_channel_id()
            if log_channel_id:
                log_channel = bot.get_channel(log_channel_id)
                log = f"{inter.author}: Initiated deletion of <#{inter.channel_id}> ({inter.channel.name}) in "
                if delay:
                    log = log + "24 hours"
                else:
                    log = log + "a few seconds"
                await log_channel.send(log)

            # Formulate and send reply
            bot_reply = (
                f"Got it, {inter.author.mention}! Deleting <#{inter.channel_id}> in "
            )
            if delay:
                bot_reply = bot_reply + "24 hours"
            else:
                bot_reply = bot_reply + "a few seconds"

            bot_reply = bot_reply + "..."

            await inter.send(bot_reply)
            await delete_channel(inter.channel, delay)
        else:
            await inter.send(
                f"Sorry, {inter.author.mention}. I'm not allowed to delete <#{inter.channel_id}>.",
                ephemeral=True,
            )

    # Handle "NO"
    elif inter.component.custom_id == "NO":
        await inter.send(
            f"Got it, {inter.author.mention}! Deleting <#{inter.channel_id}> cancelled!",
            ephemeral=True,
        )


@bot.event
async def on_connect():
    print(f"{bot.user.name} has connected to Discord!")
    await bot.change_presence(
        activity=disnake.Activity(
            name="room cleaning! | /purge",
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
#     await inter.send(f"{get_channel_file()}")


#######################
## DISCORD BOT START ##
#######################
if __name__ == "__main__":
    token = os.getenv("PURGEBOT_DISCORD_TOKEN")
    bot.run(token)
