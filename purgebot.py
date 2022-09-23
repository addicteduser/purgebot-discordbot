import asyncio
import os

import disnake
import disnake.ui
from disnake.ext import commands
from disnake.ui import Button, View, TextInput, Modal
from dotenv import load_dotenv
from time import mktime
from datetime import datetime, timedelta
from disnake import TextInputStyle
import dateparser

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
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_channels=True))
async def purge(inter: disnake.ApplicationCommandInteraction):
    """Deletes the current channel"""
    # Build UI
    components = [
        TextInput(
            label="When? (leave blank if delete immediately)",
            placeholder="Example: 'in two minutes', '1991-05-17', or similar",
            custom_id="when",
            style=TextInputStyle.short,
            required=False,
        ),
        TextInput(
            label="Custom message",
            placeholder="Custom message you want PurgeBot to say",
            custom_id="custom_msg",
            style=TextInputStyle.paragraph,
            required=False,
        ),
        TextInput(
            label="Attachment",
            placeholder="Link to image/GIF you want to attach to your custom message",
            custom_id="attachment",
            style=TextInputStyle.short,
            required=False,
        ),
    ]

    modal = Modal(
        title=f"Delete #{inter.channel.name}?",
        custom_id="purge_modal",
        components=components,
        timeout=10,
    )

    await inter.response.send_modal(modal=modal)


############################
## CHECK_CHANNELS COMMAND ##
############################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def check_channels(inter: disnake.ApplicationCommandInteraction):
    """List channels to be deleted"""
    has_old_dates = False

    # Build embed
    content = ""
    with open(get_to_delete_file(), "r") as f:
        lines = f.readlines()
        for line in lines:
            values = line.strip().split(",")
            dt = values[1]
            if not is_when_valid(dt):
                has_old_dates = True

            if values[1] != "-":
                dt = dt_to_discord_date_duration(values[1])
            content = content + f"- <#{values[0]}>: {dt}\n"
    embed = disnake.Embed(
        title=f"Channels scheduled to be purged",
        description=content,
    )
    embed.set_author(
        name=bot.user.name,
        icon_url="https://cdn.discordapp.com/attachments/594077092183015431/1022865776350351370/Untitled.png",
    )

    await inter.send(embed=embed)

    # Build buttons
    btn_purge = Button(
        style=disnake.ButtonStyle.danger,
        label="Mass Purge",
        emoji="⚠️",
        custom_id=f"PURGE",
    )
    view = View()
    view.add_item(btn_purge)

    if has_old_dates:
        bot_reply = (
            "Looks like there were still some old channels that need to be cleaned..."
        )
        await inter.send(bot_reply, view=view, ephemeral=True)


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


async def delete_channel(inter: disnake.MessageInteraction, when_dt_str):
    if when_dt_str == "-":
        await asyncio.sleep(3)
    else:
        when_to_delete = str_to_datetime(when_dt_str)
        now = datetime.now()
        delay_in_seconds = (when_to_delete - now).total_seconds()
        await asyncio.sleep(delay_in_seconds)

    # Log event
    await log_delete(inter)

    await inter.channel.delete()


async def mass_purge(inter: disnake.MessageInteraction):
    content = ""
    with open(get_to_delete_file(), "r") as f:
        lines = f.readlines()
        for line in lines:
            values = line.strip().split(",")
            channel_id = int(values[0])
            dt = values[1]
            if not is_when_valid(dt):
                channel = bot.get_channel(channel_id)
                content = content + f"- #{channel.name}"
                update_to_delete(channel_id)
                await channel.delete()

    embed = disnake.Embed(
        title=f"Mass-purged channels",
        description=content,
    )
    embed.set_author(
        name=bot.user.name,
        icon_url="https://cdn.discordapp.com/attachments/594077092183015431/1022865776350351370/Untitled.png",
    )

    # Log event
    await log_mass_delete(inter, content)

    await inter.send(embed=embed)


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


def get_to_delete_file():
    if os.path.exists("test_to_delete.txt"):
        return "test_to_delete.txt"
    else:
        return "to_delete.txt"


