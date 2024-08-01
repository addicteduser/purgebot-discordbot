import asyncio
import os
from datetime import datetime
from time import mktime

import dateparser
import disnake
import disnake.ui
from disnake import TextInputStyle, ButtonStyle
from disnake.ext import commands
from disnake.ui import Button, Modal, TextInput, View
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

BOT_IMAGE = os.getenv("BOT_IMAGE")


command_prefix = commands.when_mentioned
description = "Salutations! I'm here to help clean up your rooms!"
intents = disnake.Intents.default()
bot = commands.Bot(
    case_insensitive=True,
    command_prefix=command_prefix,
    description=description,
    help_command=None,
    intents=intents,
    test_guilds=[679218449024811067],
)


###################
## PURGE COMMAND ##
###################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_channels=True))
async def purge(inter: disnake.ApplicationCommandInteraction):
    """Deletes the current channel"""
    # Build Modal UI
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

    # Truncate channel name for modal title
    channel_name = inter.channel.name
    char_limit = 33
    title = (
        (channel_name[:char_limit] + "...")
        if len(channel_name) > char_limit
        else channel_name
    )

    modal = Modal(
        title=f"Delete #{title}?",
        custom_id="purge_modal",
        components=components,
        # timeout=5,
    )

    await inter.response.send_modal(modal=modal)


# @bot.slash_command(default_member_permissions=disnake.Permissions(manage_channels=True))
# async def purge(inter: disnake.ApplicationCommandInteraction):
#     """Deletes the current channel"""

#     async def timeout():
#         bot_reply = f"Sorry, {inter.author.mention}. You did not respond in time. Try again next time!"
#         await inter.edit_original_message(bot_reply)

#     # Build Modal UI
#     components = [
#         TextInput(
#             label="When? (leave blank if delete immediately)",
#             placeholder="Example: 'in two minutes', '1991-05-17', or similar",
#             custom_id="when",
#             style=TextInputStyle.short,
#             required=False,
#         ),
#         TextInput(
#             label="Custom message",
#             placeholder="Custom message you want PurgeBot to say",
#             custom_id="custom_msg",
#             style=TextInputStyle.paragraph,
#             required=False,
#         ),
#         TextInput(
#             label="Attachment",
#             placeholder="Link to image/GIF you want to attach to your custom message",
#             custom_id="attachment",
#             style=TextInputStyle.short,
#             required=False,
#         ),
#     ]

#     modal = Modal(
#         title=f"Delete #{inter.channel.name}?",
#         custom_id="purge_modal",
#         components=components,
#     )
#     # modal.on_timeout = timeout

#     await inter.response.send_modal(modal=modal)

#     try:
#         modal_inter: disnake.ModalInteraction = await bot.wait_for(
#             "modal_submit",
#             check=lambda i: i.custom_id == "purge_modal"
#             and i.author.id == inter.author.id,
#             timeout=5,
#         )
#     except asyncio.TimeoutError:
#         # Close modal on timeout here
#         # await inter.followup.
#         modal_inter = None

#     if modal_inter is None:
#         await inter.response.send_message("Cant process, timedout")


############################
## CHECK_CHANNELS COMMAND ##
############################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def check_channels(inter: disnake.ApplicationCommandInteraction):
    """List channels to be deleted"""

    async def purge_callback(inter_purge: disnake.MessageInteraction):
        content = ""
        with open(get_to_delete_file(inter.guild_id), "r") as f:
            lines = f.readlines()
            for line in lines:
                values = line.strip().split(",")
                channel_id = int(values[0])
                dt = values[1]
                if not is_when_valid(dt):
                    channel = bot.get_channel(channel_id)
                    if channel is not None:
                        content = content + f"- #{channel.name}"
                        update_to_delete(inter.guild_id, channel_id)
                        await channel.delete()

        embed = embed_builder("Mass-purged channels", content)

        # Log event
        await log_mass_delete(inter, content)

        # Send embed
        await inter_purge.send(embed=embed)

    has_old_dates = False

    # Build embed
    content = ""
    try:
        with open(get_to_delete_file(inter.guild_id), "r") as f:
            lines = f.readlines()
            for line in lines:
                values = line.strip().split(",")
                dt = values[1]
                if not is_when_valid(dt):
                    has_old_dates = True

                if values[1] != "-":
                    dt = dt_to_discord_date_duration(values[1])
                content = content + f"- <#{values[0]}>: {dt}\n"
    except FileNotFoundError:
        # Do nothing
        pass
    finally:
        if content == "":
            content = "None"

    embed = embed_builder("Channels scheduled to be purged", content)
    await inter.send(embed=embed)

    # Build Button UI
    btn_purge = Button(style=ButtonStyle.danger, label="Mass Purge", emoji="⚠️")
    btn_purge.callback = purge_callback

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
        description="The channel you want to send PurgeBot logs to"
    ),
):
    """Sets which channel to send PurgeBot logs"""
    set_log_channel_id(inter.guild_id, channel.id)
    await inter.send(f"PurgeBot logs will be sent to <#{channel.id}>!")


