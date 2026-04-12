import discord
from discord import app_commands
import google.generativeai as genai
import os
import io

# Load Environment Variables (Set these on Railway or your local .env file)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class LuaGeneratorBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Syncs the slash commands to Discord globally when the bot starts
        await self.tree.sync()
        print("Slash commands synced successfully!")

client = LuaGeneratorBot()

@client.event
async def on_ready():
    print(f'Logged in fully as {client.user} (ID: {client.user.id})')
    print('Bot is ready to receive commands!')
    print('------')

@client.tree.command(name="generatescript", description="Generates a flawless Lua script using AI based on your prompt")
@app_commands.describe(prompt="What do you want the Lua script to do?")
async def generatescript(interaction: discord.Interaction, prompt: str):
    if not GEMINI_API_KEY:
        await interaction.response.send_message("❌ The Bot's AI API Key is not configured on the host server.", ephemeral=True)
        return
        
    # Defer the interaction immediately because AI generation can take up to 10 seconds.
    # Discord will time out the command if we don't 'think' first.
    await interaction.response.defer(thinking=True)
    
    try:
        # Utilizing the Google Gemini generative model
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        system_instructions = (
            "You are an elite Lua and Roblox script developer. "
            "Write a highly functional, error-free Lua script based on the user's prompt. "
            "Do not include any English conversational text or explanations. "
            "Only output the pure Lua code wrapped cleanly in ```lua ``` codeblocks. "
            "Ensure the script is optimized, well-structured, and secure."
        )
        
        full_prompt = f"{system_instructions}\n\nUser request: {prompt}"
        response = model.generate_content(full_prompt)
        
        script_content = response.text.strip()
        
        # Fallback to pure text if AI forgets markdown formatting
        if not script_content.startswith("```lua"):
            script_content = f"```lua\n{script_content}\n```"
        
        # Check Discord's 2000 character limit per message
        if len(script_content) > 1900:
            # Strip the markdown blocks for raw file dumping
            raw_script = script_content.replace("```lua\n", "").replace("\n```", "").replace("```", "")
            
            file_stream = io.BytesIO(raw_script.encode('utf-8'))
            script_file = discord.File(file_stream, filename="generated_script.lua")
            
            await interaction.followup.send(content="✨ The script was too large for a message, so I attached it as a file for you!", file=script_file)
        else:
            await interaction.followup.send(content=f"✨ **Here is your generated script!**\n{script_content}")
            
    except Exception as e:
        await interaction.followup.send(content=f"❌ An error occurred while generating the script:\n```\n{str(e)}\n```")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("CRITICAL: Please set the DISCORD_TOKEN environment variable in Railway.")
    elif not GEMINI_API_KEY:
         print("CRITICAL: Please set the GEMINI_API_KEY environment variable in Railway.")
    if DISCORD_TOKEN and GEMINI_API_KEY:
        client.run(DISCORD_TOKEN)