def append_to_delete(channel_id, when_dt_str):
    with open(get_to_delete_file(), "a") as f:
        f.write(f"{channel_id},{when_dt_str}\n")


async def log_attempt_to_delete(
    inter: disnake.MessageInteraction, message, channel_id, when_dt_str
):
    append_to_delete(channel_id, when_dt_str)
    log_channel_id = get_log_channel_id()
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        embed = disnake.Embed(
            title=f"PurgeBot will clean soon...",
            description=message,
        )
        embed.set_author(
            name=bot.user.name,
            icon_url="https://cdn.discordapp.com/attachments/594077092183015431/1022865776350351370/Untitled.png",
        )
        embed.add_field(
            name="Initiated by", value=f"{inter.author.mention}", inline=False
        )
        await log_channel.send(embed=embed)


def update_to_delete(channel_id):
    new_lines = []
    with open(get_to_delete_file(), "r") as f:
        lines = f.readlines()
        for line in lines:
            values = line.strip().split(",")
            if values[0] != str(channel_id):
                new_lines.append(line)

    with open(get_to_delete_file(), "w") as f:
        f.writelines(new_lines)


async def log_delete(inter: disnake.MessageInteraction):
    update_to_delete(inter.channel_id)
    log_channel_id = get_log_channel_id()
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        embed = disnake.Embed(
            title=f"PurgeBot is done cleaning!",
            description=f"#{inter.channel.name} has been deleted!",
        )
        embed.set_author(
            name=bot.user.name,
            icon_url="https://cdn.discordapp.com/attachments/594077092183015431/1022865776350351370/Untitled.png",
        )
        embed.add_field(
            name="Initiated by", value=f"{inter.author.mention}", inline=False
        )
        await log_channel.send(embed=embed)


async def log_mass_delete(inter: disnake.MessageInteraction, content):
    log_channel_id = get_log_channel_id()
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        embed = disnake.Embed(
            title=f"PurgeBot is done cleaning! [MASS PURGE]",
            description=content,
        )
        embed.set_author(
            name=bot.user.name,
            icon_url="https://cdn.discordapp.com/attachments/594077092183015431/1022865776350351370/Untitled.png",
        )
        embed.add_field(
            name="Initiated by", value=f"{inter.author.mention}", inline=False
        )
        await log_channel.send(embed=embed)


############
## HELPER ##
############
DATE_TIME_FORMAT = "%Y%m%d%H%M%S"


def to_unix(dt: datetime):
    return int(mktime(dt.timetuple()))


def str_to_datetime(dt_str):
    return datetime.strptime(dt_str, DATE_TIME_FORMAT)


def datetime_to_str(dt: datetime):
    return dt.strftime(DATE_TIME_FORMAT)


def dt_to_discord_date_duration(dt_str):
    dt = str_to_datetime(dt_str)
    unix = to_unix(dt)
    return f"<t:{unix}:F> (<t:{unix}:R>)"


def parse_when(when):
    when_parsed = dateparser.parse(when)
    if when_parsed:
        return datetime_to_str(when_parsed)
    else:
        return None


def is_when_valid(dt_str):
    if dt_str == "-":
        return True

    when_to_delete = str_to_datetime(dt_str)
    now = datetime.now()
    return "-" not in str(when_to_delete - now)


# when_dt_str = None
custom_msg = None
attachment = None


def reset_globals():
    # global when_dt_str
    # when_dt_str = None
    global custom_msg
    custom_msg = None
    global attachment
    attachment = None