#################################
## ADD_DELETE_CATEGORY COMMAND ##
#################################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def add_delete_category(
    inter: disnake.CommandInteraction,
    category: disnake.CategoryChannel = commands.Param(
        description="The category where the channels for deletion belong to"
    ),
):
    """Adds a category to the list of categories PurgeBot will delete channels from"""
    append_delete_category_id(inter.guild_id, category.id)
    await inter.send(
        f"PurgeBot adds `{category.name}` to the list of categories it will only delete channels from!"
    )


####################################
## REMOVE_DELETE_CATEGORY COMMAND ##
####################################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def remove_delete_category(
    inter: disnake.CommandInteraction,
    category: disnake.CategoryChannel = commands.Param(
        description="The category where the channels for deletion belong to"
    ),
):
    """Removes a category to the list of categories PurgeBot will delete channels from"""
    remove_delete_category_id(inter.guild_id, category.id)
    await inter.send(
        f"PurgeBot removes `{category.name}` from the list of categories it will only delete channels from!"
    )


#############################
## PROTECT_CHANNEL COMMAND ##
#############################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def protect_channel(
    inter: disnake.CommandInteraction,
    channel: disnake.TextChannel = commands.Param(
        description="A channel you want to protect from deletion"
    ),
):
    """Adds a channel to the list of channels protected from PurgeBot"""
    protect_channel_id(inter.guild_id, channel.id)
    await inter.send(f"<#{channel.id}> is protected from PurgeBot deletion!")


###############################
## UNPROTECT_CHANNEL COMMAND ##
###############################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def unprotect_channel(
    inter: disnake.CommandInteraction,
    channel: disnake.TextChannel = commands.Param(
        description="A channel you want to remove from the protection list"
    ),
):
    """Removes a channel to the list of channels protected from PurgeBot"""
    unprotect_channel_id(inter.guild_id, channel.id)
    await inter.send(f"<#{channel.id}> is no longer protected from PurgeBot deletion!")


#########################
## VIEW_CONFIG COMMAND ##
#########################
@bot.slash_command(default_member_permissions=disnake.Permissions(manage_guild=True))
async def view_config(inter: disnake.CommandInteraction):
    """View current PurgeBot configuration"""

    log_channel = "Not set"
    log_channel_id = get_log_channel_id(inter.guild_id)
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)

        if log_channel:
            log_channel = f"<#{log_channel.id}>"
        else:
            # Remove if it does not exist
            set_log_channel_id(inter.guild_id, "")

    delete_categories = ""
    try:
        with open(get_delete_categories_file(inter.guild_id), "r") as f:
            ids = f.readlines()
            for id in ids:
                channel = bot.get_channel(int(id))
                if channel:
                    delete_categories = delete_categories + f"- {channel.name}\n"
                else:
                    # Remove if it does not exist
                    remove_delete_category_id(inter.guild_id, id)
    except FileNotFoundError:
        # Do nothing
        pass
    finally:
        if delete_categories == "":
            delete_categories = "None"

    protected_channels = ""
    try:
        with open(get_protected_channels_file(inter.guild_id), "r") as f:
            ids = f.readlines()
            for id in ids:
                channel = bot.get_channel(int(id))
                if channel:
                    protected_channels = protected_channels + f"- <#{channel.id}>\n"
                else:
                    # Remove if it does not exist
                    unprotect_channel_id(inter.guild_id, id)
    except FileNotFoundError:
        # Do nothing
        pass
    finally:
        if protected_channels == "":
            protected_channels = "None"

    # Build embed
    embed = embed_builder(
        "PurgeBot Configuration", "Here are you current configurations"
    )
    embed.add_field(name="Log Channel", value=log_channel, inline=False)
    embed.add_field(name="Delete Categories", value=delete_categories, inline=False)
    embed.add_field(name="Protected Channels", value=protected_channels, inline=False)

    await inter.send(embed=embed)


