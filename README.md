# AI Lua Generator Bot 

A powerful Discord bot built in Python (`discord.py`) that uses Google's incredible **Gemini AI** to instantly write, fix, or generate functional Lua scripts natively in Discord channels using the `/generatescript` slash command.

## How to Host on Railway (24/7 Hosting)

This project is already pre-configured to be dragged and dropped into GitHub and automatically built on Railway without you writing another line of code!

### Step 1: Upload to GitHub
1. Create a new empty repository on your GitHub account.
2. Upload every file in this folder (`bot.py`, `requirements.txt`, `Procfile`, `runtime.txt`, and `.gitignore`) directly into the repository.
   
### Step 2: Deploy to Railway
1. Go to [Railway.app](https://railway.app/) and log in with your GitHub.
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your new Discord Bot repository.
4. Railway will automatically detect the `requirements.txt` and `Procfile` and begin building a cloud worker for your bot!

### Step 3: Add the API Keys
Your bot needs its brain and its Discord body to function safely in the cloud. While on your Railway Project Dashboard, head to the **Variables** tab and add these exactly as written:

- `DISCORD_TOKEN` -> Get this from the Discord Developer Portal inside your Bot tab!
- `GEMINI_API_KEY` -> Get this for free from Google AI Studio!

Once the variables are saved, Railway will restart the bot and it will go online in your server.

## Usage
In any channel the bot is in, simply type:
`/generatescript [your prompt]`
*(Example: `/generatescript Write an ESP highlight script for all models in Workspace`)*

The bot will defer the response, ping the AI to generate the code, and instantly output the script blocks right into the chat. If the script is super long, it will automatically package it into a downloadable `.lua` file for you instead!