########################
## DISCORD BOT EVENTS ##
########################
@bot.event
async def on_modal_submit(inter: disnake.ModalInteraction):
    if "purge_modal" == inter.custom_id:
        # global when_dt_str
        when = inter.text_values.get("when")
        when_dt_str = "-"
        if when != "":
            when_dt_str = parse_when(when)

        global custom_msg
        custom_msg = inter.text_values.get("custom_msg")
        # if custom_msg == "":
        #     custom_msg = "-"

        global attachment
        attachment = inter.text_values.get("attachment")
        # if attachment == "":
        #     attachment = "-"

        if when_dt_str is None:
            # If `when` cannot be parsed
            bot_reply = f"Sorry, {inter.author.mention}. I don't understand when you want me to delete the channel: `{when}`"
            await inter.send(bot_reply, ephemeral=True)

        else:
            # Build UI
            btn_no = Button(
                style=disnake.ButtonStyle.secondary, label="No", custom_id="NO"
            )
            btn_yes = Button(
                style=disnake.ButtonStyle.danger,
                label="Yes",
                emoji="⚠️",
                custom_id=f"YES//{str(when_dt_str)}"
                # custom_id=f"YES/////{str(when_dt_str)}/////{custom_msg}/////{attachment}",
            )
            view = View()
            view.add_item(btn_no)
            view.add_item(btn_yes)

            # Build bot reply
            bot_reply = f"{inter.author.mention}, are you sure you want to delete <#{inter.channel_id}>"
            if when_dt_str != "-":
                bot_reply = (
                    bot_reply + f" by {dt_to_discord_date_duration(when_dt_str)}"
                )

            bot_reply = (
                bot_reply
                + "?\n\n*(Note: Once you click `Yes`, this cannot be cancelled!)*"
            )

            # Send response
            await inter.send(bot_reply, view=view, ephemeral=True)


@bot.event
async def on_button_click(inter: disnake.MessageInteraction):
    # Handle "YES"
    if "YES" in inter.component.custom_id:
        # Parse values
        values = inter.component.custom_id.split("//")
        when_dt_str = values[1]
        # custom_msg = values[2]
        # attachment = values[3]
        # global when_dt_str
        global custom_msg
        global attachment

        # Check if when is still valid
        if is_when_valid(when_dt_str):

            # Check if channel is valid for deletion
            if is_channel_valid_for_deletion(inter.channel.category_id):
                message = f"Deleting #{inter.channel.name} (<#{inter.channel_id}>) "
                if when_dt_str != "-":
                    embed_value = f"by {dt_to_discord_date_duration(when_dt_str)}"
                    message = message + f"by {embed_value}"
                else:
                    embed_value = "in a few seconds"
                    message = message + embed_value

                # Log event
                await log_attempt_to_delete(
                    inter, message, inter.channel_id, when_dt_str
                )

                # Formulate reply
                # bot_reply = f"Understood, {inter.author.mention}! {message}..."

                # Build embed
                embed = disnake.Embed(
                    title=f"Attention!",
                    description=custom_msg,
                )
                embed.set_author(
                    name=bot.user.name,
                    icon_url="https://cdn.discordapp.com/attachments/594077092183015431/1022865776350351370/Untitled.png",
                )
                embed.add_field(
                    name="This channel will be deleted", value=embed_value, inline=False
                )
                embed.add_field(
                    name="Initiated by", value=f"{inter.author.mention}", inline=False
                )

                if attachment:
                    embed.set_image(url=attachment)

                # Send reply
                await inter.send(embed=embed)
                reset_globals()

                # Delete channel
                await delete_channel(inter, when_dt_str)

            else:
                reset_globals()
                bot_reply = f"Sorry, {inter.author.mention}. I'm not allowed to delete <#{inter.channel_id}>."
                await inter.send(bot_reply, ephemeral=True)

        else:
            reset_globals()
            bot_reply = f"Sorry, {inter.author.mention}. The date/time you told me to delete the channel has already happened."
            await inter.send(bot_reply, ephemeral=True)

    # Handle "NO"
    elif "NO" == inter.component.custom_id:
        reset_globals()
        bot_reply = f"Okay, {inter.author.mention}! I will **not** delete <#{inter.channel_id}>!"
        await inter.send(bot_reply, ephemeral=True)

    elif "PURGE" == inter.component.custom_id:
        await mass_purge(inter)


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


@bot.event
async def on_disconnect():
    print(f"{bot.user.name} is has been disconnected from Discord!")


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
