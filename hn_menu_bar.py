import rumps
import requests
import webbrowser
import threading
import time
import logging
from datetime import datetime
import json
import os

# --- Configuration Defaults ---
# These are used if settings.json is missing or invalid
DEFAULT_SETTINGS = {
    "MAX_TITLE_LENGTH": 50,
    "UPDATE_INTERVAL_SECONDS": 3600,
    "MAX_ARTICLES_IN_MENU": 5,
    "REQUEST_TIMEOUT": 10,
    "ICON_DEFAULT": "📰",
    "ICON_ERROR": "⚠️"
}
SETTINGS_FILE = "settings.json"

# --- Configuration ---
MAX_TITLE_LENGTH = 50 # Max length for the menu bar title in characters
UPDATE_INTERVAL_SECONDS = 3600 # Update every hour (3600 seconds)
MAX_ARTICLES_IN_MENU = 5 # Number of articles to show in the dropdown menu
REQUEST_TIMEOUT = 10 # Seconds to wait for API requests
ICON_DEFAULT = "📰"
ICON_ERROR = "⚠️"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Hacker News API ---
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
TOP_STORIES_URL = f"{HN_API_BASE}/topstories.json"
ITEM_URL_TEMPLATE = f"{HN_API_BASE}/item/{{}}.json" # Use .format()

# --- Settings Functions ---
def load_settings():
    """Loads settings from JSON file or returns defaults."""
    if not os.path.exists(SETTINGS_FILE):
        logging.warning(f"{SETTINGS_FILE} not found, using default settings.")
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, 'r') as f:
            loaded = json.load(f)
        # Ensure all keys exist, add defaults for missing ones
        settings = DEFAULT_SETTINGS.copy()
        settings.update(loaded) # Overwrite defaults with loaded values
        logging.info(f"Loaded settings from {SETTINGS_FILE}.")
        return settings
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading {SETTINGS_FILE}: {e}. Using default settings.")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Saves settings dictionary to JSON file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        logging.info(f"Saved settings to {SETTINGS_FILE}.")
    except IOError as e:
        logging.error(f"Error saving settings to {SETTINGS_FILE}: {e}")
        rumps.alert("Error saving settings!", f"Could not write to {SETTINGS_FILE}.\n{e}")

