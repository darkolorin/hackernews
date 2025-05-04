import rumps
import requests
import webbrowser
import threading
import time
import logging
from datetime import datetime

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

# --- App Class ---
class HackerNewsApp(rumps.App):
    def __init__(self):
        super(HackerNewsApp, self).__init__(f"{ICON_DEFAULT} Loading...")
        self.top_article_url = None
        self.last_refresh_time = None
        self.menu = ["Loading...", None, "Refresh", rumps.MenuItem("Quit", callback=self.quit_app)]
        # Remove the explicit thread start, Timer will handle the background task
        # threading.Thread(target=self.update_hacker_news_thread, args=(None,), daemon=True).start()
        # Set up the recurring timer - it runs the callback in a thread
        self.update_timer = rumps.Timer(self.update_hacker_news_thread, UPDATE_INTERVAL_SECONDS)
        self.update_timer.start() # Start the timer (runs first update soon)
        logging.info("HackerNewsApp initialized, timer started.")


    def fetch_top_story_ids(self):
        """Fetches top story IDs from Hacker News."""
        try:
            logging.info(f"Fetching top story IDs from {TOP_STORIES_URL}")
            response = requests.get(TOP_STORIES_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            story_ids = response.json()
            logging.info(f"Fetched {len(story_ids)} top story IDs.")
            return story_ids
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching top stories: {e}")
            rumps.notification("Hacker News App Error", "Network Error", f"Could not fetch top stories: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching top story IDs: {e}")
            rumps.notification("Hacker News App Error", "API Error", f"Could not process top stories response: {e}")
            return None

    def fetch_item_details(self, item_id):
        """Fetches details for a specific Hacker News item."""
        url = ITEM_URL_TEMPLATE.format(item_id)
        try:
            # logging.debug(f"Fetching details for item {item_id} from {url}") # DEBUG level
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            details = response.json()
            # logging.debug(f"Successfully fetched details for item {item_id}") # DEBUG level
            return details
        except requests.exceptions.RequestException as e:
            # Log error but don't notify for every single item failure to avoid spam
            logging.warning(f"Error fetching item {item_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching item {item_id}: {e}")
            return None

    def update_hacker_news_thread(self, _):
        """Runs the update logic in a separate thread to avoid blocking the UI."""
        logging.info("Starting Hacker News update cycle.")
        top_story_ids = self.fetch_top_story_ids()

        if top_story_ids is None:
            self.title = f"{ICON_ERROR} HN Err"
            self.menu.clear() # Explicitly clear before error assignment
            self.menu = [
                "Error fetching stories",
                None,
                "Refresh",
                rumps.MenuItem("Quit", callback=self.quit_app)
            ]
            logging.warning("Update failed: Could not fetch story IDs.")
            return

        fetched_articles = []
        processed_ids = 0
        max_ids_to_process = min(len(top_story_ids), MAX_ARTICLES_IN_MENU * 5) # Look deeper if top ones are Ask HN etc.

        with requests.Session() as session: # Use a session for potential connection reuse
            for story_id in top_story_ids:
                if len(fetched_articles) >= MAX_ARTICLES_IN_MENU:
                    logging.info(f"Reached target of {MAX_ARTICLES_IN_MENU} articles.")
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
            self.title = f"{ICON_DEFAULT} HN Empty"
            self.menu.clear() # Explicitly clear before error assignment
            self.menu = [
                "No suitable articles found",
                None,
                "Refresh",
                rumps.MenuItem("Quit", callback=self.quit_app)
            ]
            logging.warning("Update completed but no suitable articles found.")
            return

        top_article = fetched_articles[0]
        self.top_article_url = top_article.get("url")

        # Update menu bar title (truncated with score)
        score = top_article.get('score', 0)
        title = top_article.get('title', 'No Title')
        prefix = f"{ICON_DEFAULT} [{score}] "
        # Calculate remaining length for title text, ensuring it's non-negative
        available_title_len = max(0, MAX_TITLE_LENGTH - len(prefix))
        truncated_article_title = (title[:available_title_len] + '...') if len(title) > available_title_len else title
        self.title = f"{prefix}{truncated_article_title}"

        # --- Create New Menu Items ---
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

        # Format Refresh item title with last update time
        refresh_title = "Refresh"
        if self.last_refresh_time:
            refresh_time_str = datetime.fromtimestamp(self.last_refresh_time).strftime('%H:%M:%S')
            refresh_title = f"Refresh (Last: {refresh_time_str})"

        # Add Refresh item with callback to the update method itself
        new_menu_items.append(rumps.MenuItem(refresh_title, callback=self.update_hacker_news_thread))
        # Explicitly add Quit MenuItem
        new_menu_items.append(rumps.MenuItem("Quit", callback=self.quit_app))

        # --- Clear and Reassign self.menu ---
        self.menu.clear() # Explicitly clear first
        self.menu = new_menu_items

        # Record successful refresh time
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

    # @rumps.clicked() # <<< Temporarily disabled by commenting out
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

    # @rumps.clicked("Settings") # Removed Settings decorator
    # def settings_menu(self, _): # Removed Settings method
    #     """Callback for the Settings menu item. Opens a settings window."""
    #     logging.info("Settings menu item clicked.")
    #
    #     # Define the content and behavior of the settings window
    #     response = rumps.Window(
    #         title="Hacker News Settings",
    #         message="Enter your Hacker News username (optional):",
    #         default_text="", # Placeholder for the input field
    #         ok="Save",       # Label for the confirmation button
    #         cancel=True      # Show a Cancel button
    #     ).run() # Show the window and wait for user input
    #
    #     if response.clicked: # Check if the user clicked OK/Save
    #         username = response.text
    #         logging.info(f"Settings saved. Username entered: '{username}'")
    #         # TODO: Actually save or use the username (e.g., store in preferences)
    #         rumps.notification("Settings Saved", "Username Updated", f"Username set to: {username}")
    #     else:
    #         logging.info("Settings window cancelled.")

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