###################
## HELPER: PURGE ##
###################
def is_channel_valid_for_deletion(inter: disnake.MessageInteraction):
    log_channel_id = get_log_channel_id(inter.guild_id)
    if log_channel_id is None:
        log_channel_id = 0

    delete_category_ids = []
    try:
        with open(get_delete_categories_file(inter.guild_id), "r") as f:
            ids = f.readlines()
            for id in ids:
                channel = bot.get_channel(int(id))
                if channel:
                    delete_category_ids.append(channel.id)
                else:
                    # Remove if it does not exist
                    remove_delete_category_id(inter.guild_id, id)
    except FileNotFoundError:
        # Do nothing
        pass

    protected_channel_ids = []
    try:
        with open(get_protected_channels_file(inter.guild_id), "r") as f:
            ids = f.readlines()
            for id in ids:
                channel = bot.get_channel(int(id))
                if channel:
                    protected_channel_ids.append(channel.id)
                else:
                    # Remove if it does not exist
                    unprotect_channel_id(inter.guild_id, id)
    except FileNotFoundError:
        # Do nothing
        pass

    is_not_log_channel = inter.channel_id != log_channel_id
    is_in_delete_category = inter.channel.category_id in delete_category_ids
    is_not_protected = inter.channel_id not in protected_channel_ids

    return is_not_log_channel and is_in_delete_category and is_not_protected


async def delete_channel(inter: disnake.MessageInteraction, when_dt_str):
    # Set delay
    if when_dt_str == "-":
        await asyncio.sleep(3)
    else:
        when_to_delete = str_to_datetime(when_dt_str)
        now = datetime.now()
        delay_in_seconds = (when_to_delete - now).total_seconds()
        await asyncio.sleep(delay_in_seconds)

    try:
        # Delete channel
        await inter.channel.delete()

        # Log event
        await log_delete(inter)

    except disnake.errors.NotFound:
        # Do nothing
        pass


#####################
## HELPER: LOGGING ##
#####################
def get_log_channel_file(guild_id):
    return f"{guild_id}_log_channel.txt"


def get_log_channel_id(guild_id):
    try:
        with open(get_log_channel_file(guild_id), "r") as f:
            channel_id = int(f.read())
    except:
        channel_id = None
    finally:
        return channel_id


def set_log_channel_id(guild_id, channel_id):
    with open(get_log_channel_file(guild_id), "w+") as f:
        f.write(str(channel_id))


def get_delete_categories_file(guild_id):
    return f"{guild_id}_delete_categories.txt"


def append_delete_category_id(guild_id, category_id):
    with open(get_delete_categories_file(guild_id), "a+") as f:
        line = f"{category_id}\n"
        f.write(line)


def remove_delete_category_id(guild_id, category_id):
    filename = get_delete_categories_file(guild_id)
    updated_ids = []

    try:
        with open(filename, "r") as f:
            ids = f.readlines()
            for id in ids:
                if id.strip() != str(category_id):
                    updated_ids.append(id)
    except FileNotFoundError:
        # Do nothing
        pass
    finally:
        with open(filename, "w+") as f:
            f.writelines(updated_ids)


def get_protected_channels_file(guild_id):
    return f"{guild_id}_protected_channels.txt"


def protect_channel_id(guild_id, channel_id):
    with open(get_protected_channels_file(guild_id), "a+") as f:
        line = f"{channel_id}\n"
        f.write(line)


def unprotect_channel_id(guild_id, channel_id):
    filename = get_protected_channels_file(guild_id)
    updated_ids = []

    try:
        with open(filename, "r") as f:
            ids = f.readlines()
            for id in ids:
                if id.strip() != str(channel_id):
                    updated_ids.append(id)
    except FileNotFoundError:
        # Do nothing
        pass
    finally:
        with open(filename, "w+") as f:
            f.writelines(updated_ids)


def get_to_delete_file(guild_id):
    return f"{guild_id}_to_delete.txt"


def append_to_delete(guild_id, channel_id, when_dt_str):
    with open(get_to_delete_file(guild_id), "a+") as f:
        f.write(f"{channel_id},{when_dt_str}\n")


def update_to_delete(guild_id, channel_id):
    filename = get_to_delete_file(guild_id)
    updated_id_time_pairs = []

    try:
        with open(filename, "r") as f:
            id_time_pairs = f.readlines()
            for id_time in id_time_pairs:
                values = id_time.strip().split(",")
                if values[0] != str(channel_id):
                    updated_id_time_pairs.append(id_time)
    except FileNotFoundError:
        # Do nothing
        pass
    finally:
        with open(filename, "w+") as f:
            f.writelines(updated_id_time_pairs)


def embed_builder(title, description):
    embed = disnake.Embed(title=title, description=description)
    embed.set_author(name=bot.user.name, icon_url=BOT_IMAGE)
    return embed


