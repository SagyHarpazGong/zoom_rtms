# Getting Started Guide: Setting Up Your Zoom RTMS App

This guide will walk you through **every single step** needed to create a Zoom app, get your credentials, and start using the Zoom RTMS Real-Time Transcription System.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Create a Zoom Account](#step-1-create-a-zoom-account)
3. [Step 2: Access Zoom Marketplace](#step-2-access-zoom-marketplace)
4. [Step 3: Create Your App](#step-3-create-your-app)
5. [Step 4: Configure Basic Information](#step-4-configure-basic-information)
6. [Step 5: Enable RTMS Feature](#step-5-enable-rtms-feature)
7. [Step 6: Get Your Credentials](#step-6-get-your-credentials)
8. [Step 7: Configure Event Subscriptions (Webhooks)](#step-7-configure-event-subscriptions-webhooks)
9. [Step 8: Activate Your App](#step-8-activate-your-app)
10. [Step 9: Configure Your Project](#step-9-configure-your-project)
11. [Step 10: Test Your Setup](#step-10-test-your-setup)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, make sure you have:

- ✅ A computer with internet access
- ✅ A valid email address
- ✅ Basic understanding of terminal/command line
- ✅ Python 3.8 or higher installed
- ✅ This project downloaded or cloned

---

## Step 1: Create a Zoom Account

If you already have a Zoom account, skip to [Step 2](#step-2-access-zoom-marketplace).

### 1.1 Sign Up for Zoom

1. **Open your web browser** and go to: https://zoom.us
2. **Click on "Sign Up, It's Free"** in the top right corner
3. **Enter your email address** and click "Sign Up"
4. **Check your email** for a confirmation message from Zoom
5. **Click the confirmation link** in the email
6. **Complete your profile**:
   - Enter your first name
   - Enter your last name
   - Create a password (make it strong!)
   - Click "Continue"

### 1.2 Verify Your Account

1. You may need to **verify your phone number**
2. Follow the on-screen instructions to complete verification
3. **You now have a Zoom account!** ✅

---

## Step 2: Access Zoom Marketplace

### 2.1 Navigate to Zoom App Marketplace

1. **Go to**: https://marketplace.zoom.us
2. **Sign in** with your Zoom account credentials if prompted
   - Email: (your Zoom email)
   - Password: (your Zoom password)
   - Click "Sign In"

### 2.2 Access Developer Portal

1. **Look at the top navigation bar**
2. **Click on "Develop"** (in the top right area)
3. **From the dropdown menu, click "Build App"**
   - This will take you to the developer portal

---

## Step 3: Create Your App

### 3.1 Choose App Type

You'll see several app types. Here's what to do:

1. **Look for "General App"** card
   - Description: "Build apps that leverage Zoom's APIs, Webhooks, and SDKs"
2. **Click the "Create" button** under "General App"

> **Why General App?** This type gives you access to RTMS (Real-Time Media Streams) which is what we need for real-time transcription.

### 3.2 Name Your App

1. **A modal/popup will appear** asking for app details
2. **Enter your app name** in the "App Name" field
   - Example: "My RTMS Transcription"
   - Example: "Meeting Transcriber"
   - Use any name you like - you can change it later
3. **Choose account type**: Select "User-managed app"
   - This means the app will be tied to your account
4. **Click "Create"** button

🎉 **Congratulations!** Your app has been created!

---

## Step 4: Configure Basic Information

After creating your app, you'll be taken to the app configuration page.

### 4.1 Fill Out App Information

1. **You'll see a form with several fields**. Fill them out:

   **Short Description** (Required):
   ```
   Real-time transcription system for Zoom meetings using VAD and ASR
   ```

   **Long Description** (Optional but recommended):
   ```
   This application provides real-time transcription of Zoom meetings using
   Voice Activity Detection (VAD) and Automatic Speech Recognition (ASR).
   It processes audio streams in real-time and generates accurate transcripts
   with speaker identification.
   ```

   **Company Name**:
   - Enter your company name or your name

   **Developer Name**:
   - Enter your name

   **Developer Email**:
   - Enter your email (this should already be filled)

2. **Scroll down and click "Continue"** (or "Save" if available)

### 4.2 Upload App Icon (Optional)

1. **Look for "App Logo" section**
2. You can skip this for now or upload a logo
3. **Click "Continue"** to proceed

---

## Step 5: Enable RTMS Feature

This is the **most important step** for real-time transcription!

### 5.1 Navigate to Features Section

1. **Look at the left sidebar menu**
2. **Click on "Features"**
3. You'll see a list of features you can enable

### 5.2 Enable Real-Time Media Streams

1. **Scroll down** until you find **"Real-time Media Streams (RTMS)"**
2. **Toggle the switch to ON** (it should turn blue/green)
3. **A dialog may appear** with terms and conditions
   - **Read the terms** (or at least scroll through them)
   - **Check the box** to accept
   - **Click "Enable"** or "Accept"

### 5.3 Configure RTMS Settings

After enabling RTMS, you'll see additional options:

1. **Media Streams**:
   - ☑️ Check "Audio"
   - ☑️ Check "Video" (optional, only if you need video)
   - ☑️ Check "Share" (optional, for screen sharing)

2. **Data Options** (what kind of streams to receive):
   - ☑️ Check "Raw Audio" - **REQUIRED for transcription**
   - You can also check "Encoded Audio" if needed

3. **Click "Save"** at the bottom

---

## Step 6: Get Your Credentials

Now we'll get the `client_id` and `client_secret` you need for the project!

### 6.1 Navigate to App Credentials

1. **Look at the left sidebar menu**
2. **Click on "App Credentials"** (usually near the top)

### 6.2 Copy Your Client ID

1. You'll see a section labeled **"Client ID"**
2. **Copy the Client ID**:
   - **Method 1**: Click the "Copy" button next to it
   - **Method 2**: Select the text and press Ctrl+C (Windows) or Cmd+C (Mac)
3. **Paste it somewhere safe** - you'll need this in a moment!

   It looks something like this:
   ```
   AbCdEfGh123456789012345678
   ```

### 6.3 Copy Your Client Secret

1. **Look for "Client Secret"** section (right below Client ID)
2. **Click "View"** button to reveal the secret
3. **Copy the Client Secret**:
   - Click the "Copy" button or select and copy the text
4. **Paste it somewhere safe** next to your Client ID

   It looks something like this:
   ```
   aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890abcdef
   ```

### 6.4 Keep These Safe! 🔐

> ⚠️ **IMPORTANT**: Your Client Secret is like a password. Never share it publicly, commit it to GitHub, or post it online!

**Save both values** in a secure location. You'll use them in [Step 9](#step-9-configure-your-project).

---

## Step 7: Configure Event Subscriptions (Webhooks)

Webhooks allow Zoom to notify your app when meetings start and end.

### 7.1 Navigate to Event Subscriptions

1. **Look at the left sidebar menu**
2. **Click on "Feature"** (if not already there)
3. **Scroll down to find "Event Subscriptions"**
4. **Toggle the "Event Subscriptions" switch to ON**

### 7.2 Add Webhook Endpoint

Before we can add the webhook URL, we need to expose our local server to the internet. We'll do this with **ngrok**.

#### 7.2.1 Install ngrok (if not already installed)

**On Mac:**
```bash
brew install ngrok
```

**On Linux:**
```bash
# Download and install
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

**On Windows:**
- Download from https://ngrok.com/download
- Extract and run ngrok.exe

#### 7.2.2 Start ngrok

Open a **new terminal window** and run:
```bash
ngrok http 8080
```

You'll see output like this:
```
Session Status                online
Forwarding                    https://abc123.ngrok.io -> http://localhost:8080
```

**Copy the HTTPS URL** (the one that looks like `https://abc123.ngrok.io`)

> 📝 **Note**: Keep this terminal window open! If you close it, the tunnel will stop working.

#### 7.2.3 Add Your Webhook URL to Zoom

Back in the Zoom App Marketplace configuration:

1. **Find "Event notification endpoint URL"** field
2. **Enter your webhook URL**:
   ```
   https://abc123.ngrok.io/webhook
   ```
   (Replace `abc123` with your actual ngrok subdomain)

3. **Click "Validate"** button
   - Zoom will try to send a test request to your URL
   - **If validation fails**, that's okay for now - we'll test it later when the app is running

4. **Add Event Types**:
   - Click "Add Event Type" button
   - **Select "Meeting" from the dropdown**
   - Check these two events:
     - ☑️ **"Start RTMS"** (meeting.rtms_started)
     - ☑️ **"Stop RTMS"** (meeting.rtms_ended)
   - Click "Done" or "Add"

5. **Click "Save"** at the bottom of the page

### 7.3 Webhook Configuration Summary

Your webhook should now be configured with:
- ✅ Event Subscriptions: **Enabled**
- ✅ Endpoint URL: **Your ngrok URL + /webhook**
- ✅ Events subscribed: **meeting.rtms_started**, **meeting.rtms_ended**

---

## Step 8: Activate Your App

Before you can use your app, you need to activate it.

### 8.1 Review App Information

1. **Look at the left sidebar menu**
2. **Click on "Activation"** or **"Submit"** (near the bottom)

### 8.2 Activate/Publish

1. **If it's for personal/internal use**:
   - Click "Activate" or "Publish" for local use
   - You don't need Zoom to review it

2. **If you see "Publish to Marketplace"**:
   - You can skip this if it's just for your personal use
   - For personal use, the app is already active after creation

3. **Your app is now ready to use!** ✅

---

## Step 9: Configure Your Project

Now let's use those credentials in your transcription project!

### 9.1 Navigate to Project Directory

Open your terminal and go to the project directory:
```bash
cd /path/to/zoom_rtms
```

### 9.2 Copy Environment File

Create a copy of the example environment file:
```bash
cp .env.example .env
```

### 9.3 Edit Configuration

Open `config.yaml` in your text editor:
```bash
# Use your preferred editor
nano config.yaml
# or
vim config.yaml
# or
code config.yaml  # VS Code
```

### 9.4 Add Your Credentials

Find the `zoom:` section and replace with your credentials:

```yaml
zoom:
  client_id: "AbCdEfGh123456789012345678"        # ← Paste your Client ID here
  client_secret: "aBcDeFgHiJkLmNoPqRsTuVwXyZ..."  # ← Paste your Client Secret here
```

**Example:**
```yaml
zoom:
  client_id: "QxK8fMnpL2vHb9Yr3TzW1"
  client_secret: "s3cr3t_k3y_h3r3_d0nt_sh4r3_th1s"

webhook:
  port: 8080
  path: "/webhook"

vad:
  ws_url: "ws://localhost:8001/vad"
  packet_duration_ms: 100

asr:
  ws_url: "ws://localhost:8002/asr"
  segment_duration_seconds: 2.5
  enable_diarization: true
```

### 9.5 Save the File

- **nano**: Press `Ctrl+O`, then `Enter`, then `Ctrl+X`
- **vim**: Press `Esc`, type `:wq`, press `Enter`
- **VS Code**: Press `Ctrl+S` (Windows/Linux) or `Cmd+S` (Mac)

---

## Step 10: Test Your Setup

Let's make sure everything works!

### 10.1 Install Dependencies

First, install all required Python packages:
```bash
pip install -r requirements.txt
```

This will install:
- ✅ Zoom RTMS SDK
- ✅ Audio processing libraries
- ✅ WebSocket clients
- ✅ Other dependencies

**Wait for installation to complete** (may take 1-2 minutes)

### 10.2 Verify Installation

Check that the RTMS SDK is installed:
```bash
python -c "import rtms; print('RTMS SDK installed successfully!')"
```

You should see:
```
RTMS SDK installed successfully!
```

### 10.3 Start Your VAD Server

In a **new terminal window**, start your VAD server:
```bash
# Example - replace with your actual VAD server command
python vad_server.py
```

### 10.4 Start Your ASR Server

In **another new terminal window**, start your ASR server:
```bash
# Example - replace with your actual ASR server command
python asr_server.py
```

### 10.5 Start ngrok (if not running)

Make sure ngrok is still running from [Step 7.2.2](#722-start-ngrok):
```bash
ngrok http 8080
```

### 10.6 Start the Transcription System

In your **main terminal window**, start the application in webhook mode:
```bash
python main.py --mode webhook
```

You should see output like:
```
🚀 Starting webhook server on http://localhost:8080/webhook
⏳ Waiting for webhook events...
```

### 10.7 Join a Zoom Meeting

Now it's time to test with a real meeting!

1. **Start a Zoom meeting** (or join one)
2. **Make sure RTMS is enabled** for the meeting
   - The meeting must be hosted by your account (the one with the app)
3. **Speak into the microphone**
4. **Watch your terminal** for transcription output!

You should see:
```
📩 Webhook received: meeting.rtms_started
✅ Meeting started: stream_id_12345
🎉 Joined meeting! Result: success
🎵 Audio: 640 bytes at timestamp
💬 Speaker 1: Hello everyone
💬 Speaker 2: Hi there!
```

### 10.8 Verify Output

Check that:
- ✅ Webhook was received
- ✅ RTMS client joined the meeting
- ✅ Audio data is being received
- ✅ VAD is detecting speech
- ✅ ASR is producing transcriptions
- ✅ Transcriptions appear in real-time

---

## Troubleshooting

### Issue: "Failed to join RTMS meeting"

**Possible causes:**
1. ❌ Client ID or Secret is wrong
2. ❌ RTMS feature not enabled
3. ❌ Meeting doesn't have RTMS enabled

**Solutions:**
1. ✅ Double-check credentials in `config.yaml`
2. ✅ Go back to [Step 5](#step-5-enable-rtms-feature)
3. ✅ Make sure you're the meeting host
4. ✅ Try creating a new meeting

### Issue: "Webhook validation failed"

**Possible causes:**
1. ❌ ngrok is not running
2. ❌ Wrong webhook URL
3. ❌ Firewall blocking port 8080
4. ❌ Application not running

**Solutions:**
1. ✅ Make sure ngrok is running: `ngrok http 8080`
2. ✅ Copy the HTTPS ngrok URL exactly
3. ✅ Add `/webhook` to the end of the URL
4. ✅ Start the application first, then validate
5. ✅ Check firewall settings

### Issue: "No module named 'rtms'"

**Solution:**
```bash
pip install rtms
# or
pip install -r requirements.txt
```

### Issue: "Connection refused" to VAD or ASR server

**Possible causes:**
1. ❌ VAD/ASR server not running
2. ❌ Wrong URL in config

**Solutions:**
1. ✅ Start your VAD server on port 8001
2. ✅ Start your ASR server on port 8002
3. ✅ Check `config.yaml` URLs are correct:
   ```yaml
   vad:
     ws_url: "ws://localhost:8001/vad"
   asr:
     ws_url: "ws://localhost:8002/asr"
   ```

### Issue: "No audio received"

**Possible causes:**
1. ❌ Microphone muted in Zoom
2. ❌ No one is speaking
3. ❌ Audio params misconfigured

**Solutions:**
1. ✅ Unmute your microphone in Zoom
2. ✅ Speak clearly into the microphone
3. ✅ Check Zoom meeting settings
4. ✅ Review logs for `rtms_audio_received` messages

### Issue: ngrok "Session Expired"

**Cause:**
- Free ngrok sessions expire after 2 hours

**Solution:**
1. ✅ Restart ngrok: `ngrok http 8080`
2. ✅ Update webhook URL in Zoom with new ngrok URL
3. ✅ For permanent solution, use a paid ngrok account or deploy to a server

### Issue: "Permission denied" errors

**Solution:**
```bash
# Make sure you have write permissions
chmod +x main.py

# Or run with sudo (not recommended)
sudo python main.py --mode webhook
```

### Need More Help?

1. **Check the logs**: Look in `logs/zoom_rtms.log`
2. **Enable debug logging**: Set log level to DEBUG in `config.yaml`
3. **Review documentation**:
   - [README.md](README.md)
   - [UPDATED_SDK_GUIDE.md](UPDATED_SDK_GUIDE.md)
   - [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Check Zoom's documentation**: https://developers.zoom.us/docs/rtms/

---

## 🎉 Success!

If you've made it this far and everything is working, congratulations! You now have:

✅ A Zoom app with RTMS enabled
✅ Client ID and Client Secret configured
✅ Webhooks set up and working
✅ Real-time transcription running
✅ VAD and ASR processing pipeline working

### Next Steps

- **Customize the system** for your use case
- **Improve VAD/ASR models** for better accuracy
- **Add more features** like speaker identification
- **Deploy to production** with proper hosting
- **Add monitoring** and error alerts

---

## Quick Reference Card

Keep this handy:

| Item | Value |
|------|-------|
| **Zoom Marketplace** | https://marketplace.zoom.us |
| **Developer Portal** | Develop → Build App |
| **App Type** | General App |
| **Required Feature** | Real-time Media Streams (RTMS) |
| **Webhook Events** | meeting.rtms_started, meeting.rtms_ended |
| **Config File** | config.yaml |
| **Start Command** | `python main.py --mode webhook` |
| **ngrok Command** | `ngrok http 8080` |
| **Test Meeting** | Start Zoom meeting and speak |

---

## Appendix: Configuration File Reference

Complete `config.yaml` template:

```yaml
# Zoom RTMS Credentials
zoom:
  client_id: "YOUR_CLIENT_ID_HERE"
  client_secret: "YOUR_CLIENT_SECRET_HERE"

# Webhook Configuration
webhook:
  port: 8080
  path: "/webhook"

# Voice Activity Detection
vad:
  ws_url: "ws://localhost:8001/vad"
  packet_duration_ms: 100
  reconnect_attempts: 5
  reconnect_delay_seconds: 2

# Automatic Speech Recognition
asr:
  ws_url: "ws://localhost:8002/asr"
  segment_duration_seconds: 2.5
  enable_diarization: true
  reconnect_attempts: 5
  reconnect_delay_seconds: 2

# Audio Settings
audio:
  sample_rate: 16000
  channels: 1
  bit_depth: 16

# Buffer Management
buffering:
  min_speech_duration_ms: 500
  silence_timeout_seconds: 1.0
  speech_buffer_size_seconds: 5.0

# Transcription Output
transcription:
  output_format: "text"  # Options: json, text, srt
  enable_timestamps: true
  enable_speaker_labels: true
  real_time_output: true

# Recording
recording:
  enabled: true
  output_dir: "./recordings"
  audio_format: "wav"

# Logging
logging:
  level: "INFO"  # Options: DEBUG, INFO, WARNING, ERROR
  file: "./logs/zoom_rtms.log"
  console: true
```

---

**Good luck with your real-time transcription project!** 🚀
