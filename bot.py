import discord
import re
import random
import math
import os
from discord.ext import commands

# ── Config ──────────────────────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN", "SEU_TOKEN_AQUI")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ── Dice regex ───────────────────────────────────────────────────────────────
# Matches expressions like: 1d20, 3d6, 10d100, 1d20+1d4, 1d4+1d20/2-5d4*2
DICE_PATTERN = re.compile(r'\b(\d+)d(\d+)\b', re.IGNORECASE)
VALID_EXPR_PATTERN = re.compile(
    r'^[\d\s\+\-\*\/\(\)\.d]+$', re.IGNORECASE
)

MAX_DICE = 100
MAX_SIDES = 100000


def roll_dice(num: int, sides: int) -> list[int]:
    """Roll num dice with given sides."""
    if num < 1 or num > MAX_DICE:
        raise ValueError(f"Número de dados deve ser entre 1 e {MAX_DICE}. Recebeu: {num}")
    if sides < 1 or sides > MAX_SIDES:
        raise ValueError(f"Número de faces deve ser entre 1 e {MAX_SIDES}. Recebeu: {sides}")
    return [random.randint(1, sides) for _ in range(num)]


def parse_and_roll(expression: str):
    """
    Parse a dice expression like '1d20+1d4/2-5d4*2'.
    Returns (result, breakdown_str).
    """
    expr = expression.strip()

    # Validate characters (only digits, d/D, operators, parens, spaces, dots)
    if not re.match(r'^[\d\s\+\-\*\/\(\)\.dD]+$', expr):
        raise ValueError("Expressão inválida. Usa apenas dados (XdX), números e operadores (+, -, *, /).")

    rolls_breakdown = []

    def replace_dice(match):
        num = int(match.group(1))
        sides = int(match.group(2))
        results = roll_dice(num, sides)
        total = sum(results)
        if num == 1:
            rolls_breakdown.append(f"**{num}d{sides}** → `{results[0]}`")
        else:
            rolls_breakdown.append(f"**{num}d{sides}** → `{results}` = `{total}`")
        return str(total)

    # Replace all dice with their rolled totals
    math_expr = DICE_PATTERN.sub(replace_dice, expr)

    # Safety: only allow safe math characters after substitution
    if not re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', math_expr):
        raise ValueError("Expressão contém caracteres inválidos após substituição dos dados.")

    # Evaluate the math expression safely
    try:
        result = eval(math_expr, {"__builtins__": {}}, {})
        result = round(result, 4)
    except ZeroDivisionError:
        raise ValueError("Divisão por zero na expressão.")
    except Exception:
        raise ValueError("Não foi possível calcular a expressão.")

    return result, rolls_breakdown, math_expr


def is_dice_expression(text: str) -> bool:
    """Check if the message looks like a dice expression."""
    text = text.strip()
    # Must contain at least one XdX pattern
    if not DICE_PATTERN.search(text):
        return False
    # Must only contain valid dice expression characters
    if not re.match(r'^[\d\s\+\-\*\/\(\)\.dD]+$', text):
        return False
    return True


# ── Events ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"🎲 Bot conectado como {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="D&D 🎲 | Digite XdX para rolar!"
        )
    )


@bot.event
async def on_message(message: discord.Message):
    # Ignore messages from bots (including self)
    if message.author.bot:
        return

    content = message.content.strip()

    if is_dice_expression(content):
        await handle_roll(message, content)
        return

    # Process prefix commands normally
    await bot.process_commands(message)


async def handle_roll(message: discord.Message, expression: str):
    """Handle a dice roll expression and reply with an embed."""
    try:
        result, breakdown, math_expr = parse_and_roll(expression)
    except ValueError as e:
        embed = discord.Embed(
            title="❌ Erro na Rolagem",
            description=str(e),
            color=0xE74C3C
        )
        await message.reply(embed=embed, mention_author=False)
        return

    # Determine embed color based on result (if single d20, check crit/fail)
    color = 0x9B59B6  # default purple

    single_d20 = re.fullmatch(r'\s*1d20\s*', expression, re.IGNORECASE)
    crit_label = ""
    if single_d20:
        if result == 20:
            color = 0x2ECC71  # green
            crit_label = "⚡ **CRÍTICO!**\n"
        elif result == 1:
            color = 0xE74C3C  # red
            crit_label = "💀 **FALHA CRÍTICA!**\n"

    # Build embed
    embed = discord.Embed(
        title=f"🎲 {expression}",
        color=color
    )

    breakdown_text = "\n".join(breakdown) if breakdown else ""
    if breakdown_text:
        embed.add_field(name="Dados Rolados", value=breakdown_text, inline=False)

    # Show math if there's more than one dice or operators
    if "+" in expression or "-" in expression or "*" in expression or "/" in expression:
        embed.add_field(name="Cálculo", value=f"`{math_expr}` = **{result}**", inline=False)

    embed.add_field(
        name="Resultado Final",
        value=f"{crit_label}# **{result}**",
        inline=False
    )
    embed.set_footer(text=f"Rolado por {message.author.display_name}")

    await message.reply(embed=embed, mention_author=False)


# ── Commands ──────────────────────────────────────────────────────────────────
@bot.command(name="ajuda", aliases=["help", "h"])
async def ajuda(ctx):
    embed = discord.Embed(
        title="🎲 Bot de RPG — Ajuda",
        description="Digite qualquer expressão de dados diretamente no chat!",
        color=0x9B59B6
    )
    embed.add_field(
        name="📖 Como usar",
        value=(
            "Basta digitar uma expressão de dados e o bot rola automaticamente.\n"
            "Não precisas de prefixo ou comando!"
        ),
        inline=False
    )
    embed.add_field(
        name="🎯 Exemplos",
        value=(
            "`1d20` — rola 1 dado de 20 faces\n"
            "`3d6` — rola 3 dados de 6 faces\n"
            "`1d20+5` — rola 1d20 e adiciona 5\n"
            "`1d20+1d4` — rola 1d20 + 1d4\n"
            "`1d4+1d20/2-5d4*2` — expressão complexa\n"
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Limites",
        value=f"Máximo de **{MAX_DICE} dados** por expressão.\nMáximo de **{MAX_SIDES:,} faces** por dado.",
        inline=False
    )
    embed.add_field(
        name="✨ Especial",
        value="Ao rolar `1d20`, o bot detecta **crítico (20)** e **falha crítica (1)**!",
        inline=False
    )
    embed.set_footer(text="!ajuda | !help | !h")
    await ctx.send(embed=embed)


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
                                                                                    
