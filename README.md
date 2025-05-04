# Hacker News Menu Bar App

A simple macOS menu bar application that displays the latest top story from Hacker News.

## Features

*   Displays the title and score of the current top Hacker News story in the menu bar.
*   Updates the story automatically every hour (configurable).
*   Clicking the menu bar item opens a dropdown menu:
    *   Shows the top 5 stories (title and score).
    *   Clicking a story opens its URL in the default browser.
    *   "Refresh" option to manually update the story list (shows last refresh time).
    *   "Quit" option to exit the application.
*   Packaged as a standalone macOS `.app` bundle.

## Prerequisites

*   macOS
*   Python 3 (Tested with 3.8, might work with others)
*   pip (Python package installer)

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd hacker-news-menu-bar
    ```

2.  **Install dependencies:**
    It's recommended to use a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
    *(Note: A `requirements.txt` file should be created containing `rumps`, `requests`, and `py2app`)*

## Building the Application

This project uses `py2app` to create the standalone `.app` bundle.

1.  **Ensure `py2app` is installed:**
    ```bash
    pip install py2app
    ```

2.  **(Optional) Add a custom icon:**
    *   Create a `.icns` file (e.g., `icon.icns`).
    *   Place it in the project's root directory.
    *   Ensure the `iconfile` option in `setup.py` points to it (`'iconfile': 'icon.icns',`).

3.  **Build the app:**
    ```bash
    python setup.py py2app
    ```
    This will create a `dist` folder containing `HackerNewsMenuBar.app`.

## Running the Application

*   Navigate to the `dist` folder.
*   Double-click `HackerNewsMenuBar.app` to launch it.
*   The app icon will appear in your macOS menu bar.

## Configuration

Some parameters can be adjusted directly in the `hn_menu_bar.py` script:

*   `MAX_TITLE_LENGTH`: Maximum characters for the story title in the menu bar.
*   `UPDATE_INTERVAL_SECONDS`: How often to automatically refresh stories (in seconds).
*   `MAX_ARTICLES_IN_MENU`: Number of stories shown in the dropdown menu.
*   `REQUEST_TIMEOUT`: Network request timeout in seconds.
*   `ICON_DEFAULT`, `ICON_ERROR`: Emojis used for the menu bar icon in normal/error states.

Remember to rebuild the app (`python setup.py py2app`) after changing these.

## Known Issues

*   The direct left-click action on the menu bar icon (intended to open the top story directly) is currently disabled due to a potential conflict with `rumps` or `py2app` during initialization (`AttributeError: 'Menu' object has no attribute 'set_callback'`). The top story can still be opened by clicking the icon to show the menu and then clicking the first story listed.
*   The Quit button functionality within the packaged `.app` might be inconsistent depending on the environment or `py2app` version. We've attempted several fixes, but further investigation might be needed if issues persist. 