async def log_attempt_to_delete(
    inter: disnake.MessageInteraction, message, channel_id, when_dt_str
):
    append_to_delete(inter.guild_id, channel_id, when_dt_str)
    log_channel_id = get_log_channel_id(inter.guild_id)
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        embed = embed_builder("PurgeBot will clean soon...", message)
        embed.add_field(
            name="Initiated by", value=f"{inter.author.mention}", inline=False
        )
        await log_channel.send(embed=embed)


async def log_delete(inter: disnake.MessageInteraction):
    update_to_delete(inter.guild_id, inter.channel_id)
    log_channel_id = get_log_channel_id(inter.guild_id)
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        embed = embed_builder(
            "PurgeBot is done cleaning!", f"#{inter.channel.name} has been deleted!"
        )
        embed.add_field(
            name="Initiated by", value=f"{inter.author.mention}", inline=False
        )
        await log_channel.send(embed=embed)


async def log_mass_delete(inter: disnake.MessageInteraction, content):
    log_channel_id = get_log_channel_id(inter.guild_id)
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        embed = embed_builder("PurgeBot is done cleaning! [MASS PURGE]", content)
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


########################
## DISCORD BOT EVENTS ##
########################
@bot.event
async def on_modal_submit(inter: disnake.ModalInteraction):
    if "purge_modal" == inter.custom_id:
        when = inter.text_values.get("when")
        when_dt_str = "-"
        if when != "":
            when_dt_str = parse_when(when)

        custom_msg = inter.text_values.get("custom_msg")
        attachment = inter.text_values.get("attachment")

        if when_dt_str is None:
            # If `when` cannot be parsed
            bot_reply = f"Sorry, {inter.author.mention}. I don't understand when you want me to delete the channel. You said: `{when}`"
            await inter.send(bot_reply, ephemeral=True)

        else:

            async def no_callback(inter_no: disnake.MessageInteraction):
                bot_reply = f"Okay, {inter.author.mention}! I will **not** delete <#{inter.channel_id}>!"
                await inter.edit_original_message(bot_reply, view=None)
                await inter_no.response.defer()

            async def yes_callback(inter_yes: disnake.MessageInteraction):
                # Check if when is still valid
                if is_when_valid(when_dt_str):

                    # Check if channel is valid for deletion
                    if is_channel_valid_for_deletion(inter):
                        message = (
                            f"Deleting #{inter.channel.name} (<#{inter.channel_id}>) "
                        )
                        if when_dt_str != "-":
                            embed_value = (
                                f"by {dt_to_discord_date_duration(when_dt_str)}"
                            )
                            # message = message + f"by {embed_value}"
                        else:
                            embed_value = "in a few seconds"

                        message = message + embed_value

                        # Log event
                        await log_attempt_to_delete(
                            inter, message, inter.channel_id, when_dt_str
                        )

                        # Send reply
                        bot_reply = (
                            f"Understood, {inter.author.mention}! {embed_value}..."
                        )
                        await inter.edit_original_message(bot_reply, view=None)

                        # Build embed
                        embed = embed_builder("Attention!", custom_msg)
                        embed.add_field(
                            name="This channel will be deleted",
                            value=embed_value,
                            inline=False,
                        )
                        embed.add_field(
                            name="Initiated by",
                            value=f"{inter.author.mention}",
                            inline=False,
                        )

                        if attachment:
                            embed.set_image(url=attachment)

                        await inter_yes.send(embed=embed)

                        # Delete channel
                        await delete_channel(inter, when_dt_str)

                    else:
                        bot_reply = f"Sorry, {inter.author.mention}. I'm not allowed to delete <#{inter.channel_id}>."
                        await inter.edit_original_message(bot_reply, view=None)
                        await inter_yes.response.defer()

                else:
                    bot_reply = f"Sorry, {inter.author.mention}. The date/time you told me to delete the channel has already happened."
                    await inter.edit_original_message(bot_reply, view=None)
                    await inter_yes.response.defer()

            async def timeout():
                bot_reply = f"Sorry, {inter.author.mention}. You did not respond in time. Try again next time!"
                await inter.edit_original_message(bot_reply, view=None)

            # Build Button UI
            btn_no = Button(style=ButtonStyle.secondary, label="No")
            btn_no.callback = no_callback

            btn_yes = Button(style=ButtonStyle.danger, label="Yes", emoji="⚠️")
            btn_yes.callback = yes_callback

            view = View(timeout=180)  # 3 minutes
            view.add_item(btn_no)
            view.add_item(btn_yes)
            view.on_timeout = timeout

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
