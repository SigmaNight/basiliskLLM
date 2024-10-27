# 🐍 BasiliskLLM: Where LLMs Unite

[![Crowdin](https://badges.crowdin.net/basiliskllm/localized.svg)](https://crowdin.com/project/basiliskllm)
[![Continuous Integration](https://github.com/SigmaNight/basiliskLLM/actions/workflows/ci.yml/badge.svg)](https://github.com/SigmaNight/basiliskLLM/actions/workflows/ci.yml)

In Development - It's still in its infancy. Use with caution!

## So, What's the Idea Here?

**BasiliskLLM** is like the cool uncle of LLM interaction tools. Drawing "inspiration" (a.k.a. brilliant ideas stolen in the dead of night) from [OpenAI's NVDA add-on](https://github.com/aaclause/nvda-OpenAI/), it aims to do what every project dreams of: actually be useful. Our noble mission? To make chatting with large language models (LLMs) so easy, even your grandma could do it blindfolded. Whether you're into Anthropic, Gemini, Mistral, OpenAI, OpenRouter, or running your own secretive AI in the basement, we've got you covered. Yes, even you, screen reader users. We see you.

### And the Name? Seriously?

Why does anyone name anything? Partially as a joke, partially hoping it becomes a self-fulfilling prophecy. Why this particular name? It's a nod to the infamous **Roko's basilisk**, which if you're curious (or bored), you can dive into [here](https://en.wikipedia.org/wiki/Roko%27s_basilisk) and [here](https://www.lesswrong.com/tag/rokos-basilisk). Spoiler alert: it's the ultimate rabbit hole.

## Key features

- **Multi-Chat Support**: Chat with multiple LLMs at the same time.
- **Describe Image**: Analyze images directly in the chat, whether they are from a screenshot, file, or URL.
- **Speech to Text**: Turn speech into text using your microphone or an audio file.
- **Multi-Conversation Support**: Manage several conversations at once, each in its own tab.
- **Auto-Update**: The app checks and installs updates automatically, so you're always on the latest version.
- **NVDA Add-on Integration**: Send the current navigator object's image directly to the active chat from any application, enhancing accessibility for those using NVDA.
- **Credential Security**: Protect your credentials by using the Windows Credential Manager.

## Download and installation

### Download Options

- Visit the [latest release page](https://github.com/SigmaNight/basiliskLLM/releases/latest) for the most up-to-date stable version.
- For pre-releases or historical versions, head over to [all releases](https://github.com/SigmaNight/basiliskLLM/releases).

### Available Assets for Each Release

- **Setup for Windows x64**: Traditional installer for 64-bit Windows systems. Suitable if you prefer a standard installation.
- **Setup for Windows x86**: Traditional installer for 32-bit Windows systems.
- **Portable Version for Windows x64**: No installation needed, just extract and run `basilisk.exe`. Ideal for users who prefer not to install software.
- **Portable Version for Windows x86**: No installation needed, just extract and run `basilisk.exe`.

### Installation Using the Setup Installer

- **Download the Installer:** Choose the appropriate installer (x64 or x86) from the releases page.
- **Run the Installer:** Follow the installation prompts to get **BasiliskLLM** set up on your machine.
- **Start the Application:** Once installed, launch **BasiliskLLM** from your desktop or start menu.

### Using the Portable Version

- **Download the Portable Version:** Select the portable version (x64 or x86) from the releases page.
- **Extract the Files:** Unzip the downloaded file to a folder of your choice.
- **Run the Application:** Launch `basilisk.exe` from the extracted folder. No installation needed.

### Manual Installation (for Developers and Brave Souls)

**Clone the Repository:**

```shell
git clone https://github.com/SigmaNight/basiliskLLM.git
cd basiliskLLM
```

**Install Dependencies:**

```shell
poetry install
```

**Run the Application:**

```shell
poetry run python -m basilisk
```

## account configuration

When you run the app for the first time, it will prompt you to configure your account. Alternatively, you can configure your account by clicking on the 'Tool' menu and selecting 'Manage Account.'

A configuration window will appear, allowing you to enter your API key and select the AI provider you wish to use. You can also configure the Credential Manager to securely store your API key.

You can obtain an API key from your chosen AI provider. The app supports the following AI providers:

- [Anthropic](https://www.anthropic.com/api)
- [Gemini](htps://makersuite.google.com/app/apikey)
- [Mistral AI](https://mistral.ai/)
- [OpenAI](https://platform.openai.com/)
- [OpenRouter](https://openrouter.ai/)

## Shortcuts

Except for global shortcuts, keyboard shortcuts are displayed alongside the labels of their corresponding elements.

### Global shortcuts

These shortcuts work anywhere in Windows.

- **`AltGr+Shift+B`**: Minimize to tray or show the BasiliskLLM window.
- **`AltGr+Shift+W`**: Take a screenshot of the current window and send the image to the active chat.
- **`AltGr+Shift+F`**: Take a screenshot of the full screen and send the image to the active chat.

**Note**: You can also minimize the window using `Alt+F4`.

### BasiliskLLM window shortcuts

These shortcuts work only when the BasiliskLLM window is focused.

- **`Ctrl+1` to `Ctrl+9`**: Select the corresponding tab. Each tab is a different chat.
- **`Ctrl+n`**: Create a new chat.
- **`Ctrl+w`**: Close the current chat.

### Contextual Shortcuts

The multiline "System prompt," "Messages," and "Prompt" fields come equipped with context menus filled with commands that can be quickly executed using keyboard shortcuts. The same applies to the models list. These shortcuts are active when the relevant field is in focus.

Examples of Contextual Shortcuts in the Messages Area:

- **`j`**: Move to the previous message.
- **`k`**: Move to the next message.

**Note**: Context menu can be opened using the `Shift+F10` key combination, the `Applications` key, or by right-clicking on the field.

## NVDA Add-on Connector

For those using NVDA, you can install the NVDA add-on connector to send the image of the current object directly to the active chat from any application.

To install the NVDA add-on connector, navigate to the Tools menu > Install NVDA add-on.
Once the add-on is installed, you can use the following shortcuts:

- **`NVDA+SHIFT+k`**: Capture the current navigator object and send it to BasiliskLLM.
- **`NVDA+SHIFT+l`**: Send the current image source to BasiliskLLM (url or base64).

## Automatic update of the Application (Windows only)

The app includes a built-in auto-update feature with three update channels:

- `stable`: the stable version of the app (default a stable release on GitHub)
- `beta`: the beta version of the app (default a pre-release on GitHub)
- `dev`: the dev version of the app (default the last commit on the master branch)

You have four update modes available:

- **notify**: the app will notify you when a new version is available.
- **download**: the app will download the new version but you have to install it manually.
- **install**: the app will download and install the new version automatically (not implemented yet).
- **off**: the app will not check for new versions.

## 🛠 Setting Up Your Dev Palace 🏰

Requirements: Python 3.12

The project requires poetry. To install it visit the [Poetry installation guide](https://python-poetry.org/docs/#installing-with-pipx).
For short reference:

```shell
pip3.12 install pipx
pipx ensurepath
pipx install poetry
```

In the root of what may soon become your favorite project, install dependencies with poetry. It will create a special virtual environment for the project.

```shell
poetry install
```

Activate the virtual environment (because magic needs a little nudge):

```shell
poetry shell
```

Ready to watch the code baby crawl, maybe even walk? Fire up the project:

```shell
python -m basilisk
```

### 🚀 Build Standalone Executable

You can build a standalone executable with the following command:

```shell
poetry run python -m cx_Freeze build_exe
```

This will create a `dist` directory with the standalone executable. You can run the executable by double-clicking on it.

### 📦 Packaging for Windows

The project utilizes Inno Setup to create an all-in-one installer, packaging the output generated by cx_Freeze. ...

To create the installer, you need to install Inno Setup. You can download it from [here](https://www.jrsoftware.org/isdl.php).

After installing Inno Setup, check that the `ISCC.exe` is in your PATH. You can do this by running the following command:

```shell
where ISCC.exe
```

If the command returns the path to the `ISCC.exe`, you are good to go.

You can create the installer by running the following command:

```shell
iscc win_installer.iss
```

This will create an installer in the `output_setup` directory.

## 🌍 Translations

We welcome and appreciate translations for this project. If you're interested in helping us translate the content into your language, you have two options:

### Recommended: Use Crowdin

The preferred method is to use the Crowdin platform. To begin, ensure you have a Crowdin account and visit the [BasiliskLLM Crowdin project](https://crowdin.com/project/basiliskllm). If your language is not currently supported, please open an issue to request its addition. You can contribute translations via the Crowdin web interface or use popular translation tools like [Poedit](https://poedit.net/).
In the file menu of the poedit you can open translation from a cloud service and select Crowdin.
You must login to your crowdin account and select the project and the language you want to translate.
After that you can start translating the strings like a normal po file.
When you save the file it will be automatically uploaded to crowdin.

### Alternative: Use the `.pot` File

Alternatively, you can work with the `.pot` (Portable Object Template) file. Download it from the releases page and use a text editor such as [Poedit](https://poedit.net/) for translation.

If you prefer, you can also generate a `.pot` file directly from the source code with the following command:

```shell
python setup.py extract_messages
```

To create a PO (Portable Object) file for your language, use the command:

```shell
python setup.py init_catalog --locale <your_language_code>
```

The language code should adhere to the ISO 639-1 standard. For instance, the code for Spanish is `es`. You can find the appropriate code for your language [here](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes).

Use a text editor like [Poedit](https://poedit.net/) to translate the strings in the `.po` file. Once you've finished translating, compile the `.po` file into an `.mo` (Machine Object) file with the command:

```shell
python setup.py compile_catalog
```

Finally, create a pull request with your translated `.po` file.

## 🧙‍♂️🧙‍♀️ Contributions: Summoning All Wizards and Witches

Got ideas, translations, or magical spells to contribute? We're all ears. Open an issue like it's your Hogwarts acceptance letter. Time to make some magic happen!