# --- App Class ---
class HackerNewsApp(rumps.App):
    def __init__(self):
        # Load settings first
        self.settings = load_settings()

        super(HackerNewsApp, self).__init__(f"{self.settings['ICON_DEFAULT']} Loading...")
        self.top_article_url = None
        self.last_refresh_time = None
        # Define initial menu including Settings as MenuItem
        self.menu = ["Loading...", None, "Refresh", rumps.MenuItem("Settings", callback=self.settings_menu), rumps.MenuItem("Quit", callback=self.quit_app)]

        # Set up the recurring timer using loaded interval
        update_interval = self.settings.get("UPDATE_INTERVAL_SECONDS", DEFAULT_SETTINGS["UPDATE_INTERVAL_SECONDS"])
        self.update_timer = rumps.Timer(self.update_hacker_news_thread, update_interval)
        self.update_timer.start()
        logging.info("HackerNewsApp initialized, timer started.")

    def fetch_top_story_ids(self):
        """Fetches top story IDs from Hacker News."""
        try:
            logging.info(f"Fetching top story IDs from {TOP_STORIES_URL}")
            # Use timeout from settings
            timeout = self.settings.get("REQUEST_TIMEOUT", DEFAULT_SETTINGS["REQUEST_TIMEOUT"])
            response = requests.get(TOP_STORIES_URL, timeout=timeout)
            response.raise_for_status()
            story_ids = response.json()
            logging.info(f"Fetched {len(story_ids)} top story IDs.")
            return story_ids
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching top stories: {e}")
            rumps.notification("Hacker News App Error", "Network Error", f"Could not fetch top stories: {e}")
            self.title = f"{self.settings['ICON_ERROR']} HN Err"
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching top story IDs: {e}")
            rumps.notification("Hacker News App Error", "API Error", f"Could not process top stories response: {e}")
            self.title = f"{self.settings['ICON_ERROR']} HN Err"
            return None

    def fetch_item_details(self, item_id):
        """Fetches details for a specific Hacker News item."""
        url = ITEM_URL_TEMPLATE.format(item_id)
        try:
            timeout = self.settings.get("REQUEST_TIMEOUT", DEFAULT_SETTINGS["REQUEST_TIMEOUT"])
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            details = response.json()
            return details
        except requests.exceptions.RequestException as e:
            logging.warning(f"Error fetching item {item_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching item {item_id}: {e}")
            return None

    def update_hacker_news_thread(self, _):
        """Runs the update logic in a separate thread to avoid blocking the UI."""
        logging.info("Starting Hacker News update cycle.")
        top_story_ids = self.fetch_top_story_ids()

        # Use icons from settings
        icon_default = self.settings.get("ICON_DEFAULT", DEFAULT_SETTINGS["ICON_DEFAULT"])
        icon_error = self.settings.get("ICON_ERROR", DEFAULT_SETTINGS["ICON_ERROR"])

        if top_story_ids is None:
            self.title = f"{icon_error} HN Err"
            self.menu.clear()
            # Rebuild menu explicitly on error
            self.menu = [
                "Error fetching stories",
                None,
                "Refresh",
                rumps.MenuItem("Settings", callback=self.settings_menu), # Explicit MenuItem
                rumps.MenuItem("Quit", callback=self.quit_app)
            ]
            logging.warning("Update failed: Could not fetch story IDs.")
            return

        fetched_articles = []
        processed_ids = 0
        # Use max articles from settings
        max_articles = self.settings.get("MAX_ARTICLES_IN_MENU", DEFAULT_SETTINGS["MAX_ARTICLES_IN_MENU"])
        max_ids_to_process = min(len(top_story_ids), max_articles * 5)

        with requests.Session() as session:
            for story_id in top_story_ids:
                if len(fetched_articles) >= max_articles:
                    logging.info(f"Reached target of {max_articles} articles.")
                    break
                if processed_ids >= max_ids_to_process:
                    logging.warning(f"Processed {max_ids_to_process} IDs without finding enough articles.")
                    break

                processed_ids += 1
                details = self.fetch_item_details(story_id)

                if details and details.get("type") == "story" and details.get("url"):
                    article = {
                        "title": details.get("title", "No Title Provided"),
                        "url": details.get("url"),
                        "id": story_id,
                        "score": details.get("score", 0)
                    }
                    fetched_articles.append(article)

        if not fetched_articles:
            self.title = f"{icon_default} HN Empty"
            self.menu.clear()
            # Rebuild menu explicitly on error
            self.menu = [
                "No suitable articles found",
                None,
                "Refresh",
                rumps.MenuItem("Settings", callback=self.settings_menu), # Explicit MenuItem
                rumps.MenuItem("Quit", callback=self.quit_app)
            ]
            logging.warning("Update completed but no suitable articles found.")
            return

        top_article = fetched_articles[0]
        self.top_article_url = top_article.get("url")

        # Use title length from settings
        max_title_len_setting = self.settings.get("MAX_TITLE_LENGTH", DEFAULT_SETTINGS["MAX_TITLE_LENGTH"])
        score = top_article.get('score', 0)
        title = top_article.get('title', 'No Title')
        prefix = f"{icon_default} [{score}] "
        available_title_len = max(0, max_title_len_setting - len(prefix))
        truncated_article_title = (title[:available_title_len] + '...') if len(title) > available_title_len else title
        self.title = f"{prefix}{truncated_article_title}"

        new_menu_items = []
        for i, article in enumerate(fetched_articles):
            score = article.get('score', 0)
            title = article.get('title', 'No Title')
            menu_title = f"{i+1}. [{score}] {title}"
            max_len = 75 - (len(str(score)) + 4)
            menu_title_truncated = (menu_title[:max_len] + '...') if len(menu_title) > max_len else menu_title
            callback = self.create_menu_callback(article.get("url"))
            menu_item = rumps.MenuItem(menu_title_truncated, callback=callback)
            new_menu_items.append(menu_item)

        new_menu_items.append(None)

        refresh_title = "Refresh"
        if self.last_refresh_time:
            refresh_time_str = datetime.fromtimestamp(self.last_refresh_time).strftime('%H:%M:%S')
            refresh_title = f"Refresh (Last: {refresh_time_str})"

        new_menu_items.append(rumps.MenuItem(refresh_title, callback=self.update_hacker_news_thread))
        # Explicitly add Settings MenuItem
        new_menu_items.append(rumps.MenuItem("Settings", callback=self.settings_menu))
        new_menu_items.append(rumps.MenuItem("Quit", callback=self.quit_app))

        self.menu.clear()
        self.menu = new_menu_items

        self.last_refresh_time = time.time()
        logging.info(f"Update successful. Title set to: {truncated_article_title}")

    def create_menu_callback(self, url):
        """Creates a callback function for a menu item to open a specific URL."""
        if not url:
            def no_url_callback(_):
                logging.warning("Clicked menu item with no associated URL.")
                rumps.alert("No URL", "This Hacker News item does not have an external URL.")
            return no_url_callback
        else:
            def open_url_callback(_):
                logging.info(f"Opening URL via menu click: {url}")
                try:
                    webbrowser.open(url)
                except Exception as e:
                    logging.error(f"Failed to open URL {url}: {e}")
                    rumps.notification("Error", "Browser Error", f"Could not open link: {e}")
            return open_url_callback

    # @rumps.clicked() # Left-click still disabled
    def open_top_article(self, _):
        """Opens the primary top article URL when the menu bar icon is left-clicked."""
        if self.top_article_url:
            logging.info(f"Left-click: Opening top article URL: {self.top_article_url}")
            try:
                webbrowser.open(self.top_article_url)
            except Exception as e:
                logging.error(f"Failed to open top article URL {self.top_article_url}: {e}")
                rumps.notification("Error", "Browser Error", f"Could not open link: {e}")
        else:
            logging.warning("Left-click: No top article URL is currently set.")

    @rumps.clicked("Settings")
    def settings_menu(self, _):
        """Opens a settings window to configure interval and title length."""
        logging.info("Settings menu item clicked.")

        # Prepare current values for the prompt
        current_interval = self.settings.get("UPDATE_INTERVAL_SECONDS", DEFAULT_SETTINGS["UPDATE_INTERVAL_SECONDS"])
        current_title_len = self.settings.get("MAX_TITLE_LENGTH", DEFAULT_SETTINGS["MAX_TITLE_LENGTH"])

        prompt_message = f"Update Interval (seconds):\nMax Title Length (chars):"
        default_input = f"{current_interval}\n{current_title_len}"

        response = rumps.Window(
            title="Configure Settings",
            message=prompt_message,
            default_text=default_input,
            ok="Save",
            cancel=True,
            dimensions=(300, 100)
        ).run()

        if response.clicked: # User clicked Save
            try:
                lines = response.text.strip().split('\n')
                if len(lines) != 2:
                    raise ValueError("Expected two lines of input.")

                new_interval_str, new_title_len_str = lines
                new_interval = int(new_interval_str.strip())
                new_title_len = int(new_title_len_str.strip())

                if new_interval <= 0 or new_title_len <= 0:
                    raise ValueError("Values must be positive integers.")

                # Update settings dictionary
                self.settings["UPDATE_INTERVAL_SECONDS"] = new_interval
                self.settings["MAX_TITLE_LENGTH"] = new_title_len

                # Save to file
                save_settings(self.settings)

                # Apply interval change to timer
                if self.update_timer.interval != new_interval:
                    logging.info(f"Changing update interval to {new_interval} seconds.")
                    self.update_timer.interval = new_interval # rumps timers allow direct interval update
                    # Optionally trigger an immediate refresh after changing settings
                    # self.update_hacker_news_thread(None)

                rumps.notification("Settings Saved", f"Interval: {new_interval}s, Title Length: {new_title_len} chars", "Changes applied.")
                logging.info("Settings saved and applied.")

            except ValueError as e:
                logging.error(f"Invalid settings input: {e}")
                rumps.alert("Invalid Input", f"Could not save settings: {e}\nPlease enter positive numbers on separate lines.")
            except Exception as e:
                logging.error(f"Error processing settings: {e}")
                rumps.alert("Error", f"Could not process settings: {e}")
        else:
            logging.info("Settings window cancelled.")

    # Keep decorator as backup, but MenuItem callback should primarily work
    @rumps.clicked("Quit")
    def quit_app(self, _):
        logging.info("Quit button clicked.")
        rumps.quit_application()

# --- Main Execution ---
if __name__ == '__main__':
    logging.info("Starting Hacker News Menu Bar App...")
    try:
        app = HackerNewsApp()
        app.run()
    except Exception as e:
        logging.critical(f"Failed to initialize or run the application: {e}", exc_info=True) # Add exc_info for more details 