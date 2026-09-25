# Study Bot Deployment Guide

This is the setup and deploy path for Study Bot: a Discord gateway bot (`python main.py`) that stays connected, runs study timers, and streams YouTube audio into voice with FFmpeg and Node.js.

One process per bot token. A second process using the same `DISCORD_TOKEN` disconnects the first. The invite link in the README is the already-hosted bot. Follow this guide when you want your own instance.

## Quick Comparison

| | Local | Production (Oracle Cloud Always Free) |
| --- | --- | --- |
| Where it runs | Your machine | Ubuntu 24.04 VM, Ampere A1 |
| Stays online | Until you stop it or the machine sleeps | Across reboot, via systemd |
| Token | `.env` on your machine | `.env` on the VM, mode `600` |
| Cost | $0 | $0 inside Always Free limits |
| Voice + YouTube | Works while the process is up | Works while the VM is running |

The bot holds a Discord gateway socket and sends voice over outbound UDP. It needs a machine that stays running, plus FFmpeg and Node.js (yt-dlp uses Node to extract audio; nothing is saved to disk). Oracle Cloud Always Free Ampere is the $0 host that fits: enough RAM for extraction, and 10 TB/month of outbound data included.

App platforms that stop the process when idle drop the gateway and the voice connection. Use the VM below for anything you want left on.

Limits below are from [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) (Ampere allowance is 2 OCPUs and 12 GB as of June 2026).

## Option 1: Production (recommended)

### 1. Create the Discord application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Under **Bot**, reset the token and copy it. This value goes in `.env` only.
3. Enable these **Privileged Gateway Intents**:
   - Message Content Intent (required for `!` prefix commands)
   - Server Members Intent
4. Under **OAuth2 → URL Generator**, select the `bot` scope and these permissions:
   - View Channels
   - Send Messages
   - Embed Links
   - Read Message History
   - Manage Channels (lets the bot create `#study`)
   - Connect
   - Speak
5. Open the generated URL, pick a server you manage, and authorize. You can do this after the process is running; the bot shows as offline until `python main.py` is up.

### 2. Create the Always Free VM

Sign up at [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/). Always Free compute has to live in the tenancy **home region**.

Create a compute instance with:

| Setting | Value |
| --- | --- |
| Image | Ubuntu 24.04, Always Free eligible (aarch64) |
| Shape | `VM.Standard.A1.Flex` |
| OCPU | **1** |
| Memory | **6 GB** |
| Boot volume | 50 GB (default) |
| Public IPv4 | Assign a public IP |
| SSH key | Your public key |

1 OCPU and 6 GB sit inside the free cap (2 OCPUs and 12 GB total, 200 GB block storage, 10 TB outbound data per month). The 1 GB AMD micro shape is also Always Free, and it is tight once FFmpeg and Node are extracting a track. Use Ampere.

If create fails with **out of host capacity**, try another availability domain in the same home region, then try again later. Capacity moves.

Stay on an Always Free account when you can. Upgrading to Pay As You Go still leaves Always Free resources at $0 and bills only usage above those limits. If the account can be charged, set a budget alert at **$1** before you create anything else.

Networking:

- Ingress: TCP **22** from your IP. The bot does not listen on a public port.
- Egress: leave the default rule (all protocols). Voice and YouTube are outbound.

Oracle may reclaim an Always Free VM that, for 7 days, stays under 20% CPU (95th percentile), 20% network, and 20% memory. If that happens, start the instance from the console. With the systemd unit enabled, the bot comes back on boot.

### 3. Install system packages

SSH in as the Ubuntu user (`ubuntu` on the default image):

```bash
ssh ubuntu@YOUR_PUBLIC_IP
```

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg nodejs git
python3 --version
ffmpeg -version
node --version
```

`ffmpeg` on `PATH` is the binary the bot uses. On Ampere, skip a copied `bin/ffmpeg` from an x86 machine; that binary will not run.

### 4. Install the bot

```bash
git clone https://github.com/Dpoin23/Study-Bot.git
cd Study-Bot

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

