# 🐍 BasiliskLLM: Where LLMs Unite

In Development - It's still in its infancy. Use with caution!

## So, What's the Idea Here?

**BasiliskLLM** is like the cool uncle of LLM interaction tools. Drawing "inspiration" (a.k.a. brilliant ideas stolen in the dead of night) from [OpenAI's NVDA add-on](https://github.com/aaclause/nvda-OpenAI/), it aims to do what every project dreams of: actually be useful. Our noble mission? To make chatting with large language models (LLMs) so easy, even your grandma could do it blindfolded. Whether you're into OpenAI, OpenRouter, Mistral, or running your own secretive AI in the basement, we've got you covered. Yes, even you, screen reader users. We see you.

### And the Name? Seriously?

Why does anyone name anything? Partially as a joke, partially hoping it becomes a self-fulfilling prophecy. Why this particular name? It's a nod to the infamous **Roko's basilisk**, which if you're curious (or bored), you can dive into [here](https://en.wikipedia.org/wiki/Roko%27s_basilisk) and [here](https://www.lesswrong.com/tag/rokos-basilisk). Spoiler alert: it's the ultimate rabbit hole.

## Download and installation

### Download Options

- Visit the [latest release page](https://github.com/aaclause/basiliskLLM/releases/latest) for the most up-to-date stable version.
- For pre-releases or historical versions, head over to [all releases](https://github.com/aaclause/basiliskLLM/releases).

### Available Assets for Each Release

- **Setup for Windows x64:** Traditional installer for 64-bit Windows systems.
- **Setup for Windows x86:** Traditional installer for 32-bit Windows systems.
- **Portable Version for Windows x64:** No installation required, just extract and run `basilisk.exe`.
- **Portable Version for Windows x86:** No installation required, just extract and run `basilisk.exe`.

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
git clone https://github.com/aaclause/basiliskLLM.git
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

## Shortcuts

### Global shortcuts

These shortcuts work anywhere in Windows.

- `AltGr+Shift+B`: Minimize to tray or show the BasiliskLLM window.
- `AltGr+Shift+W`: take a screenshot of the current window and send the image to the active chat.
- `AltGr+Shift+F`: take a screenshot of the full screen and send the image to the active chat.

### BasiliskLLM window shortcuts

These shortcuts work only when the BasiliskLLM window is focused.

- `Ctrl+1` to `Ctrl+9`: Select the corresponding tab. Each tab is a different chat.
- `Ctrl+n`: Create a new chat.
- `Ctrl+w`: Close the current chat.

### Automatic update of the Application (Windows only)

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

Requirements: Python 3.12 (because we settle for nothing but the best, naturally)

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

### 🌍 Translations

This project is open to translations. If you want to help us translate the project into your language, you can create a PO template file (.pot) with the following command:

```shell
python setup.py extract_messages
```

Then you can create a PO file for your language with the following command:

```shell
python setup.py init_catalog --locale <your_language_code>
```

The language code should be in the format of the ISO 639-1 standard. For example, for Spanish, the language code is `es`. You can find the language code for your language [here](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes).
Use a text editor like [Poedit](https://poedit.net/) to translate the strings in the po file. When you finish translating the strings, you can compile the PO file to a MO file with the following command:

```shell
python setup.py compile_catalog
```

## 🧙‍♂️🧙‍♀️ Contributions: Summoning All Wizards and Witches

Got ideas, translations, or magical spells to contribute? We're all ears. Open an issue like it's your Hogwarts acceptance letter. Time to make some magic happen!
