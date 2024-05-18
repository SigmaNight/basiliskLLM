# 🐍 BasiliskLLM: Where LLMs Unite

***In Development - Yep, it's still crawling. Cue the baby theme music.***. USE AT YOUR OWN RISK!

## So, What's the Idea Here?

**BasiliskLLM** is like the cool uncle of LLM interaction tools. Drawing "inspiration" (a.k.a. brilliant ideas stolen in the dead of night) from [OpenAI's NVDA add-on](https://github.com/aaclause/nvda-OpenAI/), it aims to do what every project dreams of: actually be useful. Our noble mission? To make chatting with large language models (LLMs) so easy, even your grandma could do it blindfolded. Whether you're into OpenAI, OpenRouter, Mistral, or running your own secretive AI in the basement, we've got you covered. Yes, even you, screen reader users. We see you.

### And the Name? Seriously?

Why does anyone name anything? Partially as a joke, partially hoping it becomes a self-fulfilling prophecy. Why this particular name? It's a nod to the infamous **Roko's basilisk**, which if you're curious (or bored), you can dive into [here](https://en.wikipedia.org/wiki/Roko%27s_basilisk) and [here](https://www.lesswrong.com/tag/rokos-basilisk). Spoiler alert: it's the ultimate rabbit hole.

## Download and installation

Hold your horses! Not quite there yet...

## Shortcuts

### Global shortcuts

These shortcuts work anywhere in Windows.

- `AltGr+Shift+B`: Minimize to tray or show the BasiliskLLM window.

  Note: you can also minimize the window by clicking the minimize button or by pressing the *Windows key + Down arrow*.

- `AltGr+Shift+W`: take a screenshot of the current window and send the image to the active chat.

- `AltGr+Shift+F`: take a screenshot of the full screen and send the image to the active chat.

### BasiliskLLM window shortcuts

These shortcuts work only when the BasiliskLLM window is focused.

- `Ctrl+1` to `Ctrl+9`: Select the corresponding tab. Each tab is a different chat.
- `Ctrl+n`: Create a new chat.
- `Ctrl+w`: Close the current chat.

## 🛠 Setting Up Your Dev Palace 🏰

Requirements: Python 3.12.2 (because only the best for us, obviously)

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

## 🚀 build standalone executable

You can build a standalone executable with the following command:

```shell
poetry run python -m cx_Freeze build_exe
```

This will create a `dist` directory with the standalone executable. You can run the executable by double-clicking on it.

## 📦 packaging for windows

The project uses innosetup to make an all in one installer. The installer package the output produced by cxfreeze.
To create the installer, you need to install innosetup. You can download it from [here](https://www.jrsoftware.org/isdl.php).
After installing innosetup, check that the `ISCC.exe` is in your PATH. You can do this by running the following command:

```shell
where ISCC.exe
```

If the command returns the path to the `ISCC.exe`, you are good to go.
You can create the installer by running the following command:

```shell
iscc win_installer.iss
```

This will create an installer in the `output_setup` directory.

## 🌍 translations

This project is open to translations. If you want to help us translate the project into your language, you can create a po template file with the following command:

```shell
python setup.py extract_messages
```

Then you can create a po file for your language with the following command:

```shell
python setup.py init_catalog --locale <your_language_code>
```

The language code should be in the format of the ISO 639-1 standard. For example, for Spanish, the language code is `es`. You can find the language code for your language [here](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes).
Use a text editor like [Poedit](https://poedit.net/) to translate the strings in the po file. When you finish translating the strings, you can compile the po file to a mo file with the following command:

```shell
python setup.py compile_catalog
```

## 🧙‍♂️🧙‍♀️ Contributions: Summoning All Wizards and Witches

Got ideas, translations, or magical spells to contribute? We're all ears. Open an issue like it's your Hogwarts acceptance letter. Time to make some magic happen!