A private GitHub repo needs a read-only deploy key or `gh auth login` before `git clone`.

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env`:

```
DISCORD_TOKEN=your_bot_token_here
```

Leave `NODE_PATH` and `FFMPEG_PATH` unset when `node` and `ffmpeg` are on `PATH`, which they are after the apt install above.

### 5. Run it under systemd

From `~/Study-Bot`:

```bash
sudo tee /etc/systemd/system/study-bot.service >/dev/null <<'EOF'
[Unit]
Description=Study Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Study-Bot
ExecStart=/home/ubuntu/Study-Bot/.venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now study-bot
```

The process loads `DISCORD_TOKEN` from `/home/ubuntu/Study-Bot/.env` itself. Keep the token out of the unit file.

Check that it logged in:

```bash
systemctl status study-bot
journalctl -u study-bot -n 50 --no-pager
```

You want a line that the bot logged in. A missing or placeholder token exits immediately; fix `.env` and restart:

```bash
sudo systemctl restart study-bot
```

`discord.log` in the repo root is also written on each start (it is gitignored).

### 6. Prove voice and study

In Discord, join a voice channel on the server you invited, then:

```
!help
!study 1
!play lofi study beats
```

`!study 1` should post a countdown in `#study`. `!play` should put audio in your voice channel. Then `!studyend` and `!leave`.

### 7. Update

```bash
cd ~/Study-Bot
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart study-bot
```

YouTube changes extraction often. When `!play` or `!search` starts failing and the rest of the bot is fine:

```bash
cd ~/Study-Bot
source .venv/bin/activate
pip install -U yt-dlp
sudo systemctl restart study-bot
```

## Option 2: Local development

Use this to try the bot on your own machine. It stops when you stop the process or the machine sleeps.

### 1. Prerequisites

| Tool | Why |
| --- | --- |
| Python 3.10+ | Runs the bot |
| FFmpeg | Streams audio into Discord voice |
| Node.js | yt-dlp extracts YouTube audio |

```bash
python3 --version
ffmpeg -version
node --version
```

On WSL, if a bundled FFmpeg crashes, put a Linux binary at `bin/ffmpeg` or set `FFMPEG_PATH`.

### 2. Token

Use a Discord application you control (same portal steps as Option 1). One token, one running process.

### 3. Install and run

From a clone of this repo:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DISCORD_TOKEN` in `.env`. If Node is not on `PATH` (common on Windows):

```
NODE_PATH=C:\Program Files\nodejs\node.exe
```

```bash
python main.py
```

`python -m bot` is the same entry. Join a voice channel, then `!help`, `!study`, or `!play lofi study beats`.

Command list and behavior: [README](../README.md).

## Cost Model

| Item | Monthly cost | Notes |
| --- | --- | --- |
| Ampere VM, 1 OCPU / 6 GB | $0 | Inside 2 OCPU / 12 GB Always Free |
| 50 GB boot volume | $0 | Inside 200 GB Always Free block storage |
| Outbound data | $0 | 10 TB/month included; voice for this bot stays far under that |
| Public IPv4 on that instance | $0 | Included with the Always Free instance |
| Discord, YouTube audio | $0 | Streamed, not downloaded |
| Extra Oracle services (databases, load balancers) | — | Leave them uncreated |

## Rollout Checklist

1. Create a Discord application, enable Message Content and Server Members intents, copy the bot token.
2. Create an Always Free Ubuntu 24.04 Ampere instance: 1 OCPU, 6 GB, public IP, your SSH key, in the home region.
3. Confirm the security list allows SSH from your IP and default egress.
4. If the account can be billed, set a $1 budget alert.
5. Install `python3`, `ffmpeg`, `nodejs`, and `git`.
6. Clone the repo, create `.venv`, `pip install -r requirements.txt`.
7. `cp .env.example .env`, set `DISCORD_TOKEN`, `chmod 600 .env`.
8. Install and enable `study-bot.service`.
9. Confirm `journalctl` shows a login.
10. Invite the bot, join voice, run `!help`, `!study 1`, and `!play lofi study beats`.
